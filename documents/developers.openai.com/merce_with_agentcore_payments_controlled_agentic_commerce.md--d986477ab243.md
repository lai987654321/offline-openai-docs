# Build an AI agent that can pay for APIs using AgentCore Payments

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

AI agents often need information from external services to complete a task. A procurement agent might check a supplier against a sanctions database, retrieve a current risk report, or use a paid search API. When those services charge for each request, the application needs clear rules for which purchases the agent can request and who approves the spending.

Agentic commerce describes workflows in which an agent can request a paid resource while application code retains authority over payment. Amazon Bedrock AgentCore Payments provides infrastructure for bounded payment sessions, and the OpenAI Agents SDK lets a model request an application-defined tool. The application checks the merchant, purpose, amount, and approval before a payment can occur.

This notebook explains that workflow through a supplier research example. It covers the AgentCore Payments flow, the x402 payment exchange, application-owned spending controls, and receipt verification. The same payment controls are first illustrated with a local simulation and then connected to AgentCore Payments on the AWS testnet.


## Why agents need access to paid services

Consider a procurement agent reviewing a fictional supplier named Northstar Components. The agent has basic supplier information, but it needs a current risk report from a paid API before it can summarize potential concerns for a human reviewer.

The application approves that data provider, defines a supplier research purpose, and sets a maximum price for the report. It also records the human approval associated with the request. When the model decides that the report is useful, it requests the `x402_fetch` tool with the supplier report URL and the approved purpose.

The merchant returns an HTTP `402 Payment Required` challenge describing its payment terms. The application checks those terms against the approved merchant, amount, network, expiry, and budget. If the request passes, the application obtains a bounded payment proof, retrieves the report, and records a receipt and audit history. The agent then prepares its answer from the report and receipt evidence returned by the tool.


## Architecture and payment authority

The system separates four responsibilities:

1. **The AI agent** identifies when a paid service could help complete the user's request and calls the application-defined tool.
2. **The application** checks the merchant, purchase purpose, amount, approval, and spending limit before recording the receipt and audit history.
3. **AgentCore Payments** generates a payment proof within the limits of an approved payment session.
4. **The paid API** checks the payment proof and returns the requested content.

The local example simulates the AgentCore Payments step. The connected AWS workflow uses AgentCore Payments to generate the bounded proof.

The application is the boundary between the model and the payment infrastructure. The model receives the resource URL and research purpose, while approval records, spending limits, payment credentials, and audit state remain outside its control.

