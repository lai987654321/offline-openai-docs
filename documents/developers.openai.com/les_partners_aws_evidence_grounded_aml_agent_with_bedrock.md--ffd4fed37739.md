# AML Analysis with the Agents SDK on Amazon Bedrock

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

This notebook demonstrates one synthetic anti-money-laundering (AML) analysis with the OpenAI Agents SDK and GPT-5.6 Sol on Amazon Bedrock. The default path uses a deterministic offline assessment so a top-to-bottom run makes no model call. An explicit opt-in runs the agent with read-only tools. Both paths validate material claims against deterministic calculations.

An alert starts an investigation. It does not prove wrongdoing. The model proposes an assessment. Application code verifies the structured claims and controls workflow state. A qualified human decides whether optional drafting may begin. All data is synthetic. Nothing here files a Suspicious Activity Report (SAR) or implements production compliance policy.


## Workflow boundaries

The notebook keeps deterministic evidence, model proposals, application controls, and human authority in separate boundaries.

![Four boundaries for the regulated-investigation workflow](https://developers.openai.com/cookbook/assets/images/partners/AWS/evidence-grounded-four-boundaries.png)


## 1. Start the notebook

The default offline path requires Python 3.10 or newer and `uv`. The optional paid Bedrock paths also require AWS credentials through the standard credential chain and access to `openai.gpt-5.6-sol`. From a clone of [openai/openai-cookbook](https://github.com/openai/openai-cookbook), run:

```bash
cd /path/to/openai-cookbook
unset VIRTUAL_ENV
export AWS_REGION=us-east-2
uv run --with jupyterlab jupyter lab
```

Open this notebook at `examples/partners/AWS/evidence_grounded_aml_agent_with_bedrock.ipynb`. The default run keeps both paid flags disabled. To run the analysis agent, set `RUN_ANALYSIS_DEMO=true` before starting Jupyter. To run the optional drafting agent, set `RUN_DRAFTING_DEMO=true`. Set `AWS_PROFILE` first if your organization uses a named profile. Never paste AWS credentials into the notebook.


```python
%pip install -U "openai[bedrock]>=2.46.0" "openai-agents>=0.18.2" "pydantic>=2.13.0" --quiet
```

## 2. Configure Amazon Bedrock

Both paid demonstrations require an explicit environment flag. When either flag is enabled, the SDK uses the AWS credential chain and a separate client lists models through the Bedrock Mantle discovery endpoint before paid inference. With both flags disabled, this cell constructs no client and makes no AWS call.


```python
import json
import math
import os
from datetime import datetime
from typing import Literal

from agents import (
    Agent,
    ModelSettings,
    RunConfig,
    RunContextWrapper,
    Runner,
    function_tool,
    set_default_openai_api,
    set_default_openai_client,
)
from agents.items import ToolCallItem, ToolCallOutputItem
from openai import AsyncOpenAI
from openai.providers import bedrock
from openai.types.shared import Reasoning
from pydantic import BaseModel, Field

AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
MODEL_ID = os.getenv("BEDROCK_MODEL", "openai.gpt-5.6-sol")
RUN_ANALYSIS_DEMO = (
    os.getenv("RUN_ANALYSIS_DEMO", "false").casefold() == "true"
)
RUN_DRAFTING_DEMO = (
    os.getenv("RUN_DRAFTING_DEMO", "false").casefold() == "true"
)
RUN_BEDROCK_DEMOS = RUN_ANALYSIS_DEMO or RUN_DRAFTING_DEMO

set_default_openai_api("responses")

if RUN_BEDROCK_DEMOS:
    client = AsyncOpenAI(provider=bedrock(region=AWS_REGION))
    models_client = AsyncOpenAI(
        provider=bedrock(
            region=AWS_REGION,
            base_url=(
                f"https://bedrock-mantle.{AWS_REGION}.api.aws/v1"
            ),
        )
    )
    set_default_openai_client(client, use_for_tracing=False)
    available_models = await models_client.models.list()
    available_model_ids = {model.id for model in available_models.data}
    if MODEL_ID not in available_model_ids:
        raise RuntimeError(
            f"{MODEL_ID!r} is not visible in {AWS_REGION}. "
            "Verify the AWS account, Region, and Bedrock model access."
        )
    print({"region": AWS_REGION, "model": MODEL_ID, "preflight": "passed"})
else:
    print("Paid Bedrock demonstrations disabled; no AWS call was made.")
```

## 3. Load the synthetic case

The case has three same-day cash credits followed by an outbound wire. A factory creates a fresh typed case for each application context. The amounts make the calculations easy to reproduce; they are demonstration rules, not regulatory thresholds.


```python
DEMO_CASH_AMOUNT_MIN = 9_000
DEMO_CASH_AMOUNT_MAX = 10_000
DEMO_RAPID_MOVEMENT_RATIO = 0.90
DEMO_REQUIRED_CASH_CREDITS = 3

class Transaction(BaseModel):
    id: str
    timestamp: str
    direction: Literal["CREDIT", "DEBIT"]
    channel: Literal["CASH", "WIRE"]
    amount: int = Field(gt=0)
    currency: str
    counterparty: str
    country_code: str


class InvestigationCase(BaseModel):
    case_id: str
    subject: str
    subject_type: Literal["BUSINESS"]
    stated_business: str
    risk_tier: Literal["STANDARD"]
    alert_reason: str
    transactions: list[Transaction]


def build_synthetic_case() -> InvestigationCase:
    return InvestigationCase(
        case_id="SYNTH-AML-001",
        subject="Northstar Imports LLC",
        subject_type="BUSINESS",
        stated_business="Wholesale home goods",
        risk_tier="STANDARD",
        alert_reason=(
            "Unusual cash activity followed by an outbound wire"
        ),
        transactions=[
            Transaction(
                id="TXN-001",
                timestamp="2026-05-04T09:20:00Z",
                direction="CREDIT",
                channel="CASH",
                amount=9200,
                currency="USD",
                counterparty="Synthetic cash deposit A",
                country_code="US",
            ),
            Transaction(
                id="TXN-002",
                timestamp="2026-05-04T11:05:00Z",
                direction="CREDIT",
                channel="CASH",
                amount=9500,
                currency="USD",
                counterparty="Synthetic cash deposit B",
                country_code="US",
            ),
            Transaction(
                id="TXN-003",
                timestamp="2026-05-04T13:40:00Z",
                direction="CREDIT",
                channel="CASH",
                amount=9800,
                currency="USD",
                counterparty="Synthetic cash deposit C",
                country_code="US",
            ),
            Transaction(
                id="TXN-004",
                timestamp="2026-05-04T16:10:00Z",
                direction="DEBIT",
                channel="WIRE",
                amount=28200,
                currency="USD",
                counterparty="Synthetic overseas supplier",
                country_code="GB",
            ),
        ],
    )


print(build_synthetic_case().model_dump_json(indent=2))
```

## 4. Define the output and evidence tools

The output schema makes the material claims machine-checkable. Each finding carries its evidence IDs and computed values. The validator recomputes those values because a valid transaction ID alone does not prove support.

A typed `InvestigationContext` scopes one tenant, case, analysis, and review history. Each request creates its own context instance, passes it through `Runner.run(..., context=...)`, and lets tools access it through `RunContextWrapper`. The context is not itself model input; each read-only tool controls which fields it returns.

Two tools return source facts, and one applies transparent demo checks. The checks identify signals for investigation, not intent, wrongdoing, or a filing requirement.


```python
class Finding(BaseModel):
    finding_type: Literal["STRUCTURING_SIGNAL", "RAPID_MOVEMENT_SIGNAL"]
    title: str
    explanation: str
    evidence_ids: list[str] = Field(min_length=1)
    cash_credit_count: int = Field(ge=0)
    cash_credit_total_usd: int = Field(ge=0)
    outbound_wire_usd: int | None
    movement_ratio_percent: float | None


class RiskAssessment(BaseModel):
    case_id: str
    assessment_posture: Literal[
        "ROUTINE_REVIEW",
        "ENHANCED_REVIEW",
        "ESCALATE_FOR_QUALIFIED_REVIEW",
    ]
    executive_summary: str
    findings: list[Finding] = Field(min_length=2, max_length=2)
    information_gaps: list[str] = Field(min_length=1)
    recommended_next_steps: list[str] = Field(min_length=1)
    drafting_authorized: Literal[False]
    filing_decision: Literal["NOT_DETERMINED"]


class EvidenceCitation(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(min_length=1)


class SarDraft(BaseModel):
    case_id: str
    narrative: str
    draft_status: Literal[
        "DRAFT_READY_FOR_HUMAN_REVIEW", "INSUFFICIENT_INFORMATION"
    ]
    citations: list[EvidenceCitation] = Field(min_length=1)
    disclaimer: str


ReviewDecision = Literal["APPROVE_DRAFTING", "REJECT_DRAFTING"]
ReviewStatus = Literal[
    "PENDING_REVIEW",
    "PENDING_REREVIEW",
    "APPROVE_DRAFTING",
    "REJECT_DRAFTING",
]


class HumanReviewEvent(BaseModel):
    event: Literal["HUMAN_REVIEW"] = "HUMAN_REVIEW"
    analysis_revision: int = Field(ge=1)
    reviewer_alias: str
    decision: ReviewDecision
    rationale: str


class AnalysisRevisedEvent(BaseModel):
    event: Literal["ANALYSIS_REVISED"] = "ANALYSIS_REVISED"
    from_revision: int = Field(ge=1)
    to_revision: int = Field(ge=2)
    rework_note: str


ReviewEvent = HumanReviewEvent | AnalysisRevisedEvent


class InvestigationContext(BaseModel):
    tenant_id: str
    case: InvestigationCase
    analysis: RiskAssessment | None = None
    analysis_revision: int = Field(default=0, ge=0)
    review_status: ReviewStatus = "PENDING_REVIEW"
    review_history: list[ReviewEvent] = Field(default_factory=list)
    draft: SarDraft | None = None


def new_investigation_context() -> InvestigationContext:
    return InvestigationContext(
        tenant_id="SYNTHETIC-TENANT-001",
        case=build_synthetic_case(),
    )


run_context = new_investigation_context()
```

```python
def require_known_case(
    wrapper: RunContextWrapper[InvestigationContext],
    case_id: str,
) -> InvestigationCase:
    case = wrapper.context.case
    if case_id != case.case_id:
        raise ValueError(f"Unknown case in this request context: {case_id}")
    return case


@function_tool(failure_error_function=None)
def get_case_profile(
    wrapper: RunContextWrapper[InvestigationContext],
    case_id: str,
) -> str:
    """Return the synthetic profile and alert context for one case."""

    case = require_known_case(wrapper, case_id)
    profile = case.model_dump(exclude={"transactions"})
    return json.dumps(profile)


@function_tool(failure_error_function=None)
def list_case_transactions(
    wrapper: RunContextWrapper[InvestigationContext],
    case_id: str,
) -> str:
    """Return all synthetic transactions and their evidence identifiers."""

    case = require_known_case(wrapper, case_id)
    return json.dumps(
        [transaction.model_dump() for transaction in case.transactions]
    )


def parse_transaction_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def detect_typology_signals(
    case: InvestigationCase,
) -> list[dict[str, object]]:
    transactions = case.transactions
    cash_credits = [
        transaction
        for transaction in transactions
        if transaction.direction == "CREDIT"
        and transaction.channel == "CASH"
        and DEMO_CASH_AMOUNT_MIN
        <= transaction.amount
        < DEMO_CASH_AMOUNT_MAX
    ]
    if len(cash_credits) < DEMO_REQUIRED_CASH_CREDITS:
        return []

    activity_dates = {
        parse_transaction_timestamp(item.timestamp).date()
        for item in cash_credits
    }
    currencies = {item.currency for item in cash_credits}
    if len(activity_dates) != 1 or len(currencies) != 1:
        return []

    cash_total = sum(item.amount for item in cash_credits)
    latest_cash_timestamp = max(
        parse_transaction_timestamp(item.timestamp)
        for item in cash_credits
    )
    rapid_wires = [
        transaction
        for transaction in transactions
        if transaction.direction == "DEBIT"
        and transaction.channel == "WIRE"
        and transaction.currency in currencies
        and parse_transaction_timestamp(transaction.timestamp).date()
        in activity_dates
        and parse_transaction_timestamp(transaction.timestamp)
        > latest_cash_timestamp
        and transaction.amount
        >= cash_total * DEMO_RAPID_MOVEMENT_RATIO
    ]

    cash_ids = [item.id for item in cash_credits]
    signals = [
        {
            "finding_type": "STRUCTURING_SIGNAL",
            "evidence_ids": cash_ids,
            "cash_credit_count": len(cash_credits),
            "cash_credit_total_usd": cash_total,
            "outbound_wire_usd": None,
            "movement_ratio_percent": None,
        }
    ]
    if rapid_wires:
        wire = rapid_wires[0]
        signals.append(
            {
                "finding_type": "RAPID_MOVEMENT_SIGNAL",
                "evidence_ids": [*cash_ids, wire.id],
                "cash_credit_count": len(cash_credits),
                "cash_credit_total_usd": cash_total,
                "outbound_wire_usd": wire.amount,
                "movement_ratio_percent": round(
                    wire.amount / cash_total * 100, 1
                ),
            }
        )
    return signals


@function_tool(failure_error_function=None)
def run_typology_checks(
    wrapper: RunContextWrapper[InvestigationContext],
    case_id: str,
) -> str:
    """Return transparent demo signals and their calculated support."""

    case = require_known_case(wrapper, case_id)
    return json.dumps(detect_typology_signals(case))


print(json.dumps(detect_typology_signals(run_context.case), indent=2))
```

## 5. Run the analysis agent

The instructions require all three tools and a typed result. With `RUN_ANALYSIS_DEMO=true`, `Runner.run` manages the paid model and tool loop. The default path uses a labeled deterministic fixture with simulated tool-call evidence so the remaining validation and review cells run without AWS credentials or paid inference. The fixture does not prove Agents SDK orchestration.


```python
MODEL_SETTINGS = ModelSettings(
    reasoning=Reasoning(effort="medium"),
    store=False,
)

analysis_agent = Agent[InvestigationContext](
    name="Synthetic AML Analysis Agent",
    model=MODEL_ID,
    model_settings=MODEL_SETTINGS,
    output_type=RiskAssessment,
    tools=[
        get_case_profile,
        list_case_transactions,
        run_typology_checks,
    ],
    instructions=(
        "Analyze exactly one synthetic AML case. Call get_case_profile, "
        "list_case_transactions, and run_typology_checks. Copy the "
        "deterministic tool's evidence IDs and computed values into the "
        "matching structured finding fields. Do not introduce other amounts "
        "in the finding explanations. Treat signals as prompts for qualified "
        "review, not proof of intent or wrongdoing. Identify missing "
        "information. Set drafting_authorized to false and filing_decision "
        "to NOT_DETERMINED. Do not draft or file a SAR, change case state, "
        "approve your own work, or claim that filing is required. Return "
        "only the RiskAssessment schema."
    ),
)

REQUIRED_ANALYSIS_TOOLS = {
    "get_case_profile",
    "list_case_transactions",
    "run_typology_checks",
}

FINDING_TEXT = {
    "STRUCTURING_SIGNAL": (
        "Cash-credit pattern",
        "The deterministic check identified same-day cash credits.",
    ),
    "RAPID_MOVEMENT_SIGNAL": (
        "Rapid movement pattern",
        "The deterministic check identified a later outbound wire.",
    ),
}


def build_offline_assessment(
    context: InvestigationContext,
) -> RiskAssessment:
    findings = []
    for signal in detect_typology_signals(context.case):
        title, explanation = FINDING_TEXT[signal["finding_type"]]
        findings.append(
            Finding(
                finding_type=signal["finding_type"],
                title=title,
                explanation=explanation,
                evidence_ids=signal["evidence_ids"],
                cash_credit_count=signal["cash_credit_count"],
                cash_credit_total_usd=signal["cash_credit_total_usd"],
                outbound_wire_usd=signal["outbound_wire_usd"],
                movement_ratio_percent=signal["movement_ratio_percent"],
            )
        )
    return RiskAssessment(
        case_id=context.case.case_id,
        assessment_posture="ESCALATE_FOR_QUALIFIED_REVIEW",
        executive_summary=(
            "Synthetic signals require qualified review."
        ),
        findings=findings,
        information_gaps=[
            "Source-of-funds records remain unverified."
        ],
        recommended_next_steps=[
            "Obtain source records for qualified human review."
        ],
        drafting_authorized=False,
        filing_decision="NOT_DETERMINED",
    )


if RUN_ANALYSIS_DEMO:
    result = await Runner.run(
        analysis_agent,
        f"Analyze synthetic case {run_context.case.case_id}.",
        context=run_context,
        max_turns=8,
        run_config=RunConfig(
            tracing_disabled=True,
            workflow_name="Validated synthetic AML analysis",
        ),
    )
    assessment = result.final_output
    tool_calls = {
        item.raw_item.name
        for item in result.new_items
        if isinstance(item, ToolCallItem)
    }
    analysis_source = "paid Agents SDK run"
else:
    assessment = build_offline_assessment(run_context)
    tool_calls = set(REQUIRED_ANALYSIS_TOOLS)
    analysis_source = "offline fixture with simulated tool calls"

print("Analysis source:", analysis_source)
print("Tool-call evidence:", sorted(tool_calls))
print(assessment.model_dump_json(indent=2))
```

## 6. Validate support, not just citation syntax

The validator performs three distinct checks:

1. **Citation validity:** every evidence ID exists in this case.
2. **Claim support:** each finding type uses the exact transactions and computed values returned by deterministic application code.
3. **Structured authority:** `drafting_authorized` must remain `false`, and `filing_decision` must remain `NOT_DETERMINED`.

The schema prevents the model from granting drafting authority or making a filing decision through those structured fields. The validator does not classify every possible free-form paraphrase. A qualified reviewer still evaluates the narrative, information gaps, relevance, and disposition. Production systems should add expert-reviewed datasets, trace grading, adversarial cases, and policy-specific tests.


```python
def validate_risk_assessment(
    candidate: RiskAssessment,
    observed_tool_calls: set[str],
    context: InvestigationContext,
) -> dict[str, bool]:
    expected = {
        signal["finding_type"]: signal
        for signal in detect_typology_signals(context.case)
    }
    valid_evidence_ids = {
        transaction.id for transaction in context.case.transactions
    }
    observed = {
        finding.finding_type: finding for finding in candidate.findings
    }
    unique_finding_types = len(observed) == len(candidate.findings)

    valid_citations = all(
        finding.evidence_ids
        and set(finding.evidence_ids).issubset(valid_evidence_ids)
        for finding in candidate.findings
    )
    supported_claims = unique_finding_types and set(observed) == set(expected)
    if supported_claims:
        for finding_type, expected_support in expected.items():
            finding = observed[finding_type]
            supported_claims = supported_claims and (
                set(finding.evidence_ids)
                == set(expected_support["evidence_ids"])
                and finding.cash_credit_count
                == expected_support["cash_credit_count"]
                and finding.cash_credit_total_usd
                == expected_support["cash_credit_total_usd"]
                and finding.outbound_wire_usd
                == expected_support["outbound_wire_usd"]
                and (
                    finding.movement_ratio_percent is None
                    and expected_support["movement_ratio_percent"] is None
                    or finding.movement_ratio_percent is not None
                    and expected_support["movement_ratio_percent"] is not None
                    and math.isclose(
                        finding.movement_ratio_percent,
                        expected_support["movement_ratio_percent"],
                        abs_tol=0.1,
                    )
                )
            )

    checks = {
        "case identity": candidate.case_id == context.case.case_id,
        "required tools": REQUIRED_ANALYSIS_TOOLS.issubset(
            observed_tool_calls
        ),
        "valid citations": valid_citations,
        "material claims supported": supported_claims,
        "structured authority denied": (
            candidate.drafting_authorized is False
            and candidate.filing_decision == "NOT_DETERMINED"
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("Assessment validation failed: " + ", ".join(failed))
    return checks


checks = validate_risk_assessment(assessment, tool_calls, run_context)
for check_name in checks:
    print("PASS:", check_name)
```

## 7. Exercise negative cases

These local tests demonstrate failure behavior without additional model calls. A fabricated amount can use real transaction IDs and still be unsupported. Invalid IDs, a missing tool call, a structured authority claim, and a rejected review are separate failure modes.


```python
def expect_validation_failure(
    label: str,
    candidate: RiskAssessment,
    observed_tools: set[str],
    context: InvestigationContext,
) -> None:
    try:
        validate_risk_assessment(candidate, observed_tools, context)
    except ValueError as exc:
        print(f"PASS ({label}):", exc)
    else:
        raise AssertionError(f"Expected validation failure: {label}")


fabricated_claim = assessment.model_copy(deep=True)
fabricated_claim.findings[0].cash_credit_total_usd = 50_000
expect_validation_failure(
    "fabricated amount", fabricated_claim, tool_calls, run_context
)

invalid_citation = assessment.model_copy(deep=True)
invalid_citation.findings[0].evidence_ids = ["TXN-999"]
expect_validation_failure(
    "invalid citation", invalid_citation, tool_calls, run_context
)

missing_tool_calls = tool_calls - {"run_typology_checks"}
expect_validation_failure(
    "missing tool", assessment, missing_tool_calls, run_context
)

invalid_authority = assessment.model_copy(deep=True)
invalid_authority.drafting_authorized = True
invalid_authority.filing_decision = "FILE_REQUIRED"
expect_validation_failure(
    "structured authority", invalid_authority, tool_calls, run_context
)
```

## 8. Preserve rejection and require explicit re-review

The application now owns the approval boundary. It first stores the validated assessment, records a rejection, and proves drafting remains blocked. A revised assessment is then submitted as a new revision and reviewed again. The original rejection stays in `review_history`; it is never reset or overwritten.

The synthetic reviewer alias and typed context keep the example visible in one notebook. A concurrent service must create a separate context for every request and tenant. Production systems must derive reviewer identity from authentication, authorize the case and operation, persist revisions and decisions durably, and maintain an independently governed audit record.


```python
run_context.analysis = assessment
run_context.analysis_revision = 1
run_context.review_status = "PENDING_REVIEW"
run_context.review_history.clear()
run_context.draft = None


def record_human_review(
    context: InvestigationContext,
    reviewer_alias: str,
    decision: ReviewDecision,
    rationale: str,
) -> HumanReviewEvent:
    if context.review_status not in {
        "PENDING_REVIEW",
        "PENDING_REREVIEW",
    }:
        raise RuntimeError("The current analysis revision is not awaiting review")
    if len(rationale.strip()) < 12:
        raise ValueError("Review rationale is too short")

    event = HumanReviewEvent(
        analysis_revision=context.analysis_revision,
        reviewer_alias=reviewer_alias,
        decision=decision,
        rationale=rationale,
    )
    context.review_history.append(event)
    context.review_status = decision
    return event


def require_drafting_allowed(
    context: InvestigationContext,
) -> RiskAssessment:
    analysis = context.analysis
    history = context.review_history
    latest = history[-1] if history else None
    if not isinstance(analysis, RiskAssessment):
        raise RuntimeError(  # noqa: TRY004 - unmet workflow precondition
            "A validated analysis is required before drafting"
        )
    if (
        not isinstance(latest, HumanReviewEvent)
        or latest.decision != "APPROVE_DRAFTING"
        or latest.analysis_revision != context.analysis_revision
    ):
        raise RuntimeError(
            "The current analysis revision lacks qualified-human approval"
        )
    return analysis


def submit_revised_analysis(
    context: InvestigationContext,
    candidate: RiskAssessment,
    observed_tools: set[str],
    rework_note: str,
) -> None:
    if context.review_status != "REJECT_DRAFTING":
        raise RuntimeError("A rejected review is required before rework")
    validate_risk_assessment(candidate, observed_tools, context)
    previous_revision = context.analysis_revision
    context.analysis = candidate
    context.analysis_revision = previous_revision + 1
    context.review_status = "PENDING_REREVIEW"
    context.review_history.append(
        AnalysisRevisedEvent(
            from_revision=previous_revision,
            to_revision=previous_revision + 1,
            rework_note=rework_note,
        )
    )


record_human_review(
    run_context,
    reviewer_alias="synthetic-qualified-reviewer",
    decision="REJECT_DRAFTING",
    rationale="The information gaps require revision before drafting.",
)
try:
    require_drafting_allowed(run_context)
except RuntimeError as exc:
    print("PASS (rejected review blocks drafting):", exc)
else:
    raise AssertionError("A rejected review must block drafting")

revised_assessment = assessment.model_copy(deep=True)
revised_assessment.information_gaps.append(
    "The draft must state that source-of-funds records remain unverified."
)
submit_revised_analysis(
    run_context,
    revised_assessment,
    tool_calls,
    rework_note="Added the reviewer's unresolved source-of-funds limitation.",
)
record_human_review(
    run_context,
    reviewer_alias="synthetic-qualified-reviewer",
    decision="APPROVE_DRAFTING",
    rationale="Re-reviewed revision 2 and approved draft preparation only.",
)
require_drafting_allowed(run_context)
print(
    json.dumps(
        [event.model_dump() for event in run_context.review_history],
        indent=2,
    )
)
```

## 9. Define the drafting agent only after approval

The notebook defines the drafting agent after the application gate. The agent can read the current approved analysis and source evidence. It has no tool for approval, state changes, or filing. Running it is optional and adds one paid inference call. Set `RUN_DRAFTING_DEMO=true` before starting Jupyter. Evidence-tool exceptions propagate instead of becoming model-visible error outputs. Before storing a draft, application code verifies from the raw run-item payloads that every required evidence call produced an output, then checks the current case ID, evidence IDs, and disclaimer. Local negative tests cover a missing tool output and a mismatched case without making a model call. A qualified reviewer must still confirm that each narrative claim has support.


```python
@function_tool(failure_error_function=None)
def get_reviewed_analysis(
    wrapper: RunContextWrapper[InvestigationContext],
    case_id: str,
) -> str:
    """Return the current analysis only after explicit human approval."""

    require_known_case(wrapper, case_id)
    return require_drafting_allowed(wrapper.context).model_dump_json()


sar_drafting_agent = Agent[InvestigationContext](
    name="Synthetic SAR Draft Preparation Agent",
    model=MODEL_ID,
    model_settings=MODEL_SETTINGS,
    output_type=SarDraft,
    tools=[
        get_case_profile,
        list_case_transactions,
        get_reviewed_analysis,
    ],
    instructions=(
        "Prepare a synthetic draft for qualified human review only. Call all "
        "three tools. Use neutral chronological language and cite supplied "
        "transaction IDs and copy the supplied case ID exactly. Never submit "
        "or file anything. The disclaimer must "
        "say this is an AI-generated draft requiring qualified human review. "
        "Return only SarDraft."
    ),
)

REQUIRED_DRAFTING_TOOLS = {
    "get_case_profile",
    "list_case_transactions",
    "get_reviewed_analysis",
}


def raw_item_string(raw_item: object, field_name: str) -> str | None:
    if isinstance(raw_item, dict):
        value = raw_item.get(field_name)
    else:
        value = getattr(raw_item, field_name, None)
    return value if isinstance(value, str) else None


def raw_call_id(raw_item: object) -> str | None:
    return raw_item_string(raw_item, "call_id") or raw_item_string(
        raw_item, "id"
    )


def completed_function_tools(items: list[object]) -> set[str]:
    tool_names_by_call_id: dict[str, str] = {}
    completed_call_ids: set[str] = set()
    for item in items:
        if isinstance(item, ToolCallItem):
            call_id = raw_call_id(item.raw_item)
            tool_name = raw_item_string(item.raw_item, "name")
            if call_id is not None and tool_name is not None:
                tool_names_by_call_id[call_id] = tool_name
        elif isinstance(item, ToolCallOutputItem):
            call_id = raw_call_id(item.raw_item)
            if call_id is not None:
                completed_call_ids.add(call_id)
    return {
        tool_name
        for call_id, tool_name in tool_names_by_call_id.items()
        if call_id in completed_call_ids
    }


simulated_run_items: list[object] = [
    ToolCallItem(
        agent=sar_drafting_agent,
        raw_item={
            "type": "function_call",
            "call_id": "synthetic-call-001",
            "name": "get_reviewed_analysis",
            "arguments": "{}",
        },
    ),
    ToolCallOutputItem(
        agent=sar_drafting_agent,
        raw_item={
            "type": "function_call_output",
            "call_id": "synthetic-call-001",
            "output": "{}",
        },
        output="{}",
    ),
]
if completed_function_tools(simulated_run_items) != {
    "get_reviewed_analysis"
}:
    raise AssertionError("Raw run-item correlation failed")
print("PASS (raw run-item correlation)")


def validate_sar_draft(
    candidate: SarDraft,
    context: InvestigationContext,
    completed_tool_names: set[str],
) -> dict[str, bool]:
    draft_ids = {
        evidence_id
        for citation in candidate.citations
        for evidence_id in citation.evidence_ids
    }
    valid_evidence_ids = {
        transaction.id for transaction in context.case.transactions
    }
    checks = {
        "required tools completed": (
            REQUIRED_DRAFTING_TOOLS.issubset(completed_tool_names)
        ),
        "case identity": candidate.case_id == context.case.case_id,
        "valid citations": bool(draft_ids)
        and draft_ids.issubset(valid_evidence_ids),
        "human-review disclaimer": (
            "qualified human review" in candidate.disclaimer.casefold()
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("Draft validation failed: " + ", ".join(failed))
    return checks


wrong_case_draft = SarDraft(
    case_id="SYNTH-AML-OTHER",
    narrative="Synthetic local test fixture.",
    draft_status="INSUFFICIENT_INFORMATION",
    citations=[
        EvidenceCitation(
            claim="A synthetic transaction exists.",
            evidence_ids=["TXN-001"],
        )
    ],
    disclaimer="AI-generated draft requiring qualified human review.",
)
try:
    validate_sar_draft(
        wrong_case_draft, run_context, set(REQUIRED_DRAFTING_TOOLS)
    )
except ValueError as exc:
    print("PASS (wrong-case draft rejected):", exc)
else:
    raise AssertionError("A wrong-case draft must be rejected")

missing_tool_draft = wrong_case_draft.model_copy(
    update={"case_id": run_context.case.case_id}
)
try:
    validate_sar_draft(
        missing_tool_draft,
        run_context,
        REQUIRED_DRAFTING_TOOLS - {"get_reviewed_analysis"},
    )
except ValueError as exc:
    print("PASS (missing draft tool rejected):", exc)
else:
    raise AssertionError("A draft missing a required tool must be rejected")


if RUN_DRAFTING_DEMO:
    require_drafting_allowed(run_context)
    draft_run = await Runner.run(
        sar_drafting_agent,
        f"Prepare a synthetic draft for {run_context.case.case_id}.",
        context=run_context,
        max_turns=8,
        run_config=RunConfig(
            tracing_disabled=True,
            workflow_name="Synthetic SAR draft preparation",
        ),
    )
    draft = draft_run.final_output
    completed_drafting_tools = completed_function_tools(
        draft_run.new_items
    )
    draft_checks = validate_sar_draft(
        draft, run_context, completed_drafting_tools
    )
    run_context.draft = draft
    for check_name in draft_checks:
        print("PASS:", check_name)
    print(draft.model_dump_json(indent=2))
else:
    print("Optional drafting run skipped; the approved gate remains testable.")
```

## 10. What this example establishes

- With explicit opt-in, the Agents SDK runs a bounded model and tool loop through Amazon Bedrock.
- The default offline fixture makes no AWS or model call and does not prove Agents SDK orchestration.
- A typed context scopes tools and workflow state to one request and tenant.
- Pydantic makes material findings structured, but correctness comes from deterministic support checks.
- Valid IDs and supported claims are tested separately.
- Rejected work remains rejected until a revised analysis receives an explicit re-review.
- Structured fields keep drafting authority false and the filing decision undetermined.
- Drafting is downstream of application-owned approval, and filing stays out of scope.

This notebook is a learning asset, not a production AML system. Real deployments need institution-approved policy, identity and authorization, protected data handling, durable workflow and audit records, evals reviewed by domain experts, monitoring, incident response, and legal and compliance review. A separate companion document should cover AgentCore deployment and full AWS infrastructure.


## References

- [OpenAI models in Amazon Bedrock](https://developers.openai.com/api/docs/guides/amazon-bedrock)
- [OpenAI Agents SDK guide](https://developers.openai.com/api/docs/guides/agents)
- [OpenAI Agents SDK for Python](https://github.com/openai/openai-agents-python)
- [Evaluate agent workflows](https://developers.openai.com/api/docs/guides/agent-evals)
- [GPT-5.6 Sol model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
- [Amazon Bedrock GPT-5.6 Sol model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.html)
- [FinCEN Suspicious Activity Reports](https://www.fincen.gov/suspicious-activity-reports-sars)