![An agent requests a paid supplier report through application controls and AgentCore Payments](https://developers.openai.com/cookbook/assets/images/partners/AWS/controlled-agentic-commerce-overview.png)

*The application controls approval and spending, while AgentCore Payments provides a bounded payment session for the connected AWS workflow.*


## 1. Setting up the supplier research example

The example requires Python 3.11 through 3.13 and `uv`. Follow the repository-root Jupyter command in `README.md` so the notebook can load its package and display the architecture diagrams.

The first part uses a scripted model, a simulated merchant, and a synthetic payment proof. This setup lets you inspect the same request, approval, receipt, and audit sequence without configuring AWS credentials or transferring funds. The final section shows where a real Amazon Bedrock model and AgentCore Payments testnet resources enter the workflow.

The following cell locates the example package and makes its application, merchant, and policy modules available to the notebook.


```python
import sys
from pathlib import Path

cwd = Path.cwd().resolve()
candidates = [
    cwd,
    cwd / "examples/partners/AWS/controlled_agentic_commerce_with_agentcore_payments",
    *cwd.parents,
]
ROOT = next(
    (path for path in candidates if (path / "src/agentic_commerce").is_dir()),
    None,
)
if ROOT is None:
    raise FileNotFoundError("Run this notebook from its example directory.")
sys.path.insert(0, str(ROOT / "src"))

print(f"Example root: {ROOT}")
```

## 2. Defining supplier requests and spending limits

The application needs to establish its payment rules before the model can request a tool. In this example, the supplier report costs 0.25 synthetic USDC. The application also defines the approved merchant, the permitted research purpose, a maximum amount for this purchase, and the total budget available to the agent run.

`ApprovalGrant` ties the purchase to a particular request ID and resource URL. Its expiry limits how long that authorization remains valid. The model never supplies or changes these values; they are provided by application code when the tool is created.


```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from agentic_commerce.demo import build_demo
from agentic_commerce.merchant import RESOURCE_URL
from agentic_commerce.models import ApprovalGrant

now = datetime.now(UTC)
application, merchant, local_payments = build_demo(now)
approval = ApprovalGrant(
    approval_id="approval-cookbook-001",
    request_id="request-cookbook-001",
    resource_url=RESOURCE_URL,
    purpose="supplier_due_diligence",
    maximum_amount=Decimal("0.25"),
    approved_by="synthetic-cookbook-reviewer",
    approved_at=now,
    expires_at=now + timedelta(minutes=10),
)

{
    "approved_merchant": str(RESOURCE_URL),
    "purpose": approval.purpose,
    "approved_amount": str(approval.maximum_amount),
    "run_budget": str(application.policy.policy.per_run_limit),
    "currency": approval.currency,
    "approval_expires_at": approval.expires_at.isoformat(),
}
```

## 3. Defining an agent tool for approved purchases

The `x402_fetch` function is the only payment-related tool available to the agent. The model can provide a resource URL and a business purpose, but the application supplies the request ID, idempotency key, spending policy, and approval grant.

Before starting a purchase, the tool consumes a one-use capability. That check prevents a model from issuing multiple economic requests during the same agent run. `application.purchase` then validates the merchant and payment challenge before producing a receipt.

`AgentPurchaseEvidence` returns only the report and receipt fields the model needs to prepare its answer. Wallet material, payment proof headers, and the complete application audit trail are kept out of the model context.


```python
from threading import Lock

from agents import Agent, ModelSettings, function_tool
from openai.types.shared import Reasoning

from agentic_commerce.agent import PurchaseResultRecorder, SupplierResearchOutput
from agentic_commerce.errors import AgentResultInvalid
from agentic_commerce.learning_model import ScriptedCommerceLearningModel
from agentic_commerce.models import AgentPurchaseEvidence, PurchaseRequest

recorder = PurchaseResultRecorder()
model = ScriptedCommerceLearningModel()
tool_capability = {"used": False}
tool_lock = Lock()


@function_tool
def x402_fetch(resource_url: str, purpose: str) -> str:
    """Fetch one paid resource using application-owned approval."""

    with tool_lock:
        if tool_capability["used"]:
            raise AgentResultInvalid(
                "access_count_invalid",
                "The economic tool permits exactly one invocation.",
            )
        tool_capability["used"] = True

    purchase = application.purchase(
        PurchaseRequest(
            request_id="request-cookbook-001",
            resource_url=resource_url,
            purpose=purpose,
            idempotency_key="purchase-cookbook-001",
        ),
        approval=approval,
    )
    recorder.record(purchase)
    return AgentPurchaseEvidence(
        status=purchase.status,
        report=purchase.report,
        receipt_id=purchase.receipt.receipt_id,
        amount=purchase.receipt.amount,
        currency=purchase.receipt.currency,
        requires_human_approval=purchase.authorization.requires_human_approval,
    ).model_dump_json()


agent = Agent(
    name="Supplier research agent",
    model=model,
    model_settings=ModelSettings(reasoning=Reasoning(effort="low"), store=False),
    output_type=SupplierResearchOutput,
    tools=[x402_fetch],
    instructions=(
        "Call x402_fetch exactly once for the approved supplier report. "
        "Return only the typed summary supported by its receipt."
    ),
)

{"agent": agent.name, "tools": [tool.name for tool in agent.tools]}
```

## 4. Running the x402 payment workflow

x402 uses the HTTP `402 Payment Required` response to communicate the terms of a paid request. When the application first requests the supplier report, the merchant returns a challenge with the amount, asset, network, recipient, and expiry.

The application checks those terms against its approved policy. If the merchant, price, request purpose, and human approval are valid, AgentCore Payments creates one bounded proof in the connected AWS workflow. The local example uses a synthetic proof to demonstrate the same sequence. The application retries the request with the proof, and the merchant returns the supplier report with HTTP `200`.

![The x402 request sequence between the agent, application, merchant, and AgentCore Payments](https://developers.openai.com/cookbook/assets/images/partners/AWS/controlled-agentic-commerce-x402-sequence.png)

*The merchant's 402 response supplies payment terms. Application approval occurs before a payment proof is requested.*

`Runner.run` executes the Agents SDK loop. The scripted model requests `x402_fetch` on its first turn and prepares a typed supplier summary after the tool returns. The application checks that summary against the purchase it actually recorded.


```python
from agents import RunConfig, Runner

from agentic_commerce.agent import (
    DEFAULT_PROMPT,
    SupplierResearchRun,
    validate_supplier_research_output,
)

result = await Runner.run(
    agent,
    DEFAULT_PROMPT,
    max_turns=4,
    run_config=RunConfig(
        tracing_disabled=True,
        workflow_name="Synthetic Agentic Commerce",
    ),
)
purchase = validate_supplier_research_output(result.final_output, recorder)
run = SupplierResearchRun(output=result.final_output, purchase=purchase)

{
    "model_turns": model.model_turns,
    "tool_calls": model.requested_tools,
    "merchant_requests": merchant.request_count,
    "synthetic_charges": local_payments.charge_count,
    "model_inference_calls": 0,
    "aws_calls": 0,
    "value_transferred": False,
}
```

### Using the Responses API directly

The OpenAI Agents SDK coordinates the tool loop in the previous example, but the payment workflow does not require that orchestration layer. The Responses API can expose `x402_fetch` as a function, return the model's proposed arguments, and accept a `function_call_output` after the application handles the purchase.

The application still checks the merchant, purpose, approval, and spending limit before making a payment. AgentCore Payments remains responsible for generating the bounded proof in the connected AWS workflow. The example below uses the same simulated merchant and payment processor as the local walkthrough.

This alternative calls a real Bedrock-hosted GPT-5.6 Sol model, so it runs only when `ALLOW_PAID_INFERENCE=1` and valid AWS credentials are configured. It does not enable a live payment or transfer funds.


```python
import json
import os

from openai import OpenAI
from openai.providers import bedrock

responses_tool = {
    "type": "function",
    "name": "x402_fetch",
    "description": "Fetch one approved supplier report.",
    "parameters": {
        "type": "object",
        "properties": {
            "resource_url": {"type": "string"},
            "purpose": {"type": "string"},
        },
        "required": ["resource_url", "purpose"],
        "additionalProperties": False,
    },
    "strict": True,
}
responses_result = {
    "result": "SKIPPED",
    "reason": "Set ALLOW_PAID_INFERENCE=1 to call the Bedrock model.",
    "model_calls": 0,
    "live_payment_calls": 0,
}

if os.environ.get("ALLOW_PAID_INFERENCE") == "1":
    responses_client = OpenAI(
        provider=bedrock(
            region=os.environ.get("AWS_REGION", "us-east-2"),
            profile=os.environ.get("BEDROCK_AWS_PROFILE") or None,
            api_key=None,
        )
    )
    prompt = (
        f"Call x402_fetch for {RESOURCE_URL} with purpose "
        "supplier_due_diligence. After the tool returns, provide JSON "
        "containing supplier, receipt_id, amount, and currency."
    )
    first_response = responses_client.responses.create(
        model="openai.gpt-5.6-sol",
        input=prompt,
        tools=[responses_tool],
        tool_choice={"type": "function", "name": "x402_fetch"},
        parallel_tool_calls=False,
        reasoning={"effort": "low"},
        max_output_tokens=128,
        store=False,
    )
    requested_tools = [
        item for item in first_response.output if item.type == "function_call"
    ]
    if len(requested_tools) != 1 or requested_tools[0].name != "x402_fetch":
        raise AgentResultInvalid(
            "access_count_invalid", "Expected exactly one x402_fetch request."
        )

    arguments = json.loads(requested_tools[0].arguments)
    responses_now = datetime.now(UTC)
    responses_application, responses_merchant, responses_payments = build_demo(
        responses_now
    )
    responses_request_id = "request-responses-cookbook-001"
    responses_approval = approval.model_copy(
        update={
            "approval_id": "approval-responses-cookbook-001",
            "request_id": responses_request_id,
            "approved_at": responses_now,
            "expires_at": responses_now + timedelta(minutes=10),
        }
    )
    responses_purchase = responses_application.purchase(
        PurchaseRequest(
            request_id=responses_request_id,
            resource_url=arguments["resource_url"],
            purpose=arguments["purpose"],
            idempotency_key="purchase-responses-cookbook-001",
        ),
        approval=responses_approval,
    )
    responses_evidence = AgentPurchaseEvidence(
        status=responses_purchase.status,
        report=responses_purchase.report,
        receipt_id=responses_purchase.receipt.receipt_id,
        amount=responses_purchase.receipt.amount,
        currency=responses_purchase.receipt.currency,
        requires_human_approval=(
            responses_purchase.authorization.requires_human_approval
        ),
    )
    response_input = [
        {"role": "user", "content": prompt},
        *(
            item.model_dump(mode="json", exclude_none=True)
            for item in first_response.output
        ),
        {
            "type": "function_call_output",
            "call_id": requested_tools[0].call_id,
            "output": responses_evidence.model_dump_json(),
        },
    ]
    final_response = responses_client.responses.create(
        model="openai.gpt-5.6-sol",
        input=response_input,
        tools=[responses_tool],
        tool_choice="none",
        parallel_tool_calls=False,
        reasoning={"effort": "low"},
        max_output_tokens=256,
        store=False,
    )
    final_output = json.loads(final_response.output_text)
    expected_output = {
        "supplier": responses_purchase.report.supplier,
        "receipt_id": responses_purchase.receipt.receipt_id,
        "amount": str(responses_purchase.receipt.amount),
        "currency": responses_purchase.receipt.currency,
    }
    if any(final_output.get(key) != value for key, value in expected_output.items()):
        raise AgentResultInvalid(
            "agent_output_mismatch", "The model response did not match its receipt."
        )
    responses_result = {
        "result": "PASSED",
        "responses_api_calls": 2,
        "tool_calls": [requested_tools[0].name],
        "merchant_requests": responses_merchant.request_count,
        "synthetic_charges": responses_payments.charge_count,
        "receipt_verified": True,
        "live_payment_calls": 0,
        "value_transferred": False,
    }

responses_result
```

## 5. Verifying the supplier report, receipt, and audit history

The model returns a structured supplier summary, but a valid schema only establishes that the response has the expected shape. The application still needs to check whether the reported receipt, amount, currency, and supplier details match the completed tool request.

The first cell compares the agent's proposed result with the application-owned receipt. The second cell shows the audit sequence from the initial resource request through authorization, payment proof creation, the merchant retry, and returned content.


```python
proposal = run.output.model_dump(mode="json")
receipt = run.purchase.receipt.model_dump(mode="json")

{
    "typed_agent_proposal": proposal,
    "application_receipt": {
        "receipt_id": receipt["receipt_id"],
        "amount": receipt["amount"],
        "currency": receipt["currency"],
        "network": receipt["network"],
        "reused": receipt["reused"],
    },
}
```

```python
[
    {
        "sequence": event.sequence,
        "event_type": event.event_type.value,
    }
    for event in run.purchase.audit_events
]
```

## 6. Checking rejected purchases and fabricated receipts

A useful payment example should show what happens when its controls reject a request. The first check submits another supplier report request without the required human approval. The application can inspect the merchant's challenge, but it must reject the purchase before creating another payment proof or charge.

The existing synthetic charge count should remain unchanged after the request is denied.


```python
from agentic_commerce.errors import PolicyDenied

blocked_request = PurchaseRequest(
    request_id="request-cookbook-002",
    resource_url=RESOURCE_URL,
    purpose="supplier_due_diligence",
    idempotency_key="purchase-cookbook-002",
)

try:
    application.purchase(blocked_request, approval=None)
except PolicyDenied as exc:
    blocked_result = {
        "status": "DENIED",
        "reason": exc.code,
        "synthetic_charges": local_payments.charge_count,
    }
else:
    raise AssertionError("Unapproved purchase unexpectedly succeeded")

blocked_result
```

The second check changes the receipt identifier in an otherwise valid supplier summary. The output validator compares that response with the purchase observed by the application and rejects the mismatch.

These two checks cover separate boundaries: authorization before payment and evidence verification after the model responds.


```python
from agentic_commerce.agent import (
    PurchaseResultRecorder,
    validate_supplier_research_output,
)

fabricated = run.output.model_copy(update={"receipt_id": "receipt-fabricated"})
try:
    validate_supplier_research_output(
        fabricated,
        PurchaseResultRecorder(results=[run.purchase]),
    )
except AgentResultInvalid as exc:
    negative_result = {"status": "REJECTED", "code": exc.code}
else:
    raise AssertionError("Fabricated output unexpectedly passed validation")

negative_result
```

## 7. Connecting AgentCore Payments to the AWS testnet

The connected supplier research workflow uses a Bedrock-hosted OpenAI model, AgentCore Payments, and an approved x402 merchant on Base Sepolia. The application keeps the same merchant policy, spending approval, request identity, and receipt checks demonstrated in the local simulation. AgentCore Payments creates a short-lived session with its own maximum spending limit.

![Local supplier research and an AWS testnet request share the same application approval and spending controls](https://developers.openai.com/cookbook/assets/images/partners/AWS/controlled-agentic-commerce-local-and-testnet.png)

*The local simulation and AWS testnet workflow share the same application controls. AgentCore Payments provides bounded payment sessions in the connected environment.*

Before enabling the AWS path, an operator provisions the payment manager, connector, instrument, and exact-wallet signing permission outside the notebook. Model inference, session administration, and payment execution use separate responsibilities. `README.md` describes the setup, supported configuration, below-budget denial check, and cleanup procedure.

AgentCore Runtime is not used by this notebook. The notebook process remains the application runtime, and all live payment gates are disabled unless an operator explicitly enables them.


### Checking testnet readiness before network calls

The readiness check inspects local configuration without contacting AWS, the model, the merchant, or the wallet. It confirms that the required payment opt-ins are present, AWS roles are separated, the session budget is finite, and no payment session is recorded in the local state file.

The check also rejects proxy settings that are incompatible with the merchant connection's DNS and TLS protections. With the default configuration, the expected result is `NOT_READY` because live payment gates are disabled.


```python
from agentic_commerce.agentcore_e2e import (
    readiness_report,
    run_managed_e2e,
)

agentcore_readiness = readiness_report()
agentcore_readiness
```

### Inspecting the payment instrument and network

When `ALLOW_AGENTCORE_READ_ONLY=1` is explicitly enabled, the application can inspect the configured payment instrument without creating a payment session. The instrument must be `ACTIVE`, use the `ETHEREUM` wallet network, and report the exact `BASE_SEPOLIA` and `USDC` balance scope.

A missing gate returns `SKIPPED`. A network or asset mismatch returns `NOT_READY`. These checks do not expose a balance amount, generate a payment proof, contact the merchant, or transfer value.


```python
from agentic_commerce.agentcore_infrastructure import (
    inspect_payment_instrument,
)

agentcore_infrastructure = inspect_payment_instrument()
agentcore_infrastructure
```

### Running one approved testnet transaction

An operator can enable the managed testnet run only after checking the approved merchant, recipient, asset, amount, wallet, and short-lived session configuration. The workflow requires all five explicit gates: `RUN_AGENTCORE_E2E`, `ALLOW_AGENTCORE_SESSION_ADMIN`, `ALLOW_PAID_INFERENCE`, `ALLOW_AGENTCORE_TESTNET`, and `APPROVE_AGENTCORE_TESTNET_PURCHASE`.

The combined execution path checks those gates again before starting model inference or payment activity. It creates one bounded session, sends the agent's request through the application policy, requests an AgentCore payment proof, and retries the approved merchant once.

Session creation is serialized. If local session persistence fails, the application attempts compensating cleanup. A successful or failed managed run also attempts to delete the session in `finally`. If cleanup fails, the operator must follow the recovery procedure in `README.md` before starting another run.

With the default notebook configuration, the cell returns `SKIPPED` and performs no live operation.


```python
import json

agentcore_e2e_result = await run_managed_e2e()
if agentcore_e2e_result["result"] not in {"PASSED", "SKIPPED"}:
    print(json.dumps(agentcore_e2e_result, indent=2, sort_keys=True))
    raise RuntimeError(
        "Managed AgentCore test did not complete safely; review the "
        "sanitized report before any rerun."
    )

agentcore_e2e_result
```

### Interpreting payment and settlement evidence

The managed result records whether the model completed its tool call, AgentCore Payments produced the payment proof, the merchant returned HTTP `200`, and the temporary session was deleted. The application hashes the original HTTP response bytes and keeps provider credentials, payment headers, and internal identifiers out of the report.

Merchant acceptance establishes that the paid request completed. Independent settlement and transaction finality require separate evidence. The example therefore reports `settlement_verified=false`.


```python
if agentcore_e2e_result["result"] == "PASSED":
    assert agentcore_e2e_result["model_run_completed"] is True
    assert agentcore_e2e_result["agentcore_payment_path_completed"] is True
    assert agentcore_e2e_result["merchant_paid_retry_completed"] is True
    assert agentcore_e2e_result["status_code"] == 200
    assert agentcore_e2e_result["payment_attempts"] == 1
    assert agentcore_e2e_result["session_cleanup"] == "DELETED"
    assert agentcore_e2e_result["identifiers_logged"] is False
    assert agentcore_e2e_result["settlement_verified"] is False

{
    "result": agentcore_e2e_result["result"],
    "session_cleanup": agentcore_e2e_result.get("session_cleanup", "NOT_CREATED"),
    "settlement_verified": agentcore_e2e_result.get("settlement_verified", False),
    "interpretation": (
        "Combined testnet path completed; settlement still needs separate evidence."
        if agentcore_e2e_result["result"] == "PASSED"
        else "Live path was not enabled; no testnet transaction was attempted."
    ),
}
```

### Optional CloudWatch lifecycle evidence

This public notebook does not include a CloudWatch screenshot. For a reviewed live run, configure AgentCore Payments log delivery before the run and use CloudWatch only as sanitized lifecycle evidence. Do not share account IDs, request IDs, wallet data, payment identifiers, or proof headers.

Lifecycle events can help confirm session creation, payment processing, and session deletion. They do not independently establish the payment amount, blockchain settlement, transaction finality, or production readiness.


## Applying the payment workflow to other services

The same structure can support other paid data sources, including premium search, sanctions screening, market data, or supplier verification. Each integration should define its approved merchants, permitted purposes, maximum amount, approval requirements, and session duration before the agent can request a purchase.

The model chooses when a paid tool might help complete the user's task. Application code determines whether that request is authorized, records the resulting transaction evidence, and checks the model's final response against the actual tool result. AgentCore Payments provides an additional spending boundary when the workflow is connected to an approved AWS testnet session.


## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [Use OpenAI models through Amazon Bedrock](https://developers.openai.com/api/docs/guides/amazon-bedrock)
- [AWS announcement: Agents that transact](https://aws.amazon.com/blogs/machine-learning/agents-that-transact-introducing-amazon-bedrock-agentcore-payments-built-with-coinbase-and-stripe/)
- [How AgentCore Payments works](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-how-it-works.html)
- [AgentCore Payments prerequisites](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-prerequisites.html)
- [Create bounded payment sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-create-session.html)
- [Separate payment IAM roles](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/payments-iam-roles.html)