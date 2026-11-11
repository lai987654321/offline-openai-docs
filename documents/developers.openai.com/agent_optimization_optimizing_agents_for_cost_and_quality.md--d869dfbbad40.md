# Optimizing customer support agents for cost and quality

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

This cookbook demonstrates a repeatable optimization sprint for a tool-using agent: measure a baseline, change one part of the workflow, and check quality before accepting savings. It uses synthetic e-commerce support tickets and a deterministic simulation that runs without API spend. The same measurement loop applies to other agent workflows.

By the end, you will have a repeatable pattern for:

- Measuring quality, latency, tool use, and total cost on the same evaluation set.
- Reducing unnecessary work through prompt and tool controls, model routing, and prompt caching.
- Separating customer-facing work from offline follow-up and checking the resulting tradeoffs.

The code defaults to dry-run mode. The optional live helpers require `OPENAI_API_KEY` and `RUN_LIVE_API_CALLS=true`.


## Outline

1. Define success criteria and a small representative eval set.
2. Build the intentionally inefficient baseline support agent.
3. Measure baseline cost, tokens, quality, latency, and tool calls.
4. Apply prompt, output, tool, and context controls.
5. Route simple steps to smaller models.
6. Restructure requests for prompt caching.
7. Split real-time and follow-up work.
8. Add monitoring, evals, and guardrails.

## Use case and agent setup

Our fictional e-commerce assistant handles order status, damaged deliveries, refund eligibility, duplicate charges, and account access. Routine lookups make smaller models worth evaluating; policy-sensitive cases test whether the optimized workflow still escalates correctly.

The five mock tools represent an order system (`lookup_order`), customer records (`lookup_customer`), a policy source (`lookup_policy`), refund or replacement cases (`create_refund_case`), and human support (`escalate_to_human`). These are local Python functions, so even the live model examples cannot change a real customer account.

The baseline exposes every tool, returns oversized payloads, and uses a full model for every step. It also performs internal QA, analytics tagging, and routing audits before replying. Later rounds keep the business task constant while reducing unnecessary work and moving follow-up processing out of the customer-facing path.


## References

**Last verified: September 14, 2026.** The examples use GPT-5.4 models; the model-selection and caching sections also describe considerations for GPT-5.6.

| Reference | Details used here |
|---|---|
| [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) | Output limits, reasoning, verbosity, usage, conversation state, and service tiers |
| [Function calling](https://developers.openai.com/api/docs/guides/function-calling) | Function schemas, `allowed_tools`, and forwarding reasoning and tool-call items |
| [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | Stable prefixes, model-specific caching controls, and token accounting |
| [Compaction](https://developers.openai.com/api/docs/guides/compaction) | `context_management` and `compact_threshold` |
| [Cost optimization](https://developers.openai.com/api/docs/guides/cost-optimization) | Fewer requests, smaller token budgets, and model selection |
| [Batch API](https://developers.openai.com/api/docs/guides/batch) and [flex processing](https://developers.openai.com/api/docs/guides/flex-processing) | Offline processing, the Batch `24h` window, and flex availability tradeoffs |
| [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4), [mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), and [nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano) | Standard text-token prices and supported reasoning settings |


## Setup

Use Python 3.10 or later. Clone the Cookbook repository or download this entire [example folder](https://github.com/openai/openai-cookbook/tree/main/examples/agent_optimization), then start the notebook with `examples/agent_optimization` as the working directory so its local imports resolve.

Install the dependencies in your notebook's environment:

```bash
pip install --upgrade openai pandas matplotlib jinja2 ipykernel
```

The same dependencies are listed in [requirements.txt](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/requirements.txt). `jinja2` is required for the styled pandas tables. The supporting files contain [mock data, tools, and prompts](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/support.py), [simulation and checks](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/simulation.py), [live API helpers](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/live_api.py), [offline answer evaluation](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/evaluation.py), and [scenario scoring](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/scenarios.py).

The notebook does not call the API by default. To opt in to the live agent example, set these variables before starting the kernel:

```bash
export OPENAI_API_KEY=...
export RUN_LIVE_API_CALLS=true
```

The optional answer judge has its own switch, `RUN_LLM_JUDGE=true`, and also requires `OPENAI_API_KEY`. It grades the 50 existing simulated traces (10 tickets × 5 variants) with 50 paid judge requests; it does not run the live agent. Leave both switches unset for a fully offline run.

Run the cells from top to bottom. The Batch example writes a local file under `outputs/`; its submission code is displayed for inspection and is not executed.


```python
import json
import math
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display
from openai import OpenAI

RUN_LIVE_API_CALLS = os.environ.get("RUN_LIVE_API_CALLS", "false").lower() == "true"
RUN_LLM_JUDGE = os.environ.get("RUN_LLM_JUDGE", "false").lower() == "true"
if (RUN_LIVE_API_CALLS or RUN_LLM_JUDGE) and not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY before enabling the live agent or judge.")
client = OpenAI() if RUN_LIVE_API_CALLS else None
judge_client = OpenAI() if RUN_LLM_JUDGE else None

pd.set_option("display.max_columns", 40)
pd.set_option("display.width", 140)
print("RUN_LIVE_API_CALLS =", RUN_LIVE_API_CALLS)
print("RUN_LLM_JUDGE =", RUN_LLM_JUDGE)
```

```text
RUN_LIVE_API_CALLS = True
RUN_LLM_JUDGE = True
```

## Success criteria and constraints

Accept savings only when the agent still uses the right facts, follows policy, takes the required action, and escalates correctly. A concise response must give the customer the next step without exposing internal data. Compare p50/p95 latency and total cost after those quality checks pass.

The eval set is deliberately small. In production, use a stratified sample covering your main intents, risk levels, languages, regions, customer tiers, and edge cases. Keep a holdout set and gate each optimization on quality before comparing savings.


## Simulation contract

The default path uses mock data and modeled metrics. It demonstrates the measurement loop; its numbers are not a production benchmark.

The harness measures serialized text lengths and compares tool, action, escalation, and response-phrase checks against the fixtures. Token counts are estimated from those lengths. Reasoning tokens, latency, cache hits, and the aggregate quality score follow illustrative formulas; cost applies the verified price table to estimated usage.

Routing and optimized actions come from the fixture labels, so this simulation does not measure a model's ability to choose them. Response checks use case-insensitive literal phrases, which can reject valid paraphrases and cannot establish factual correctness. For deployment decisions, replace these traces with real usage, timings, tool results, routing decisions, and calibrated judge or human evaluations.


## Optimization knobs

| Knob | Inefficient baseline | Optimized pattern | Primary metric |
|---|---|---|---|
| Prompt and output | Broad "be thorough" instructions and long answers | Specific task rules, concise response contract, `text.verbosity="low"`, capped output | Output tokens, concision, quality |
| Reasoning effort | High reasoning for every ticket | Low for routine work, higher only for high-risk decisions | Reasoning tokens, latency |
| Tool surface | All tools exposed for every request | Full stable tool list plus `tool_choice.allowed_tools` per task | Tool calls, cacheability |
| Tool schemas | Verbose descriptions and broad payload expectations | Small schemas with only decision-critical arguments | Input tokens |
| Tool payloads | Raw CRM, carrier, audit, and appendix blobs | Slim fields needed for the next decision | Tool output tokens |
| Model routing | One large model for all steps | Nano for triage/tags, mini for routine resolution, full model for high-risk cases | Cost, latency, escalation accuracy |
| Prompt caching | Volatile ticket data mixed into the prefix | Stable instructions, tools, policy framing, and schema first; ticket data last | Cached input tokens, cost |
| Workflow split | QA, analytics, summaries, and audits in the customer path | Customer resolution sync; QA/tags/reporting async via background, flex, or Batch | p50 latency, synchronous cost |
| Guardrails and evals | Informal spot checks | Deterministic checks plus judge schema for live traces | Regression rate, safety pass rate |


## Sample evaluation set

This small sample eval set gives the notebook concrete tickets, expected tools, expected actions, escalation labels, and forbidden claims to score each optimization round.


```python
from support import EVAL_SET

pd.DataFrame(EVAL_SET)[
    [
        "ticket_id",
        "intent",
        "risk",
        "difficulty",
        "expected_tools",
        "expected_action",
        "must_escalate",
    ]
]
```

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>ticket_id</th>
      <th>intent</th>
      <th>risk</th>
      <th>difficulty</th>
      <th>expected_tools</th>
      <th>expected_action</th>
      <th>must_escalate</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>T-001</td>
      <td>order_status</td>
      <td>low</td>
      <td>simple_lookup</td>
      <td>[lookup_order]</td>
      <td>provide_status_eta</td>
      <td>False</td>
    </tr>
    <tr>
      <th>1</th>
      <td>T-002</td>
      <td>damaged_delivery</td>
      <td>medium</td>
      <td>routine_policy</td>
      <td>[lookup_order, lookup_policy]</td>
      <td>request_photo_then_offer_replacement</td>
      <td>False</td>
    </tr>
    <tr>
      <th>2</th>
      <td>T-003</td>
      <td>refund_eligibility</td>
      <td>medium</td>
      <td>routine_policy</td>
      <td>[lookup_order, lookup_policy, create_refund_case]</td>
      <td>open_refund_case</td>
      <td>False</td>
    </tr>
    <tr>
      <th>3</th>
      <td>T-004</td>
      <td>billing_issue</td>
      <td>medium</td>
      <td>sensitive_policy</td>
      <td>[lookup_order, lookup_policy, escalate_to_human]</td>
      <td>escalate_billing_review</td>
      <td>True</td>
    </tr>
    <tr>
      <th>4</th>
      <td>T-005</td>
      <td>account_access</td>
      <td>high</td>
      <td>account_security</td>
      <td>[lookup_customer, lookup_policy, escalate_to_h...</td>
      <td>escalate_account_security</td>
      <td>True</td>
    </tr>
    <tr>
      <th>5</th>
      <td>T-006</td>
      <td>refund_dispute</td>
      <td>high</td>
      <td>outside_policy_window</td>
      <td>[lookup_order, lookup_policy, escalate_to_human]</td>
      <td>escalate_refund_review</td>
      <td>True</td>
    </tr>
    <tr>
      <th>6</th>
      <td>T-007</td>
      <td>delivered_not_received</td>
      <td>medium</td>
      <td>routine_policy</td>
      <td>[lookup_order, lookup_policy]</td>
      <td>start_delivery_trace_steps</td>
      <td>False</td>
    </tr>
    <tr>
      <th>7</th>
      <td>T-008</td>
      <td>high_value_damage</td>
      <td>high</td>
      <td>high_value_policy</td>
      <td>[lookup_order, lookup_policy, escalate_to_human]</td>
      <td>escalate_high_value_damage</td>
      <td>True</td>
    </tr>
    <tr>
      <th>8</th>
      <td>T-009</td>
      <td>refund_eligibility</td>
      <td>low</td>
      <td>routine_policy</td>
      <td>[lookup_order, lookup_policy, create_refund_case]</td>
      <td>open_refund_case</td>
      <td>False</td>
    </tr>
    <tr>
      <th>9</th>
      <td>T-010</td>
      <td>account_access</td>
      <td>high</td>
      <td>account_security</td>
      <td>[lookup_customer, lookup_policy, escalate_to_h...</td>
      <td>escalate_account_security</td>
      <td>True</td>
    </tr>
  </tbody>
</table>
</div>

## Support data and tools

The five local tool functions in [support.py](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/support.py) stand in for internal systems. The baseline returns oversized payloads to show how tool outputs can dominate input tokens; later rounds return only fields needed for the decision and response.

The following cell shows one slim order record. The mock action tools return synthetic results without creating real cases or escalations.


```python
from support import lookup_order

# Inspect the decision-critical fields returned by the slim payload.
print(json.dumps(lookup_order("O-1001", payload="slim"), indent=2))
```

```text
{
  "found": true,
  "order_id": "O-1001",
  "status": "in_transit",
  "carrier": "UPS",
  "eta": "tomorrow",
  "delivered_days_ago": null,
  "payment_status": "paid_once",
  "item_value": 18.0,
  "events": [
    "regional_delay"
  ]
}
```

```python
from support import SLIM_TOOLS, VERBOSE_TOOLS, allowed_tool_choice

print("Verbose tool schema tokens:", math.ceil(len(json.dumps(VERBOSE_TOOLS)) / 4))
print("Slim tool schema tokens:", math.ceil(len(json.dumps(SLIM_TOOLS)) / 4))
```

```text
Verbose tool schema tokens: 550
Slim tool schema tokens: 397
```

## Baseline architecture

The bad baseline does too much in one synchronous path.

```mermaid
flowchart LR
    A["Customer message"] --> B["One general agent on strongest model"]
    B --> C["Customer lookup"]
    B --> D["Order lookup"]
    B --> E["Policy lookup"]
    B --> F["Refund or escalation tools"]
    B --> G["Customer response"]
    B --> H["QA summary"]
    B --> I["Analytics tagging"]
    B --> J["Routing audit"]
```

Broad instructions, high reasoning effort, and unrestricted tools make each request expensive. Large schemas and verbose payloads inflate inputs, while long answers and synchronous QA add work before the customer receives a reply.


```python
from support import CONTROLLED_PROMPT

print(CONTROLLED_PROMPT)
```

```text
Role: E-commerce support assistant.

Goal: Resolve routine support tickets with the fewest necessary tool calls while preserving policy correctness.

Tool rules:
- Use only tools required for the current decision.
- Order status: order lookup only.
- Damaged delivery or refund: order lookup plus the relevant policy.
- Billing duplicate charge: order lookup plus billing policy, then escalate.
- Account access with unverified identity: customer lookup plus account policy, then escalate.

Response rules:
- Give the customer the outcome and next step.
- Do not expose internal reasoning, raw tool data, audit notes, or policy text.
- Keep the customer-facing answer under 120 words unless escalation legally requires more detail.
```

## Metrics helpers

The live helper reads `input_tokens`, `output_tokens`, `total_tokens`, `input_tokens_details.cached_tokens`, and `output_tokens_details.reasoning_tokens`. Output-token usage already includes reasoning tokens; do not add them again when calculating cost.

The table below shows USD per million text tokens at standard rates, verified September 14, 2026 against the [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4), [mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), and [nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano) pages. It covers the short GPT-5.4 requests used here. The estimator does not cover long-context premiums, priority pricing, or GPT-5.6 cache-write charges; update it before changing those settings. See the [pricing page](https://developers.openai.com/api/docs/pricing) for current rates.


```python
from simulation import MODEL_PRICES_USD_PER_1M

pd.DataFrame(MODEL_PRICES_USD_PER_1M).T.rename_axis("model")
```

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>input</th>
      <th>cached_input</th>
      <th>output</th>
    </tr>
    <tr>
      <th>model</th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>gpt-5.4</th>
      <td>2.50</td>
      <td>0.250</td>
      <td>15.00</td>
    </tr>
    <tr>
      <th>gpt-5.4-mini</th>
      <td>0.75</td>
      <td>0.075</td>
      <td>4.50</td>
    </tr>
    <tr>
      <th>gpt-5.4-nano</th>
      <td>0.20</td>
      <td>0.020</td>
      <td>1.25</td>
    </tr>
  </tbody>
</table>
</div>

## Dry-run simulation

The [simulation helper](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/simulation.py) applies each variant to the same tickets, estimates usage from prompts and payloads, and records the customer response with its quality checks. Missing required phrases and forbidden claims lower quality and fail the demo policy check, even when action and escalation labels match.

The optimized variants assume a correct application router and known expected actions. Caching uses a simplified warm-cache assumption and a 1,024-token eligibility threshold, not a measurement of actual cache behavior. The repeated playbook makes the demonstration large enough to exercise that branch; production prompts should contain useful shared context, and cache eligibility depends on request settings.

The final variant removes background work from synchronous latency while still counting its tokens and Batch cost. Inspect individual traces before relying on their averages.


```python
from simulation import CACHE_FRIENDLY_PROMPT, VARIANT_ORDER, simulate_trace

traces = pd.DataFrame(
    simulate_trace(ticket, variant)
    for variant in VARIANT_ORDER
    for ticket in EVAL_SET
)
traces.drop(columns="tool_results").head()
```

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>variant</th>
      <th>variant_label</th>
      <th>ticket_id</th>
      <th>intent</th>
      <th>risk</th>
      <th>difficulty</th>
      <th>model</th>
      <th>routing_tokens</th>
      <th>tool_calls</th>
      <th>expected_tools</th>
      <th>tools</th>
      <th>action</th>
      <th>expected_action</th>
      <th>input_tokens</th>
      <th>latency_input_tokens</th>
      <th>cacheable_prefix_tokens</th>
      <th>cached_tokens</th>
      <th>output_tokens</th>
      <th>visible_output_tokens</th>
      <th>reasoning_tokens</th>
      <th>...</th>
      <th>total_tokens</th>
      <th>latency_s</th>
      <th>sync_cost_usd</th>
      <th>background_tokens</th>
      <th>background_cost_usd</th>
      <th>cost_usd</th>
      <th>escalated</th>
      <th>customer_response</th>
      <th>missing_required_tools</th>
      <th>extra_tool_calls</th>
      <th>unnecessary_tools</th>
      <th>escalation_correct</th>
      <th>action_correct</th>
      <th>policy_compliant</th>
      <th>concise</th>
      <th>response_complete</th>
      <th>missing_required_phrases</th>
      <th>forbidden_claims_absent</th>
      <th>forbidden_claims_found</th>
      <th>quality_score</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>00_bad_baseline</td>
      <td>Bad baseline</td>
      <td>T-001</td>
      <td>order_status</td>
      <td>low</td>
      <td>simple_lookup</td>
      <td>gpt-5.4</td>
      <td>0</td>
      <td>5</td>
      <td>lookup_order</td>
      <td>lookup_customer, lookup_order, lookup_policy, ...</td>
      <td>provide_status_eta</td>
      <td>provide_status_eta</td>
      <td>12301</td>
      <td>12301</td>
      <td>0</td>
      <td>0</td>
      <td>612</td>
      <td>167</td>
      <td>445</td>
      <td>...</td>
      <td>12913</td>
      <td>4.88</td>
      <td>0.039933</td>
      <td>0</td>
      <td>0.0</td>
      <td>0.039933</td>
      <td>False</td>
      <td>I reviewed your message for ticket T-001 and c...</td>
      <td></td>
      <td>4</td>
      <td>create_refund_case, escalate_to_human, lookup_...</td>
      <td>True</td>
      <td>True</td>
      <td>False</td>
      <td>False</td>
      <td>False</td>
      <td>in transit, tomorrow</td>
      <td>True</td>
      <td></td>
      <td>0.55</td>
    </tr>
    <tr>
      <th>1</th>
      <td>00_bad_baseline</td>
      <td>Bad baseline</td>
      <td>T-002</td>
      <td>damaged_delivery</td>
      <td>medium</td>
      <td>routine_policy</td>
      <td>gpt-5.4</td>
      <td>0</td>
      <td>5</td>
      <td>lookup_order, lookup_policy</td>
      <td>lookup_customer, lookup_order, lookup_policy, ...</td>
      <td>open_replacement_without_photo</td>
      <td>request_photo_then_offer_replacement</td>
      <td>12273</td>
      <td>12273</td>
      <td>0</td>
      <td>0</td>
      <td>644</td>
      <td>174</td>
      <td>470</td>
      <td>...</td>
      <td>12917</td>
      <td>4.88</td>
      <td>0.040343</td>
      <td>0</td>
      <td>0.0</td>
      <td>0.040343</td>
      <td>False</td>
      <td>I reviewed your message for ticket T-002 and c...</td>
      <td></td>
      <td>3</td>
      <td>create_refund_case, escalate_to_human, lookup_...</td>
      <td>True</td>
      <td>False</td>
      <td>False</td>
      <td>False</td>
      <td>True</td>
      <td></td>
      <td>True</td>
      <td></td>
      <td>0.65</td>
    </tr>
    <tr>
      <th>2</th>
      <td>00_bad_baseline</td>
      <td>Bad baseline</td>
      <td>T-003</td>
      <td>refund_eligibility</td>
      <td>medium</td>
      <td>routine_policy</td>
      <td>gpt-5.4</td>
      <td>0</td>
      <td>5</td>
      <td>lookup_order, lookup_policy, create_refund_case</td>
      <td>lookup_customer, lookup_order, lookup_policy, ...</td>
      <td>escalate_refund_review</td>
      <td>open_refund_case</td>
      <td>12178</td>
      <td>12178</td>
      <td>0</td>
      <td>0</td>
      <td>640</td>
      <td>170</td>
      <td>470</td>
      <td>...</td>
      <td>12818</td>
      <td>4.87</td>
      <td>0.040045</td>
      <td>0</td>
      <td>0.0</td>
      <td>0.040045</td>
      <td>True</td>
      <td>I reviewed your message for ticket T-003 and c...</td>
      <td></td>
      <td>2</td>
      <td>escalate_to_human, lookup_customer</td>
      <td>False</td>
      <td>False</td>
      <td>False</td>
      <td>False</td>
      <td>False</td>
      <td>refund case, within 30 days</td>
      <td>True</td>
      <td></td>
      <td>0.22</td>
    </tr>
    <tr>
      <th>3</th>
      <td>00_bad_baseline</td>
      <td>Bad baseline</td>
      <td>T-004</td>
      <td>billing_issue</td>
      <td>medium</td>
      <td>sensitive_policy</td>
      <td>gpt-5.4</td>
      <td>0</td>
      <td>5</td>
      <td>lookup_order, lookup_policy, escalate_to_human</td>
      <td>lookup_customer, lookup_order, lookup_policy, ...</td>
      <td>escalate_billing_review</td>
      <td>escalate_billing_review</td>
      <td>12166</td>
      <td>12166</td>
      <td>0</td>
      <td>0</td>
      <td>664</td>
      <td>169</td>
      <td>495</td>
      <td>...</td>
      <td>12830</td>
      <td>4.87</td>
      <td>0.040375</td>
      <td>0</td>
      <td>0.0</td>
      <td>0.040375</td>
      <td>True</td>
      <td>I reviewed your message for ticket T-004 and c...</td>
      <td></td>
      <td>2</td>
      <td>create_refund_case, lookup_customer</td>
      <td>True</td>
      <td>True</td>
      <td>True</td>
      <td>False</td>
      <td>True</td>
      <td></td>
      <td>True</td>
      <td></td>
      <td>0.85</td>
    </tr>
    <tr>
      <th>4</th>
      <td>00_bad_baseline</td>
      <td>Bad baseline</td>
      <td>T-005</td>
      <td>account_access</td>
      <td>high</td>
      <td>account_security</td>
      <td>gpt-5.4</td>
      <td>0</td>
      <td>5</td>
      <td>lookup_customer, lookup_policy, escalate_to_human</td>
      <td>lookup_customer, lookup_order, lookup_policy, ...</td>
      <td>escalate_account_security</td>
      <td>escalate_account_security</td>
      <td>7415</td>
      <td>7415</td>
      <td>0</td>
      <td>0</td>
      <td>697</td>
      <td>172</td>
      <td>525</td>
      <td>...</td>
      <td>8112</td>
      <td>3.97</td>
      <td>0.028993</td>
      <td>0</td>
      <td>0.0</td>
      <td>0.028993</td>
      <td>True</td>
      <td>I reviewed your message for ticket T-005 and c...</td>
      <td></td>
      <td>2</td>
      <td>create_refund_case, lookup_order</td>
      <td>True</td>
      <td>True</td>
      <td>False</td>
      <td>False</td>
      <td>False</td>
      <td>account security, verification</td>
      <td>True</td>
      <td></td>
      <td>0.60</td>
    </tr>
  </tbody>
</table>
<p>5 rows × 41 columns</p>
</div>

```python
summary = (
    traces.groupby(["variant", "variant_label"], sort=False)
    .agg(
        tickets=("ticket_id", "count"),
        mean_quality=("quality_score", "mean"),
        policy_compliance=("policy_compliant", "mean"),
        action_accuracy=("action_correct", "mean"),
        escalation_accuracy=("escalation_correct", "mean"),
        concise_rate=("concise", "mean"),
        mean_tool_calls=("tool_calls", "mean"),
        mean_extra_tool_calls=("extra_tool_calls", "mean"),
        mean_input_tokens=("input_tokens", "mean"),
        mean_cached_tokens=("cached_tokens", "mean"),
        mean_output_tokens=("output_tokens", "mean"),
        mean_reasoning_tokens=("reasoning_tokens", "mean"),
        mean_sync_tokens=("sync_tokens", "mean"),
        mean_total_tokens=("total_tokens", "mean"),
        p50_latency_s=("latency_s", "median"),
        p95_latency_s=("latency_s", lambda s: s.quantile(0.95)),
        sync_cost_per_ticket_usd=("sync_cost_usd", "mean"),
        background_cost_per_ticket_usd=("background_cost_usd", "mean"),
        cost_per_ticket_usd=("cost_usd", "mean"),
    )
    .reset_index()
)

baseline_cost = summary.loc[summary["variant"] == "00_bad_baseline", "cost_per_ticket_usd"].iloc[0]
baseline_tokens = summary.loc[summary["variant"] == "00_bad_baseline", "mean_total_tokens"].iloc[0]
baseline_latency = summary.loc[summary["variant"] == "00_bad_baseline", "p50_latency_s"].iloc[0]

summary["cost_reduction_vs_baseline"] = 1 - summary["cost_per_ticket_usd"] / baseline_cost
summary["token_reduction_vs_baseline"] = 1 - summary["mean_total_tokens"] / baseline_tokens
summary["latency_reduction_vs_baseline"] = 1 - summary["p50_latency_s"] / baseline_latency
summary["monthly_cost_at_100k_tickets"] = summary["cost_per_ticket_usd"] * 100_000

summary_view = summary[
    [
        "variant_label",
        "mean_quality",
        "policy_compliance",
        "action_accuracy",
        "escalation_accuracy",
        "mean_tool_calls",
        "mean_extra_tool_calls",
        "mean_sync_tokens",
        "mean_total_tokens",
        "mean_cached_tokens",
        "p50_latency_s",
        "cost_per_ticket_usd",
        "cost_reduction_vs_baseline",
        "monthly_cost_at_100k_tickets",
    ]
]

display(
    summary_view.style.format(
        {
            "mean_quality": "{:.2f}",
            "policy_compliance": "{:.0%}",
            "action_accuracy": "{:.0%}",
            "escalation_accuracy": "{:.0%}",
            "mean_tool_calls": "{:.1f}",
            "mean_extra_tool_calls": "{:.1f}",
            "mean_sync_tokens": "{:,.0f}",
            "mean_total_tokens": "{:,.0f}",
            "mean_cached_tokens": "{:,.0f}",
            "p50_latency_s": "{:.2f}",
            "cost_per_ticket_usd": "${:.5f}",
            "cost_reduction_vs_baseline": "{:.0%}",
            "monthly_cost_at_100k_tickets": "${:,.0f}",
        }
    )
)
```

<table id="T_01f0b">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_01f0b_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_01f0b_level0_col1" class="col_heading level0 col1">mean_quality</th>
      <th id="T_01f0b_level0_col2" class="col_heading level0 col2">policy_compliance</th>
      <th id="T_01f0b_level0_col3" class="col_heading level0 col3">action_accuracy</th>
      <th id="T_01f0b_level0_col4" class="col_heading level0 col4">escalation_accuracy</th>
      <th id="T_01f0b_level0_col5" class="col_heading level0 col5">mean_tool_calls</th>
      <th id="T_01f0b_level0_col6" class="col_heading level0 col6">mean_extra_tool_calls</th>
      <th id="T_01f0b_level0_col7" class="col_heading level0 col7">mean_sync_tokens</th>
      <th id="T_01f0b_level0_col8" class="col_heading level0 col8">mean_total_tokens</th>
      <th id="T_01f0b_level0_col9" class="col_heading level0 col9">mean_cached_tokens</th>
      <th id="T_01f0b_level0_col10" class="col_heading level0 col10">p50_latency_s</th>
      <th id="T_01f0b_level0_col11" class="col_heading level0 col11">cost_per_ticket_usd</th>
      <th id="T_01f0b_level0_col12" class="col_heading level0 col12">cost_reduction_vs_baseline</th>
      <th id="T_01f0b_level0_col13" class="col_heading level0 col13">monthly_cost_at_100k_tickets</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_01f0b_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_01f0b_row0_col0" class="data row0 col0">Bad baseline</td>
      <td id="T_01f0b_row0_col1" class="data row0 col1">0.51</td>
      <td id="T_01f0b_row0_col2" class="data row0 col2">10%</td>
      <td id="T_01f0b_row0_col3" class="data row0 col3">60%</td>
      <td id="T_01f0b_row0_col4" class="data row0 col4">70%</td>
      <td id="T_01f0b_row0_col5" class="data row0 col5">5.0</td>
      <td id="T_01f0b_row0_col6" class="data row0 col6">2.4</td>
      <td id="T_01f0b_row0_col7" class="data row0 col7">11,935</td>
      <td id="T_01f0b_row0_col8" class="data row0 col8">11,935</td>
      <td id="T_01f0b_row0_col9" class="data row0 col9">0</td>
      <td id="T_01f0b_row0_col10" class="data row0 col10">4.88</td>
      <td id="T_01f0b_row0_col11" class="data row0 col11">$0.03813</td>
      <td id="T_01f0b_row0_col12" class="data row0 col12">0%</td>
      <td id="T_01f0b_row0_col13" class="data row0 col13">$3,813</td>
    </tr>
    <tr>
      <th id="T_01f0b_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_01f0b_row1_col0" class="data row1 col0">Round 1: controls</td>
      <td id="T_01f0b_row1_col1" class="data row1 col1">0.98</td>
      <td id="T_01f0b_row1_col2" class="data row1 col2">100%</td>
      <td id="T_01f0b_row1_col3" class="data row1 col3">100%</td>
      <td id="T_01f0b_row1_col4" class="data row1 col4">100%</td>
      <td id="T_01f0b_row1_col5" class="data row1 col5">2.6</td>
      <td id="T_01f0b_row1_col6" class="data row1 col6">0.0</td>
      <td id="T_01f0b_row1_col7" class="data row1 col7">1,379</td>
      <td id="T_01f0b_row1_col8" class="data row1 col8">1,379</td>
      <td id="T_01f0b_row1_col9" class="data row1 col9">0</td>
      <td id="T_01f0b_row1_col10" class="data row1 col10">2.32</td>
      <td id="T_01f0b_row1_col11" class="data row1 col11">$0.00512</td>
      <td id="T_01f0b_row1_col12" class="data row1 col12">87%</td>
      <td id="T_01f0b_row1_col13" class="data row1 col13">$512</td>
    </tr>
    <tr>
      <th id="T_01f0b_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_01f0b_row2_col0" class="data row2 col0">Round 2: routing</td>
      <td id="T_01f0b_row2_col1" class="data row2 col1">0.98</td>
      <td id="T_01f0b_row2_col2" class="data row2 col2">100%</td>
      <td id="T_01f0b_row2_col3" class="data row2 col3">100%</td>
      <td id="T_01f0b_row2_col4" class="data row2 col4">100%</td>
      <td id="T_01f0b_row2_col5" class="data row2 col5">2.6</td>
      <td id="T_01f0b_row2_col6" class="data row2 col6">0.0</td>
      <td id="T_01f0b_row2_col7" class="data row2 col7">1,485</td>
      <td id="T_01f0b_row2_col8" class="data row2 col8">1,485</td>
      <td id="T_01f0b_row2_col9" class="data row2 col9">0</td>
      <td id="T_01f0b_row2_col10" class="data row2 col10">1.87</td>
      <td id="T_01f0b_row2_col11" class="data row2 col11">$0.00302</td>
      <td id="T_01f0b_row2_col12" class="data row2 col12">92%</td>
      <td id="T_01f0b_row2_col13" class="data row2 col13">$302</td>
    </tr>
    <tr>
      <th id="T_01f0b_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_01f0b_row3_col0" class="data row3 col0">Round 3: caching</td>
      <td id="T_01f0b_row3_col1" class="data row3 col1">0.98</td>
      <td id="T_01f0b_row3_col2" class="data row3 col2">100%</td>
      <td id="T_01f0b_row3_col3" class="data row3 col3">100%</td>
      <td id="T_01f0b_row3_col4" class="data row3 col4">100%</td>
      <td id="T_01f0b_row3_col5" class="data row3 col5">2.6</td>
      <td id="T_01f0b_row3_col6" class="data row3 col6">0.0</td>
      <td id="T_01f0b_row3_col7" class="data row3 col7">2,684</td>
      <td id="T_01f0b_row3_col8" class="data row3 col8">2,684</td>
      <td id="T_01f0b_row3_col9" class="data row3 col9">1,779</td>
      <td id="T_01f0b_row3_col10" class="data row3 col10">1.85</td>
      <td id="T_01f0b_row3_col11" class="data row3 col11">$0.00244</td>
      <td id="T_01f0b_row3_col12" class="data row3 col12">94%</td>
      <td id="T_01f0b_row3_col13" class="data row3 col13">$244</td>
    </tr>
    <tr>
      <th id="T_01f0b_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_01f0b_row4_col0" class="data row4 col0">Round 4: split workflow</td>
      <td id="T_01f0b_row4_col1" class="data row4 col1">0.98</td>
      <td id="T_01f0b_row4_col2" class="data row4 col2">100%</td>
      <td id="T_01f0b_row4_col3" class="data row4 col3">100%</td>
      <td id="T_01f0b_row4_col4" class="data row4 col4">100%</td>
      <td id="T_01f0b_row4_col5" class="data row4 col5">2.6</td>
      <td id="T_01f0b_row4_col6" class="data row4 col6">0.0</td>
      <td id="T_01f0b_row4_col7" class="data row4 col7">2,412</td>
      <td id="T_01f0b_row4_col8" class="data row4 col8">2,974</td>
      <td id="T_01f0b_row4_col9" class="data row4 col9">1,779</td>
      <td id="T_01f0b_row4_col10" class="data row4 col10">1.41</td>
      <td id="T_01f0b_row4_col11" class="data row4 col11">$0.00204</td>
      <td id="T_01f0b_row4_col12" class="data row4 col12">95%</td>
      <td id="T_01f0b_row4_col13" class="data row4 col13">$204</td>
    </tr>
  </tbody>
</table>

## Round-by-round impact

Each row compares one round to the previous round. This makes the optimization knobs easier to reason about than a single before/after number.


```python
round_impact = summary[
    [
        "variant_label",
        "mean_quality",
        "policy_compliance",
        "mean_tool_calls",
        "mean_extra_tool_calls",
        "mean_sync_tokens",
        "mean_total_tokens",
        "mean_cached_tokens",
        "p50_latency_s",
        "cost_per_ticket_usd",
    ]
].copy()

for col in ["mean_sync_tokens", "mean_total_tokens", "p50_latency_s", "cost_per_ticket_usd"]:
    round_impact[f"{col}_delta_vs_previous"] = round_impact[col].diff()

round_impact["quality_delta_vs_previous"] = round_impact["mean_quality"].diff()

display(
    round_impact.style.format(
        {
            "mean_quality": "{:.2f}",
            "policy_compliance": "{:.0%}",
            "mean_tool_calls": "{:.1f}",
            "mean_extra_tool_calls": "{:.1f}",
            "mean_sync_tokens": "{:,.0f}",
            "mean_total_tokens": "{:,.0f}",
            "mean_cached_tokens": "{:,.0f}",
            "p50_latency_s": "{:.2f}",
            "cost_per_ticket_usd": "${:.5f}",
            "mean_sync_tokens_delta_vs_previous": "{:+,.0f}",
            "mean_total_tokens_delta_vs_previous": "{:+,.0f}",
            "p50_latency_s_delta_vs_previous": "{:+.2f}",
            "cost_per_ticket_usd_delta_vs_previous": "${:+.5f}",
            "quality_delta_vs_previous": "{:+.2f}",
        }
    )
)
```

<table id="T_81e05">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_81e05_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_81e05_level0_col1" class="col_heading level0 col1">mean_quality</th>
      <th id="T_81e05_level0_col2" class="col_heading level0 col2">policy_compliance</th>
      <th id="T_81e05_level0_col3" class="col_heading level0 col3">mean_tool_calls</th>
      <th id="T_81e05_level0_col4" class="col_heading level0 col4">mean_extra_tool_calls</th>
      <th id="T_81e05_level0_col5" class="col_heading level0 col5">mean_sync_tokens</th>
      <th id="T_81e05_level0_col6" class="col_heading level0 col6">mean_total_tokens</th>
      <th id="T_81e05_level0_col7" class="col_heading level0 col7">mean_cached_tokens</th>
      <th id="T_81e05_level0_col8" class="col_heading level0 col8">p50_latency_s</th>
      <th id="T_81e05_level0_col9" class="col_heading level0 col9">cost_per_ticket_usd</th>
      <th id="T_81e05_level0_col10" class="col_heading level0 col10">mean_sync_tokens_delta_vs_previous</th>
      <th id="T_81e05_level0_col11" class="col_heading level0 col11">mean_total_tokens_delta_vs_previous</th>
      <th id="T_81e05_level0_col12" class="col_heading level0 col12">p50_latency_s_delta_vs_previous</th>
      <th id="T_81e05_level0_col13" class="col_heading level0 col13">cost_per_ticket_usd_delta_vs_previous</th>
      <th id="T_81e05_level0_col14" class="col_heading level0 col14">quality_delta_vs_previous</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_81e05_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_81e05_row0_col0" class="data row0 col0">Bad baseline</td>
      <td id="T_81e05_row0_col1" class="data row0 col1">0.51</td>
      <td id="T_81e05_row0_col2" class="data row0 col2">10%</td>
      <td id="T_81e05_row0_col3" class="data row0 col3">5.0</td>
      <td id="T_81e05_row0_col4" class="data row0 col4">2.4</td>
      <td id="T_81e05_row0_col5" class="data row0 col5">11,935</td>
      <td id="T_81e05_row0_col6" class="data row0 col6">11,935</td>
      <td id="T_81e05_row0_col7" class="data row0 col7">0</td>
      <td id="T_81e05_row0_col8" class="data row0 col8">4.88</td>
      <td id="T_81e05_row0_col9" class="data row0 col9">$0.03813</td>
      <td id="T_81e05_row0_col10" class="data row0 col10">+nan</td>
      <td id="T_81e05_row0_col11" class="data row0 col11">+nan</td>
      <td id="T_81e05_row0_col12" class="data row0 col12">+nan</td>
      <td id="T_81e05_row0_col13" class="data row0 col13">$+nan</td>
      <td id="T_81e05_row0_col14" class="data row0 col14">+nan</td>
    </tr>
    <tr>
      <th id="T_81e05_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_81e05_row1_col0" class="data row1 col0">Round 1: controls</td>
      <td id="T_81e05_row1_col1" class="data row1 col1">0.98</td>
      <td id="T_81e05_row1_col2" class="data row1 col2">100%</td>
      <td id="T_81e05_row1_col3" class="data row1 col3">2.6</td>
      <td id="T_81e05_row1_col4" class="data row1 col4">0.0</td>
      <td id="T_81e05_row1_col5" class="data row1 col5">1,379</td>
      <td id="T_81e05_row1_col6" class="data row1 col6">1,379</td>
      <td id="T_81e05_row1_col7" class="data row1 col7">0</td>
      <td id="T_81e05_row1_col8" class="data row1 col8">2.32</td>
      <td id="T_81e05_row1_col9" class="data row1 col9">$0.00512</td>
      <td id="T_81e05_row1_col10" class="data row1 col10">-10,556</td>
      <td id="T_81e05_row1_col11" class="data row1 col11">-10,556</td>
      <td id="T_81e05_row1_col12" class="data row1 col12">-2.56</td>
      <td id="T_81e05_row1_col13" class="data row1 col13">$-0.03301</td>
      <td id="T_81e05_row1_col14" class="data row1 col14">+0.48</td>
    </tr>
    <tr>
      <th id="T_81e05_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_81e05_row2_col0" class="data row2 col0">Round 2: routing</td>
      <td id="T_81e05_row2_col1" class="data row2 col1">0.98</td>
      <td id="T_81e05_row2_col2" class="data row2 col2">100%</td>
      <td id="T_81e05_row2_col3" class="data row2 col3">2.6</td>
      <td id="T_81e05_row2_col4" class="data row2 col4">0.0</td>
      <td id="T_81e05_row2_col5" class="data row2 col5">1,485</td>
      <td id="T_81e05_row2_col6" class="data row2 col6">1,485</td>
      <td id="T_81e05_row2_col7" class="data row2 col7">0</td>
      <td id="T_81e05_row2_col8" class="data row2 col8">1.87</td>
      <td id="T_81e05_row2_col9" class="data row2 col9">$0.00302</td>
      <td id="T_81e05_row2_col10" class="data row2 col10">+106</td>
      <td id="T_81e05_row2_col11" class="data row2 col11">+106</td>
      <td id="T_81e05_row2_col12" class="data row2 col12">-0.45</td>
      <td id="T_81e05_row2_col13" class="data row2 col13">$-0.00210</td>
      <td id="T_81e05_row2_col14" class="data row2 col14">+0.00</td>
    </tr>
    <tr>
      <th id="T_81e05_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_81e05_row3_col0" class="data row3 col0">Round 3: caching</td>
      <td id="T_81e05_row3_col1" class="data row3 col1">0.98</td>
      <td id="T_81e05_row3_col2" class="data row3 col2">100%</td>
      <td id="T_81e05_row3_col3" class="data row3 col3">2.6</td>
      <td id="T_81e05_row3_col4" class="data row3 col4">0.0</td>
      <td id="T_81e05_row3_col5" class="data row3 col5">2,684</td>
      <td id="T_81e05_row3_col6" class="data row3 col6">2,684</td>
      <td id="T_81e05_row3_col7" class="data row3 col7">1,779</td>
      <td id="T_81e05_row3_col8" class="data row3 col8">1.85</td>
      <td id="T_81e05_row3_col9" class="data row3 col9">$0.00244</td>
      <td id="T_81e05_row3_col10" class="data row3 col10">+1,199</td>
      <td id="T_81e05_row3_col11" class="data row3 col11">+1,199</td>
      <td id="T_81e05_row3_col12" class="data row3 col12">-0.02</td>
      <td id="T_81e05_row3_col13" class="data row3 col13">$-0.00058</td>
      <td id="T_81e05_row3_col14" class="data row3 col14">+0.00</td>
    </tr>
    <tr>
      <th id="T_81e05_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_81e05_row4_col0" class="data row4 col0">Round 4: split workflow</td>
      <td id="T_81e05_row4_col1" class="data row4 col1">0.98</td>
      <td id="T_81e05_row4_col2" class="data row4 col2">100%</td>
      <td id="T_81e05_row4_col3" class="data row4 col3">2.6</td>
      <td id="T_81e05_row4_col4" class="data row4 col4">0.0</td>
      <td id="T_81e05_row4_col5" class="data row4 col5">2,412</td>
      <td id="T_81e05_row4_col6" class="data row4 col6">2,974</td>
      <td id="T_81e05_row4_col7" class="data row4 col7">1,779</td>
      <td id="T_81e05_row4_col8" class="data row4 col8">1.41</td>
      <td id="T_81e05_row4_col9" class="data row4 col9">$0.00204</td>
      <td id="T_81e05_row4_col10" class="data row4 col10">-272</td>
      <td id="T_81e05_row4_col11" class="data row4 col11">+290</td>
      <td id="T_81e05_row4_col12" class="data row4 col12">-0.44</td>
      <td id="T_81e05_row4_col13" class="data row4 col13">$-0.00040</td>
      <td id="T_81e05_row4_col14" class="data row4 col14">+0.00</td>
    </tr>
  </tbody>
</table>

```python
plot_df = summary.copy()
labels = plot_df["variant_label"].str.replace("Round ", "R", regex=False)

fig, axes = plt.subplots(1, 3, figsize=(16, 4))

axes[0].bar(labels, plot_df["mean_sync_tokens"], color="#4C78A8")
axes[0].set_title("Mean synchronous tokens")
axes[0].set_ylabel("sync tokens per ticket")
axes[0].tick_params(axis="x", rotation=30)

axes[1].bar(labels, plot_df["cost_per_ticket_usd"], color="#59A14F")
axes[1].set_title("Estimated cost")
axes[1].set_ylabel("USD per ticket")
axes[1].tick_params(axis="x", rotation=30)

axes[2].plot(labels, plot_df["mean_quality"], marker="o", color="#E15759")
axes[2].set_ylim(0, 1.0)
axes[2].set_title("Quality score")
axes[2].set_ylabel("score")
axes[2].tick_params(axis="x", rotation=30)

plt.tight_layout()
plt.show()
```

![](https://developers.openai.com/cookbook/assets/notebook-outputs/examples/agent_optimization/optimizing_agents_for_cost_and_quality/cell-23-output-0.png)

## Optional: live Responses API tool loop

The implementation in [live_api.py](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/live_api.py) forwards `response.output` before appending function results, preserving reasoning and tool-call items. Follow-up requests retain the configured tool choice, allowing an order and policy lookup followed by a refund call. After `max_tool_rounds` batches, the final request uses `tool_choice="none"` to obtain an answer without executing more tools.

The example uses a refund ticket and derives its allowed tools from that same ticket. This router still uses fixture labels; replace it with evaluated application logic for live traffic. An incomplete response or an unexpected final tool call raises an error instead of being reported as a completed answer.

For separate conversational turns, `previous_response_id` can carry state. Supply instructions again when they should apply to the next request.


```python
from live_api import (
    background_followup_request,
    live_config_for_ticket,
    run_live_support_ticket,
)

# Keep the allowed tools tied to the ticket being evaluated.
live_ticket = EVAL_SET[2]  # Order/policy lookup, then open a refund case.
live_config = live_config_for_ticket(live_ticket, "01_prompt_tool_context_controls")
```

```python
if RUN_LIVE_API_CALLS:
    live_result = run_live_support_ticket(live_ticket, live_config, client=client)
    print(live_result["response_text"])
    display(pd.DataFrame([{k: v for k, v in live_result.items() if k not in {"response_text", "tool_results"}}]))
else:
    print("Dry-run mode. Set OPENAI_API_KEY and RUN_LIVE_API_CALLS=true to run a live Responses API ticket.")
```

```text
Your refund request is eligible, and I’ve opened a return/refund case for order O-1003.

Next step: please use the return instructions from your order page or confirmation email to send the item back. Once the return is received and processed, your refund will be issued.
```

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>config</th>
      <th>ticket_id</th>
      <th>model</th>
      <th>tool_calls</th>
      <th>latency_s</th>
      <th>estimated_cost_usd</th>
      <th>input_tokens</th>
      <th>cached_tokens</th>
      <th>output_tokens</th>
      <th>reasoning_tokens</th>
      <th>total_tokens</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>01_prompt_tool_context_controls</td>
      <td>T-003</td>
      <td>gpt-5.4</td>
      <td>3</td>
      <td>8.056909</td>
      <td>0.008085</td>
      <td>1788</td>
      <td>0</td>
      <td>241</td>
      <td>84</td>
      <td>2029</td>
    </tr>
  </tbody>
</table>
</div>

## Optimization round 1: prompt, tool, and context controls

Start with concrete response and tool rules. The request below combines low verbosity and reasoning effort with an output cap and an allowed tool subset. The output cap includes both visible and reasoning tokens, so check for incomplete responses when tuning it.

The helper also limits tool rounds and returns slim payloads. For long conversations, evaluate compaction or truncation carefully: removing earlier context can discard facts needed for the next decision.

This demo restricts tools using known ticket metadata. A production router needs separate evaluation and a fallback for low-confidence routing. If you use prompt optimization, target a specific observed failure and rerun the same evals.


```python
round1_request_example = {
    "model": "gpt-5.4",
    "instructions": CONTROLLED_PROMPT,
    "tools": SLIM_TOOLS,
    "tool_choice": allowed_tool_choice(["lookup_order", "lookup_policy"], mode="auto"),
    "reasoning": {"effort": "low"},
    "text": {"verbosity": "low"},
    "max_output_tokens": 350,
    "parallel_tool_calls": True,
    "truncation": "auto",
    "context_management": [{"type": "compaction", "compact_threshold": 20_000}],
    "input": [
        {
            "role": "user",
            "content": "My blender arrived cracked. Order O-1002. Can you replace it?",
        }
    ],
}

print(json.dumps(round1_request_example, indent=2)[:2400] + "\n...")
```

```text
{
  "model": "gpt-5.4",
  "instructions": "Role: E-commerce support assistant.\n\nGoal: Resolve routine support tickets with the fewest necessary tool calls while preserving policy correctness.\n\nTool rules:\n- Use only tools required for the current decision.\n- Order status: order lookup only.\n- Damaged delivery or refund: order lookup plus the relevant policy.\n- Billing duplicate charge: order lookup plus billing policy, then escalate.\n- Account access with unverified identity: customer lookup plus account policy, then escalate.\n\nResponse rules:\n- Give the customer the outcome and next step.\n- Do not expose internal reasoning, raw tool data, audit notes, or policy text.\n- Keep the customer-facing answer under 120 words unless escalation legally requires more detail.",
  "tools": [
    {
      "type": "function",
      "name": "lookup_customer",
      "description": "Fetch minimal customer verification and support tier fields.",
      "parameters": {
        "type": "object",
        "properties": {
          "customer_id": {
            "type": "string"
          }
        },
        "required": [
          "customer_id"
        ],
        "additionalProperties": false
      },
      "strict": true
    },
    {
      "type": "function",
      "name": "lookup_order",
      "description": "Fetch order status, delivery age, payment status, and item value.",
      "parameters": {
        "type": "object",
        "properties": {
          "order_id": {
            "type": "string"
          }
        },
        "required": [
          "order_id"
        ],
        "additionalProperties": false
      },
      "strict": true
    },
    {
      "type": "function",
      "name": "lookup_policy",
      "description": "Fetch the policy needed for the current support decision.",
      "parameters": {
        "type": "object",
        "properties": {
          "topic": {
            "type": "string",
            "enum": [
              "shipping",
              "damaged_delivery",
              "refunds",
              "billing",
              "account_access"
            ]
          }
        },
        "required": [
          "topic"
        ],
        "additionalProperties": false
      },
      "strict": true
    },
    {
      "type": "function",
      "name": "create_refund_case",
      "description": "Open a refund or replacement case only after polic
...
```

```python
round1_detail = traces[traces["variant"].isin(["00_bad_baseline", "01_prompt_tool_context_controls"])]
display(
    round1_detail[
        [
            "variant_label",
            "ticket_id",
            "intent",
            "tools",
            "action",
            "extra_tool_calls",
            "policy_compliant",
            "concise",
            "visible_output_tokens",
            "total_tokens",
            "latency_s",
            "cost_usd",
            "quality_score",
        ]
    ].style.format({"cost_usd": "${:.5f}", "quality_score": "{:.2f}", "latency_s": "{:.2f}"})
)
```

<table id="T_3f362">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_3f362_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_3f362_level0_col1" class="col_heading level0 col1">ticket_id</th>
      <th id="T_3f362_level0_col2" class="col_heading level0 col2">intent</th>
      <th id="T_3f362_level0_col3" class="col_heading level0 col3">tools</th>
      <th id="T_3f362_level0_col4" class="col_heading level0 col4">action</th>
      <th id="T_3f362_level0_col5" class="col_heading level0 col5">extra_tool_calls</th>
      <th id="T_3f362_level0_col6" class="col_heading level0 col6">policy_compliant</th>
      <th id="T_3f362_level0_col7" class="col_heading level0 col7">concise</th>
      <th id="T_3f362_level0_col8" class="col_heading level0 col8">visible_output_tokens</th>
      <th id="T_3f362_level0_col9" class="col_heading level0 col9">total_tokens</th>
      <th id="T_3f362_level0_col10" class="col_heading level0 col10">latency_s</th>
      <th id="T_3f362_level0_col11" class="col_heading level0 col11">cost_usd</th>
      <th id="T_3f362_level0_col12" class="col_heading level0 col12">quality_score</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_3f362_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_3f362_row0_col0" class="data row0 col0">Bad baseline</td>
      <td id="T_3f362_row0_col1" class="data row0 col1">T-001</td>
      <td id="T_3f362_row0_col2" class="data row0 col2">order_status</td>
      <td id="T_3f362_row0_col3" class="data row0 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row0_col4" class="data row0 col4">provide_status_eta</td>
      <td id="T_3f362_row0_col5" class="data row0 col5">4</td>
      <td id="T_3f362_row0_col6" class="data row0 col6">False</td>
      <td id="T_3f362_row0_col7" class="data row0 col7">False</td>
      <td id="T_3f362_row0_col8" class="data row0 col8">167</td>
      <td id="T_3f362_row0_col9" class="data row0 col9">12913</td>
      <td id="T_3f362_row0_col10" class="data row0 col10">4.88</td>
      <td id="T_3f362_row0_col11" class="data row0 col11">$0.03993</td>
      <td id="T_3f362_row0_col12" class="data row0 col12">0.55</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_3f362_row1_col0" class="data row1 col0">Bad baseline</td>
      <td id="T_3f362_row1_col1" class="data row1 col1">T-002</td>
      <td id="T_3f362_row1_col2" class="data row1 col2">damaged_delivery</td>
      <td id="T_3f362_row1_col3" class="data row1 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row1_col4" class="data row1 col4">open_replacement_without_photo</td>
      <td id="T_3f362_row1_col5" class="data row1 col5">3</td>
      <td id="T_3f362_row1_col6" class="data row1 col6">False</td>
      <td id="T_3f362_row1_col7" class="data row1 col7">False</td>
      <td id="T_3f362_row1_col8" class="data row1 col8">174</td>
      <td id="T_3f362_row1_col9" class="data row1 col9">12917</td>
      <td id="T_3f362_row1_col10" class="data row1 col10">4.88</td>
      <td id="T_3f362_row1_col11" class="data row1 col11">$0.04034</td>
      <td id="T_3f362_row1_col12" class="data row1 col12">0.65</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_3f362_row2_col0" class="data row2 col0">Bad baseline</td>
      <td id="T_3f362_row2_col1" class="data row2 col1">T-003</td>
      <td id="T_3f362_row2_col2" class="data row2 col2">refund_eligibility</td>
      <td id="T_3f362_row2_col3" class="data row2 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row2_col4" class="data row2 col4">escalate_refund_review</td>
      <td id="T_3f362_row2_col5" class="data row2 col5">2</td>
      <td id="T_3f362_row2_col6" class="data row2 col6">False</td>
      <td id="T_3f362_row2_col7" class="data row2 col7">False</td>
      <td id="T_3f362_row2_col8" class="data row2 col8">170</td>
      <td id="T_3f362_row2_col9" class="data row2 col9">12818</td>
      <td id="T_3f362_row2_col10" class="data row2 col10">4.87</td>
      <td id="T_3f362_row2_col11" class="data row2 col11">$0.04004</td>
      <td id="T_3f362_row2_col12" class="data row2 col12">0.22</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_3f362_row3_col0" class="data row3 col0">Bad baseline</td>
      <td id="T_3f362_row3_col1" class="data row3 col1">T-004</td>
      <td id="T_3f362_row3_col2" class="data row3 col2">billing_issue</td>
      <td id="T_3f362_row3_col3" class="data row3 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row3_col4" class="data row3 col4">escalate_billing_review</td>
      <td id="T_3f362_row3_col5" class="data row3 col5">2</td>
      <td id="T_3f362_row3_col6" class="data row3 col6">True</td>
      <td id="T_3f362_row3_col7" class="data row3 col7">False</td>
      <td id="T_3f362_row3_col8" class="data row3 col8">169</td>
      <td id="T_3f362_row3_col9" class="data row3 col9">12830</td>
      <td id="T_3f362_row3_col10" class="data row3 col10">4.87</td>
      <td id="T_3f362_row3_col11" class="data row3 col11">$0.04038</td>
      <td id="T_3f362_row3_col12" class="data row3 col12">0.85</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_3f362_row4_col0" class="data row4 col0">Bad baseline</td>
      <td id="T_3f362_row4_col1" class="data row4 col1">T-005</td>
      <td id="T_3f362_row4_col2" class="data row4 col2">account_access</td>
      <td id="T_3f362_row4_col3" class="data row4 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row4_col4" class="data row4 col4">escalate_account_security</td>
      <td id="T_3f362_row4_col5" class="data row4 col5">2</td>
      <td id="T_3f362_row4_col6" class="data row4 col6">False</td>
      <td id="T_3f362_row4_col7" class="data row4 col7">False</td>
      <td id="T_3f362_row4_col8" class="data row4 col8">172</td>
      <td id="T_3f362_row4_col9" class="data row4 col9">8112</td>
      <td id="T_3f362_row4_col10" class="data row4 col10">3.97</td>
      <td id="T_3f362_row4_col11" class="data row4 col11">$0.02899</td>
      <td id="T_3f362_row4_col12" class="data row4 col12">0.60</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row5" class="row_heading level0 row5">5</th>
      <td id="T_3f362_row5_col0" class="data row5 col0">Bad baseline</td>
      <td id="T_3f362_row5_col1" class="data row5 col1">T-006</td>
      <td id="T_3f362_row5_col2" class="data row5 col2">refund_dispute</td>
      <td id="T_3f362_row5_col3" class="data row5 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row5_col4" class="data row5 col4">escalate_refund_review</td>
      <td id="T_3f362_row5_col5" class="data row5 col5">2</td>
      <td id="T_3f362_row5_col6" class="data row5 col6">False</td>
      <td id="T_3f362_row5_col7" class="data row5 col7">False</td>
      <td id="T_3f362_row5_col8" class="data row5 col8">168</td>
      <td id="T_3f362_row5_col9" class="data row5 col9">12869</td>
      <td id="T_3f362_row5_col10" class="data row5 col10">4.88</td>
      <td id="T_3f362_row5_col11" class="data row5 col11">$0.04077</td>
      <td id="T_3f362_row5_col12" class="data row5 col12">0.60</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row6" class="row_heading level0 row6">6</th>
      <td id="T_3f362_row6_col0" class="data row6 col0">Bad baseline</td>
      <td id="T_3f362_row6_col1" class="data row6 col1">T-007</td>
      <td id="T_3f362_row6_col2" class="data row6 col2">delivered_not_received</td>
      <td id="T_3f362_row6_col3" class="data row6 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row6_col4" class="data row6 col4">start_delivery_trace_steps</td>
      <td id="T_3f362_row6_col5" class="data row6 col5">3</td>
      <td id="T_3f362_row6_col6" class="data row6 col6">False</td>
      <td id="T_3f362_row6_col7" class="data row6 col7">False</td>
      <td id="T_3f362_row6_col8" class="data row6 col8">172</td>
      <td id="T_3f362_row6_col9" class="data row6 col9">12862</td>
      <td id="T_3f362_row6_col10" class="data row6 col10">4.87</td>
      <td id="T_3f362_row6_col11" class="data row6 col11">$0.04018</td>
      <td id="T_3f362_row6_col12" class="data row6 col12">0.57</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row7" class="row_heading level0 row7">7</th>
      <td id="T_3f362_row7_col0" class="data row7 col0">Bad baseline</td>
      <td id="T_3f362_row7_col1" class="data row7 col1">T-008</td>
      <td id="T_3f362_row7_col2" class="data row7 col2">high_value_damage</td>
      <td id="T_3f362_row7_col3" class="data row7 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row7_col4" class="data row7 col4">promise_refund_high_value_damage</td>
      <td id="T_3f362_row7_col5" class="data row7 col5">2</td>
      <td id="T_3f362_row7_col6" class="data row7 col6">False</td>
      <td id="T_3f362_row7_col7" class="data row7 col7">False</td>
      <td id="T_3f362_row7_col8" class="data row7 col8">174</td>
      <td id="T_3f362_row7_col9" class="data row7 col9">12997</td>
      <td id="T_3f362_row7_col10" class="data row7 col10">4.91</td>
      <td id="T_3f362_row7_col11" class="data row7 col11">$0.04136</td>
      <td id="T_3f362_row7_col12" class="data row7 col12">0.22</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row8" class="row_heading level0 row8">8</th>
      <td id="T_3f362_row8_col0" class="data row8 col0">Bad baseline</td>
      <td id="T_3f362_row8_col1" class="data row8 col1">T-009</td>
      <td id="T_3f362_row8_col2" class="data row8 col2">refund_eligibility</td>
      <td id="T_3f362_row8_col3" class="data row8 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row8_col4" class="data row8 col4">escalate_refund_review</td>
      <td id="T_3f362_row8_col5" class="data row8 col5">2</td>
      <td id="T_3f362_row8_col6" class="data row8 col6">False</td>
      <td id="T_3f362_row8_col7" class="data row8 col7">False</td>
      <td id="T_3f362_row8_col8" class="data row8 col8">169</td>
      <td id="T_3f362_row8_col9" class="data row8 col9">12921</td>
      <td id="T_3f362_row8_col10" class="data row8 col10">4.88</td>
      <td id="T_3f362_row8_col11" class="data row8 col11">$0.04029</td>
      <td id="T_3f362_row8_col12" class="data row8 col12">0.22</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row9" class="row_heading level0 row9">9</th>
      <td id="T_3f362_row9_col0" class="data row9 col0">Bad baseline</td>
      <td id="T_3f362_row9_col1" class="data row9 col1">T-010</td>
      <td id="T_3f362_row9_col2" class="data row9 col2">account_access</td>
      <td id="T_3f362_row9_col3" class="data row9 col3">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_3f362_row9_col4" class="data row9 col4">escalate_account_security</td>
      <td id="T_3f362_row9_col5" class="data row9 col5">2</td>
      <td id="T_3f362_row9_col6" class="data row9 col6">False</td>
      <td id="T_3f362_row9_col7" class="data row9 col7">False</td>
      <td id="T_3f362_row9_col8" class="data row9 col8">172</td>
      <td id="T_3f362_row9_col9" class="data row9 col9">8115</td>
      <td id="T_3f362_row9_col10" class="data row9 col10">3.97</td>
      <td id="T_3f362_row9_col11" class="data row9 col11">$0.02900</td>
      <td id="T_3f362_row9_col12" class="data row9 col12">0.60</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row10" class="row_heading level0 row10">10</th>
      <td id="T_3f362_row10_col0" class="data row10 col0">Round 1: controls</td>
      <td id="T_3f362_row10_col1" class="data row10 col1">T-001</td>
      <td id="T_3f362_row10_col2" class="data row10 col2">order_status</td>
      <td id="T_3f362_row10_col3" class="data row10 col3">lookup_order</td>
      <td id="T_3f362_row10_col4" class="data row10 col4">provide_status_eta</td>
      <td id="T_3f362_row10_col5" class="data row10 col5">0</td>
      <td id="T_3f362_row10_col6" class="data row10 col6">True</td>
      <td id="T_3f362_row10_col7" class="data row10 col7">True</td>
      <td id="T_3f362_row10_col8" class="data row10 col8">42</td>
      <td id="T_3f362_row10_col9" class="data row10 col9">1252</td>
      <td id="T_3f362_row10_col10" class="data row10 col10">2.00</td>
      <td id="T_3f362_row10_col11" class="data row10 col11">$0.00418</td>
      <td id="T_3f362_row10_col12" class="data row10 col12">0.98</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row11" class="row_heading level0 row11">11</th>
      <td id="T_3f362_row11_col0" class="data row11 col0">Round 1: controls</td>
      <td id="T_3f362_row11_col1" class="data row11 col1">T-002</td>
      <td id="T_3f362_row11_col2" class="data row11 col2">damaged_delivery</td>
      <td id="T_3f362_row11_col3" class="data row11 col3">lookup_order, lookup_policy</td>
      <td id="T_3f362_row11_col4" class="data row11 col4">request_photo_then_offer_replacement</td>
      <td id="T_3f362_row11_col5" class="data row11 col5">0</td>
      <td id="T_3f362_row11_col6" class="data row11 col6">True</td>
      <td id="T_3f362_row11_col7" class="data row11 col7">True</td>
      <td id="T_3f362_row11_col8" class="data row11 col8">45</td>
      <td id="T_3f362_row11_col9" class="data row11 col9">1354</td>
      <td id="T_3f362_row11_col10" class="data row11 col10">2.17</td>
      <td id="T_3f362_row11_col11" class="data row11 col11">$0.00482</td>
      <td id="T_3f362_row11_col12" class="data row11 col12">0.98</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row12" class="row_heading level0 row12">12</th>
      <td id="T_3f362_row12_col0" class="data row12 col0">Round 1: controls</td>
      <td id="T_3f362_row12_col1" class="data row12 col1">T-003</td>
      <td id="T_3f362_row12_col2" class="data row12 col2">refund_eligibility</td>
      <td id="T_3f362_row12_col3" class="data row12 col3">lookup_order, lookup_policy, create_refund_case</td>
      <td id="T_3f362_row12_col4" class="data row12 col4">open_refund_case</td>
      <td id="T_3f362_row12_col5" class="data row12 col5">0</td>
      <td id="T_3f362_row12_col6" class="data row12 col6">True</td>
      <td id="T_3f362_row12_col7" class="data row12 col7">True</td>
      <td id="T_3f362_row12_col8" class="data row12 col8">51</td>
      <td id="T_3f362_row12_col9" class="data row12 col9">1393</td>
      <td id="T_3f362_row12_col10" class="data row12 col10">2.32</td>
      <td id="T_3f362_row12_col11" class="data row12 col11">$0.00512</td>
      <td id="T_3f362_row12_col12" class="data row12 col12">0.98</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row13" class="row_heading level0 row13">13</th>
      <td id="T_3f362_row13_col0" class="data row13 col0">Round 1: controls</td>
      <td id="T_3f362_row13_col1" class="data row13 col1">T-004</td>
      <td id="T_3f362_row13_col2" class="data row13 col2">billing_issue</td>
      <td id="T_3f362_row13_col3" class="data row13 col3">lookup_order, lookup_policy, escalate_to_human</td>
      <td id="T_3f362_row13_col4" class="data row13 col4">escalate_billing_review</td>
      <td id="T_3f362_row13_col5" class="data row13 col5">0</td>
      <td id="T_3f362_row13_col6" class="data row13 col6">True</td>
      <td id="T_3f362_row13_col7" class="data row13 col7">True</td>
      <td id="T_3f362_row13_col8" class="data row13 col8">35</td>
      <td id="T_3f362_row13_col9" class="data row13 col9">1383</td>
      <td id="T_3f362_row13_col10" class="data row13 col10">2.31</td>
      <td id="T_3f362_row13_col11" class="data row13 col11">$0.00512</td>
      <td id="T_3f362_row13_col12" class="data row13 col12">0.98</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row14" class="row_heading level0 row14">14</th>
      <td id="T_3f362_row14_col0" class="data row14 col0">Round 1: controls</td>
      <td id="T_3f362_row14_col1" class="data row14 col1">T-005</td>
      <td id="T_3f362_row14_col2" class="data row14 col2">account_access</td>
      <td id="T_3f362_row14_col3" class="data row14 col3">lookup_customer, lookup_policy, escalate_to_human</td>
      <td id="T_3f362_row14_col4" class="data row14 col4">escalate_account_security</td>
      <td id="T_3f362_row14_col5" class="data row14 col5">0</td>
      <td id="T_3f362_row14_col6" class="data row14 col6">True</td>
      <td id="T_3f362_row14_col7" class="data row14 col7">True</td>
      <td id="T_3f362_row14_col8" class="data row14 col8">39</td>
      <td id="T_3f362_row14_col9" class="data row14 col9">1378</td>
      <td id="T_3f362_row14_col10" class="data row14 col10">2.32</td>
      <td id="T_3f362_row14_col11" class="data row14 col11">$0.00543</td>
      <td id="T_3f362_row14_col12" class="data row14 col12">0.99</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row15" class="row_heading level0 row15">15</th>
      <td id="T_3f362_row15_col0" class="data row15 col0">Round 1: controls</td>
      <td id="T_3f362_row15_col1" class="data row15 col1">T-006</td>
      <td id="T_3f362_row15_col2" class="data row15 col2">refund_dispute</td>
      <td id="T_3f362_row15_col3" class="data row15 col3">lookup_order, lookup_policy, escalate_to_human</td>
      <td id="T_3f362_row15_col4" class="data row15 col4">escalate_refund_review</td>
      <td id="T_3f362_row15_col5" class="data row15 col5">0</td>
      <td id="T_3f362_row15_col6" class="data row15 col6">True</td>
      <td id="T_3f362_row15_col7" class="data row15 col7">True</td>
      <td id="T_3f362_row15_col8" class="data row15 col8">36</td>
      <td id="T_3f362_row15_col9" class="data row15 col9">1418</td>
      <td id="T_3f362_row15_col10" class="data row15 col10">2.32</td>
      <td id="T_3f362_row15_col11" class="data row15 col11">$0.00545</td>
      <td id="T_3f362_row15_col12" class="data row15 col12">0.99</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row16" class="row_heading level0 row16">16</th>
      <td id="T_3f362_row16_col0" class="data row16 col0">Round 1: controls</td>
      <td id="T_3f362_row16_col1" class="data row16 col1">T-007</td>
      <td id="T_3f362_row16_col2" class="data row16 col2">delivered_not_received</td>
      <td id="T_3f362_row16_col3" class="data row16 col3">lookup_order, lookup_policy</td>
      <td id="T_3f362_row16_col4" class="data row16 col4">start_delivery_trace_steps</td>
      <td id="T_3f362_row16_col5" class="data row16 col5">0</td>
      <td id="T_3f362_row16_col6" class="data row16 col6">True</td>
      <td id="T_3f362_row16_col7" class="data row16 col7">True</td>
      <td id="T_3f362_row16_col8" class="data row16 col8">41</td>
      <td id="T_3f362_row16_col9" class="data row16 col9">1390</td>
      <td id="T_3f362_row16_col10" class="data row16 col10">2.17</td>
      <td id="T_3f362_row16_col11" class="data row16 col11">$0.00486</td>
      <td id="T_3f362_row16_col12" class="data row16 col12">0.98</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row17" class="row_heading level0 row17">17</th>
      <td id="T_3f362_row17_col0" class="data row17 col0">Round 1: controls</td>
      <td id="T_3f362_row17_col1" class="data row17 col1">T-008</td>
      <td id="T_3f362_row17_col2" class="data row17 col2">high_value_damage</td>
      <td id="T_3f362_row17_col3" class="data row17 col3">lookup_order, lookup_policy, escalate_to_human</td>
      <td id="T_3f362_row17_col4" class="data row17 col4">escalate_high_value_damage</td>
      <td id="T_3f362_row17_col5" class="data row17 col5">0</td>
      <td id="T_3f362_row17_col6" class="data row17 col6">True</td>
      <td id="T_3f362_row17_col7" class="data row17 col7">True</td>
      <td id="T_3f362_row17_col8" class="data row17 col8">38</td>
      <td id="T_3f362_row17_col9" class="data row17 col9">1445</td>
      <td id="T_3f362_row17_col10" class="data row17 col10">2.33</td>
      <td id="T_3f362_row17_col11" class="data row17 col11">$0.00568</td>
      <td id="T_3f362_row17_col12" class="data row17 col12">0.99</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row18" class="row_heading level0 row18">18</th>
      <td id="T_3f362_row18_col0" class="data row18 col0">Round 1: controls</td>
      <td id="T_3f362_row18_col1" class="data row18 col1">T-009</td>
      <td id="T_3f362_row18_col2" class="data row18 col2">refund_eligibility</td>
      <td id="T_3f362_row18_col3" class="data row18 col3">lookup_order, lookup_policy, create_refund_case</td>
      <td id="T_3f362_row18_col4" class="data row18 col4">open_refund_case</td>
      <td id="T_3f362_row18_col5" class="data row18 col5">0</td>
      <td id="T_3f362_row18_col6" class="data row18 col6">True</td>
      <td id="T_3f362_row18_col7" class="data row18 col7">True</td>
      <td id="T_3f362_row18_col8" class="data row18 col8">51</td>
      <td id="T_3f362_row18_col9" class="data row18 col9">1397</td>
      <td id="T_3f362_row18_col10" class="data row18 col10">2.32</td>
      <td id="T_3f362_row18_col11" class="data row18 col11">$0.00513</td>
      <td id="T_3f362_row18_col12" class="data row18 col12">0.98</td>
    </tr>
    <tr>
      <th id="T_3f362_level0_row19" class="row_heading level0 row19">19</th>
      <td id="T_3f362_row19_col0" class="data row19 col0">Round 1: controls</td>
      <td id="T_3f362_row19_col1" class="data row19 col1">T-010</td>
      <td id="T_3f362_row19_col2" class="data row19 col2">account_access</td>
      <td id="T_3f362_row19_col3" class="data row19 col3">lookup_customer, lookup_policy, escalate_to_human</td>
      <td id="T_3f362_row19_col4" class="data row19 col4">escalate_account_security</td>
      <td id="T_3f362_row19_col5" class="data row19 col5">0</td>
      <td id="T_3f362_row19_col6" class="data row19 col6">True</td>
      <td id="T_3f362_row19_col7" class="data row19 col7">True</td>
      <td id="T_3f362_row19_col8" class="data row19 col8">39</td>
      <td id="T_3f362_row19_col9" class="data row19 col9">1382</td>
      <td id="T_3f362_row19_col10" class="data row19 col10">2.32</td>
      <td id="T_3f362_row19_col11" class="data row19 col11">$0.00544</td>
      <td id="T_3f362_row19_col12" class="data row19 col12">0.99</td>
    </tr>
  </tbody>
</table>

## Optimization round 2: model selection

Right-size the model to each step instead of choosing one global model. Establish a GPT-5.4 baseline for each workload, and evaluate it against the same labeled tickets, prompts, tools, structured-output schema, and quality criteria.

- **Intent classification, extraction, and low-risk routing:** Use `gpt-5.4-nano` for ticket classification, entity extraction, and simple tags. Compare intent accuracy, high-risk false negatives, structured-output reliability, latency, and cost per correctly classified ticket. ([GPT-5.4 nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano))

- **Routine support and order workflows:** Use `gpt-5.4-mini` for order status, damaged delivery, straightforward refund-eligibility checks, and other repeatable support tasks that require policy interpretation or tool use. Evaluate resolution correctness, tool-call accuracy, policy compliance, p50/p95 latency, and cost per successfully resolved ticket. ([GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini))

- **Complex or high-risk cases:** Use `gpt-5.4` for account-access problems, duplicate-charge escalations, refund disputes, and other high-consequence interactions. Preserve deterministic authorization and refund checks, explicit escalation rules, and human review where required. Measure resolution quality, policy adherence, latency, and end-to-end cost. ([GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4))

The GPT-5.6 family offers newer models that correspond to these same tiers. [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) (`gpt-5.6-luna`) maps to the nano tier for classification and high-volume tasks. [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) (`gpt-5.6-terra`) maps to the mini tier for routine support workflows. [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) (`gpt-5.6-sol`) maps to the full-model tier for complex or high-risk cases. Each can be evaluated against its corresponding GPT-5.4 baseline using the same tickets and quality criteria.

For each comparison, begin with the existing reasoning-effort setting and also evaluate one level lower. A newer model can be more economical at the task level if it resolves tickets with fewer retries, unnecessary tool calls, or escalations. Consider fine-tuning only if a selected model explicitly supports it. ([GPT-5.6 migration guidance](https://developers.openai.com/api/docs/guides/latest-model))


```python
from live_api import TRIAGE_SCHEMA

print(json.dumps(TRIAGE_SCHEMA, indent=2))
# Optional: from live_api import live_triage_example
# live_triage_example(EVAL_SET[0]["message"], client=client)
```

```text
{
  "type": "json_schema",
  "name": "support_triage",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "intent": {
        "type": "string",
        "enum": [
          "order_status",
          "damaged_delivery",
          "refund_eligibility",
          "billing_issue",
          "account_access",
          "refund_dispute",
          "delivered_not_received",
          "high_value_damage"
        ]
      },
      "risk": {
        "type": "string",
        "enum": [
          "low",
          "medium",
          "high"
        ]
      },
      "needs_human": {
        "type": "boolean"
      },
      "order_id": {
        "type": [
          "string",
          "null"
        ]
      }
    },
    "required": [
      "intent",
      "risk",
      "needs_human",
      "order_id"
    ],
    "additionalProperties": false
  }
}
```

```python
model_routing_view = traces[traces["variant"].isin(["01_prompt_tool_context_controls", "02_model_routing"])]
display(
    model_routing_view[
        [
            "variant_label",
            "ticket_id",
            "intent",
            "risk",
            "model",
            "routing_tokens",
            "total_tokens",
            "sync_cost_usd",
            "quality_score",
            "policy_compliant",
        ]
    ].style.format({"sync_cost_usd": "${:.5f}", "quality_score": "{:.2f}"})
)
```

<table id="T_1317a">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_1317a_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_1317a_level0_col1" class="col_heading level0 col1">ticket_id</th>
      <th id="T_1317a_level0_col2" class="col_heading level0 col2">intent</th>
      <th id="T_1317a_level0_col3" class="col_heading level0 col3">risk</th>
      <th id="T_1317a_level0_col4" class="col_heading level0 col4">model</th>
      <th id="T_1317a_level0_col5" class="col_heading level0 col5">routing_tokens</th>
      <th id="T_1317a_level0_col6" class="col_heading level0 col6">total_tokens</th>
      <th id="T_1317a_level0_col7" class="col_heading level0 col7">sync_cost_usd</th>
      <th id="T_1317a_level0_col8" class="col_heading level0 col8">quality_score</th>
      <th id="T_1317a_level0_col9" class="col_heading level0 col9">policy_compliant</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_1317a_level0_row0" class="row_heading level0 row0">10</th>
      <td id="T_1317a_row0_col0" class="data row0 col0">Round 1: controls</td>
      <td id="T_1317a_row0_col1" class="data row0 col1">T-001</td>
      <td id="T_1317a_row0_col2" class="data row0 col2">order_status</td>
      <td id="T_1317a_row0_col3" class="data row0 col3">low</td>
      <td id="T_1317a_row0_col4" class="data row0 col4">gpt-5.4</td>
      <td id="T_1317a_row0_col5" class="data row0 col5">0</td>
      <td id="T_1317a_row0_col6" class="data row0 col6">1252</td>
      <td id="T_1317a_row0_col7" class="data row0 col7">$0.00418</td>
      <td id="T_1317a_row0_col8" class="data row0 col8">0.98</td>
      <td id="T_1317a_row0_col9" class="data row0 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row1" class="row_heading level0 row1">11</th>
      <td id="T_1317a_row1_col0" class="data row1 col0">Round 1: controls</td>
      <td id="T_1317a_row1_col1" class="data row1 col1">T-002</td>
      <td id="T_1317a_row1_col2" class="data row1 col2">damaged_delivery</td>
      <td id="T_1317a_row1_col3" class="data row1 col3">medium</td>
      <td id="T_1317a_row1_col4" class="data row1 col4">gpt-5.4</td>
      <td id="T_1317a_row1_col5" class="data row1 col5">0</td>
      <td id="T_1317a_row1_col6" class="data row1 col6">1354</td>
      <td id="T_1317a_row1_col7" class="data row1 col7">$0.00482</td>
      <td id="T_1317a_row1_col8" class="data row1 col8">0.98</td>
      <td id="T_1317a_row1_col9" class="data row1 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row2" class="row_heading level0 row2">12</th>
      <td id="T_1317a_row2_col0" class="data row2 col0">Round 1: controls</td>
      <td id="T_1317a_row2_col1" class="data row2 col1">T-003</td>
      <td id="T_1317a_row2_col2" class="data row2 col2">refund_eligibility</td>
      <td id="T_1317a_row2_col3" class="data row2 col3">medium</td>
      <td id="T_1317a_row2_col4" class="data row2 col4">gpt-5.4</td>
      <td id="T_1317a_row2_col5" class="data row2 col5">0</td>
      <td id="T_1317a_row2_col6" class="data row2 col6">1393</td>
      <td id="T_1317a_row2_col7" class="data row2 col7">$0.00512</td>
      <td id="T_1317a_row2_col8" class="data row2 col8">0.98</td>
      <td id="T_1317a_row2_col9" class="data row2 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row3" class="row_heading level0 row3">13</th>
      <td id="T_1317a_row3_col0" class="data row3 col0">Round 1: controls</td>
      <td id="T_1317a_row3_col1" class="data row3 col1">T-004</td>
      <td id="T_1317a_row3_col2" class="data row3 col2">billing_issue</td>
      <td id="T_1317a_row3_col3" class="data row3 col3">medium</td>
      <td id="T_1317a_row3_col4" class="data row3 col4">gpt-5.4</td>
      <td id="T_1317a_row3_col5" class="data row3 col5">0</td>
      <td id="T_1317a_row3_col6" class="data row3 col6">1383</td>
      <td id="T_1317a_row3_col7" class="data row3 col7">$0.00512</td>
      <td id="T_1317a_row3_col8" class="data row3 col8">0.98</td>
      <td id="T_1317a_row3_col9" class="data row3 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row4" class="row_heading level0 row4">14</th>
      <td id="T_1317a_row4_col0" class="data row4 col0">Round 1: controls</td>
      <td id="T_1317a_row4_col1" class="data row4 col1">T-005</td>
      <td id="T_1317a_row4_col2" class="data row4 col2">account_access</td>
      <td id="T_1317a_row4_col3" class="data row4 col3">high</td>
      <td id="T_1317a_row4_col4" class="data row4 col4">gpt-5.4</td>
      <td id="T_1317a_row4_col5" class="data row4 col5">0</td>
      <td id="T_1317a_row4_col6" class="data row4 col6">1378</td>
      <td id="T_1317a_row4_col7" class="data row4 col7">$0.00543</td>
      <td id="T_1317a_row4_col8" class="data row4 col8">0.99</td>
      <td id="T_1317a_row4_col9" class="data row4 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row5" class="row_heading level0 row5">15</th>
      <td id="T_1317a_row5_col0" class="data row5 col0">Round 1: controls</td>
      <td id="T_1317a_row5_col1" class="data row5 col1">T-006</td>
      <td id="T_1317a_row5_col2" class="data row5 col2">refund_dispute</td>
      <td id="T_1317a_row5_col3" class="data row5 col3">high</td>
      <td id="T_1317a_row5_col4" class="data row5 col4">gpt-5.4</td>
      <td id="T_1317a_row5_col5" class="data row5 col5">0</td>
      <td id="T_1317a_row5_col6" class="data row5 col6">1418</td>
      <td id="T_1317a_row5_col7" class="data row5 col7">$0.00545</td>
      <td id="T_1317a_row5_col8" class="data row5 col8">0.99</td>
      <td id="T_1317a_row5_col9" class="data row5 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row6" class="row_heading level0 row6">16</th>
      <td id="T_1317a_row6_col0" class="data row6 col0">Round 1: controls</td>
      <td id="T_1317a_row6_col1" class="data row6 col1">T-007</td>
      <td id="T_1317a_row6_col2" class="data row6 col2">delivered_not_received</td>
      <td id="T_1317a_row6_col3" class="data row6 col3">medium</td>
      <td id="T_1317a_row6_col4" class="data row6 col4">gpt-5.4</td>
      <td id="T_1317a_row6_col5" class="data row6 col5">0</td>
      <td id="T_1317a_row6_col6" class="data row6 col6">1390</td>
      <td id="T_1317a_row6_col7" class="data row6 col7">$0.00486</td>
      <td id="T_1317a_row6_col8" class="data row6 col8">0.98</td>
      <td id="T_1317a_row6_col9" class="data row6 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row7" class="row_heading level0 row7">17</th>
      <td id="T_1317a_row7_col0" class="data row7 col0">Round 1: controls</td>
      <td id="T_1317a_row7_col1" class="data row7 col1">T-008</td>
      <td id="T_1317a_row7_col2" class="data row7 col2">high_value_damage</td>
      <td id="T_1317a_row7_col3" class="data row7 col3">high</td>
      <td id="T_1317a_row7_col4" class="data row7 col4">gpt-5.4</td>
      <td id="T_1317a_row7_col5" class="data row7 col5">0</td>
      <td id="T_1317a_row7_col6" class="data row7 col6">1445</td>
      <td id="T_1317a_row7_col7" class="data row7 col7">$0.00568</td>
      <td id="T_1317a_row7_col8" class="data row7 col8">0.99</td>
      <td id="T_1317a_row7_col9" class="data row7 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row8" class="row_heading level0 row8">18</th>
      <td id="T_1317a_row8_col0" class="data row8 col0">Round 1: controls</td>
      <td id="T_1317a_row8_col1" class="data row8 col1">T-009</td>
      <td id="T_1317a_row8_col2" class="data row8 col2">refund_eligibility</td>
      <td id="T_1317a_row8_col3" class="data row8 col3">low</td>
      <td id="T_1317a_row8_col4" class="data row8 col4">gpt-5.4</td>
      <td id="T_1317a_row8_col5" class="data row8 col5">0</td>
      <td id="T_1317a_row8_col6" class="data row8 col6">1397</td>
      <td id="T_1317a_row8_col7" class="data row8 col7">$0.00513</td>
      <td id="T_1317a_row8_col8" class="data row8 col8">0.98</td>
      <td id="T_1317a_row8_col9" class="data row8 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row9" class="row_heading level0 row9">19</th>
      <td id="T_1317a_row9_col0" class="data row9 col0">Round 1: controls</td>
      <td id="T_1317a_row9_col1" class="data row9 col1">T-010</td>
      <td id="T_1317a_row9_col2" class="data row9 col2">account_access</td>
      <td id="T_1317a_row9_col3" class="data row9 col3">high</td>
      <td id="T_1317a_row9_col4" class="data row9 col4">gpt-5.4</td>
      <td id="T_1317a_row9_col5" class="data row9 col5">0</td>
      <td id="T_1317a_row9_col6" class="data row9 col6">1382</td>
      <td id="T_1317a_row9_col7" class="data row9 col7">$0.00544</td>
      <td id="T_1317a_row9_col8" class="data row9 col8">0.99</td>
      <td id="T_1317a_row9_col9" class="data row9 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row10" class="row_heading level0 row10">20</th>
      <td id="T_1317a_row10_col0" class="data row10 col0">Round 2: routing</td>
      <td id="T_1317a_row10_col1" class="data row10 col1">T-001</td>
      <td id="T_1317a_row10_col2" class="data row10 col2">order_status</td>
      <td id="T_1317a_row10_col3" class="data row10 col3">low</td>
      <td id="T_1317a_row10_col4" class="data row10 col4">gpt-5.4-mini</td>
      <td id="T_1317a_row10_col5" class="data row10 col5">208</td>
      <td id="T_1317a_row10_col6" class="data row10 col6">1353</td>
      <td id="T_1317a_row10_col7" class="data row10 col7">$0.00123</td>
      <td id="T_1317a_row10_col8" class="data row10 col8">0.98</td>
      <td id="T_1317a_row10_col9" class="data row10 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row11" class="row_heading level0 row11">21</th>
      <td id="T_1317a_row11_col0" class="data row11 col0">Round 2: routing</td>
      <td id="T_1317a_row11_col1" class="data row11 col1">T-002</td>
      <td id="T_1317a_row11_col2" class="data row11 col2">damaged_delivery</td>
      <td id="T_1317a_row11_col3" class="data row11 col3">medium</td>
      <td id="T_1317a_row11_col4" class="data row11 col4">gpt-5.4-mini</td>
      <td id="T_1317a_row11_col5" class="data row11 col5">208</td>
      <td id="T_1317a_row11_col6" class="data row11 col6">1451</td>
      <td id="T_1317a_row11_col7" class="data row11 col7">$0.00141</td>
      <td id="T_1317a_row11_col8" class="data row11 col8">0.98</td>
      <td id="T_1317a_row11_col9" class="data row11 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row12" class="row_heading level0 row12">22</th>
      <td id="T_1317a_row12_col0" class="data row12 col0">Round 2: routing</td>
      <td id="T_1317a_row12_col1" class="data row12 col1">T-003</td>
      <td id="T_1317a_row12_col2" class="data row12 col2">refund_eligibility</td>
      <td id="T_1317a_row12_col3" class="data row12 col3">medium</td>
      <td id="T_1317a_row12_col4" class="data row12 col4">gpt-5.4-mini</td>
      <td id="T_1317a_row12_col5" class="data row12 col5">210</td>
      <td id="T_1317a_row12_col6" class="data row12 col6">1490</td>
      <td id="T_1317a_row12_col7" class="data row12 col7">$0.00149</td>
      <td id="T_1317a_row12_col8" class="data row12 col8">0.98</td>
      <td id="T_1317a_row12_col9" class="data row12 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row13" class="row_heading level0 row13">23</th>
      <td id="T_1317a_row13_col0" class="data row13 col0">Round 2: routing</td>
      <td id="T_1317a_row13_col1" class="data row13 col1">T-004</td>
      <td id="T_1317a_row13_col2" class="data row13 col2">billing_issue</td>
      <td id="T_1317a_row13_col3" class="data row13 col3">medium</td>
      <td id="T_1317a_row13_col4" class="data row13 col4">gpt-5.4-mini</td>
      <td id="T_1317a_row13_col5" class="data row13 col5">207</td>
      <td id="T_1317a_row13_col6" class="data row13 col6">1474</td>
      <td id="T_1317a_row13_col7" class="data row13 col7">$0.00147</td>
      <td id="T_1317a_row13_col8" class="data row13 col8">0.98</td>
      <td id="T_1317a_row13_col9" class="data row13 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row14" class="row_heading level0 row14">24</th>
      <td id="T_1317a_row14_col0" class="data row14 col0">Round 2: routing</td>
      <td id="T_1317a_row14_col1" class="data row14 col1">T-005</td>
      <td id="T_1317a_row14_col2" class="data row14 col2">account_access</td>
      <td id="T_1317a_row14_col3" class="data row14 col3">high</td>
      <td id="T_1317a_row14_col4" class="data row14 col4">gpt-5.4</td>
      <td id="T_1317a_row14_col5" class="data row14 col5">206</td>
      <td id="T_1317a_row14_col6" class="data row14 col6">1490</td>
      <td id="T_1317a_row14_col7" class="data row14 col7">$0.00536</td>
      <td id="T_1317a_row14_col8" class="data row14 col8">0.99</td>
      <td id="T_1317a_row14_col9" class="data row14 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row15" class="row_heading level0 row15">25</th>
      <td id="T_1317a_row15_col0" class="data row15 col0">Round 2: routing</td>
      <td id="T_1317a_row15_col1" class="data row15 col1">T-006</td>
      <td id="T_1317a_row15_col2" class="data row15 col2">refund_dispute</td>
      <td id="T_1317a_row15_col3" class="data row15 col3">high</td>
      <td id="T_1317a_row15_col4" class="data row15 col4">gpt-5.4</td>
      <td id="T_1317a_row15_col5" class="data row15 col5">212</td>
      <td id="T_1317a_row15_col6" class="data row15 col6">1536</td>
      <td id="T_1317a_row15_col7" class="data row15 col7">$0.00537</td>
      <td id="T_1317a_row15_col8" class="data row15 col8">0.99</td>
      <td id="T_1317a_row15_col9" class="data row15 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row16" class="row_heading level0 row16">26</th>
      <td id="T_1317a_row16_col0" class="data row16 col0">Round 2: routing</td>
      <td id="T_1317a_row16_col1" class="data row16 col1">T-007</td>
      <td id="T_1317a_row16_col2" class="data row16 col2">delivered_not_received</td>
      <td id="T_1317a_row16_col3" class="data row16 col3">medium</td>
      <td id="T_1317a_row16_col4" class="data row16 col4">gpt-5.4-mini</td>
      <td id="T_1317a_row16_col5" class="data row16 col5">213</td>
      <td id="T_1317a_row16_col6" class="data row16 col6">1492</td>
      <td id="T_1317a_row16_col7" class="data row16 col7">$0.00142</td>
      <td id="T_1317a_row16_col8" class="data row16 col8">0.98</td>
      <td id="T_1317a_row16_col9" class="data row16 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row17" class="row_heading level0 row17">27</th>
      <td id="T_1317a_row17_col0" class="data row17 col0">Round 2: routing</td>
      <td id="T_1317a_row17_col1" class="data row17 col1">T-008</td>
      <td id="T_1317a_row17_col2" class="data row17 col2">high_value_damage</td>
      <td id="T_1317a_row17_col3" class="data row17 col3">high</td>
      <td id="T_1317a_row17_col4" class="data row17 col4">gpt-5.4</td>
      <td id="T_1317a_row17_col5" class="data row17 col5">218</td>
      <td id="T_1317a_row17_col6" class="data row17 col6">1570</td>
      <td id="T_1317a_row17_col7" class="data row17 col7">$0.00562</td>
      <td id="T_1317a_row17_col8" class="data row17 col8">0.99</td>
      <td id="T_1317a_row17_col9" class="data row17 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row18" class="row_heading level0 row18">28</th>
      <td id="T_1317a_row18_col0" class="data row18 col0">Round 2: routing</td>
      <td id="T_1317a_row18_col1" class="data row18 col1">T-009</td>
      <td id="T_1317a_row18_col2" class="data row18 col2">refund_eligibility</td>
      <td id="T_1317a_row18_col3" class="data row18 col3">low</td>
      <td id="T_1317a_row18_col4" class="data row18 col4">gpt-5.4-mini</td>
      <td id="T_1317a_row18_col5" class="data row18 col5">214</td>
      <td id="T_1317a_row18_col6" class="data row18 col6">1498</td>
      <td id="T_1317a_row18_col7" class="data row18 col7">$0.00149</td>
      <td id="T_1317a_row18_col8" class="data row18 col8">0.98</td>
      <td id="T_1317a_row18_col9" class="data row18 col9">True</td>
    </tr>
    <tr>
      <th id="T_1317a_level0_row19" class="row_heading level0 row19">29</th>
      <td id="T_1317a_row19_col0" class="data row19 col0">Round 2: routing</td>
      <td id="T_1317a_row19_col1" class="data row19 col1">T-010</td>
      <td id="T_1317a_row19_col2" class="data row19 col2">account_access</td>
      <td id="T_1317a_row19_col3" class="data row19 col3">high</td>
      <td id="T_1317a_row19_col4" class="data row19 col4">gpt-5.4</td>
      <td id="T_1317a_row19_col5" class="data row19 col5">209</td>
      <td id="T_1317a_row19_col6" class="data row19 col6">1497</td>
      <td id="T_1317a_row19_col7" class="data row19 col7">$0.00537</td>
      <td id="T_1317a_row19_col8" class="data row19 col8">0.99</td>
      <td id="T_1317a_row19_col9" class="data row19 col9">True</td>
    </tr>
  </tbody>
</table>

## Optimization round 3: prompt caching

Every support request includes the same core instructions, policy rules, tool definitions, and response schema. Prompt caching lets the API reuse that shared context across tickets, reducing repeated processing and lowering input-token costs. Customer-specific details, such as order IDs, account information, and retrieved records, should appear after the shared prefix.

Prompt caching has evolved between model generations. With `gpt-5.4-mini`, the API automatically identifies repeated prefixes and can reuse the shared support context even when the customer-specific details change. Writing a new prefix does not add a separate cache-write charge. Keep the tool definitions consistent and use `tool_choice.allowed_tools` to control which tools are available without changing the shared tool list.

GPT-5.6 introduces two changes: cache writes are billed, and developers can explicitly choose which part of the prompt should be cached. With `gpt-5.6-luna`, `gpt-5.6-terra`, or `gpt-5.6-sol`, the default cache breakpoint is placed after the latest message. If that message changes between tickets, the longest cached prefix may not match. Implicit mode can still reuse earlier eligible message endings, including the initial developer-message block. Because writing content to cache costs 1.25 times the normal input-token price, repeatedly caching those unique messages can increase cost without creating useful reuse.

For example, two order-status tickets can share the same support instructions, policy rules, and tools, even though one asks about order `O-1001` and the other asks about order `O-2002`. For GPT-5.6, put the shared playbook in a developer-message `input_text` block and mark its end with `prompt_cache_breakpoint={"mode": "explicit"}` before the order-specific details. Top-level `instructions` cannot contain a breakpoint. Set `prompt_cache_options` to explicit mode with `ttl="30m"`, and use the same `prompt_cache_key`, such as `support_order_status_v1`, for both requests. With an eligible matching prefix, the first ticket writes the playbook and later tickets can reuse it at the cached-input rate while processing their own order details normally.

Compare `cached_tokens` and `cache_write_tokens` alongside latency and cost per resolved ticket. For additional implementation details, see the [prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching).


```python
cache_friendly_request = {
    "model": "gpt-5.4-mini",
    "instructions": CACHE_FRIENDLY_PROMPT,
    "tools": SLIM_TOOLS,
    "tool_choice": allowed_tool_choice(["lookup_order"], mode="auto"),
    "prompt_cache_key": "support_order_status_v1",
    "reasoning": {"effort": "low"},
    "text": {"verbosity": "low"},
    "max_output_tokens": 300,
    "input": [
        {
            "role": "user",
            "content": json.dumps(
                {
                    "ticket_id": "T-001",
                    "customer_id": "C-100",
                    "message": "Where is order O-1001?",
                    "order_id": "O-1001",
                }
            ),
        }
    ],
}

print(json.dumps(cache_friendly_request, indent=2)[:2400] + "\n...")
```

```text
{
  "model": "gpt-5.4-mini",
  "instructions": "Role: E-commerce support assistant.\nConstraints: Be concise, policy-compliant, and explicit about next steps. Do not disclose internal data.\nEscalate: duplicate charges, account access without verification, high-value disputes, and refunds outside the window.\nOutput shape: customer_message, resolution_type, escalate, internal_tags.\nTool contract: tool definitions are stable across requests; restrict callable tools with tool_choice.allowed_tools.\nVersion: support-agent-optimization-v1.\n\nStable support playbook digest:\n- Shipping delays: provide status, ETA, and tracking next steps; do not refund solely for short carrier delays.\n- Delivered-not-received: verify delivery details, ask the customer to check common locations, and start carrier trace steps when appropriate.\n- Damaged delivery: request photo evidence before offering replacement or refund; high-value damaged items require human review.\n- Refunds: standard returnable items are eligible within 30 days; outside-window or high-value disputes require human review.\n- Billing: duplicate-charge reports require billing review; acknowledge and escalate, but do not promise a completed refund.\n- Account access: when identity is not verified, escalate to account security; do not change credentials or contact information in chat.\n- Customer messages must be concise, policy-compliant, and explicit about next steps.\n- Internal notes, raw carrier payloads, CRM audit logs, and policy appendices must never be exposed to the customer.\nStable support playbook digest:\n- Shipping delays: provide status, ETA, and tracking next steps; do not refund solely for short carrier delays.\n- Delivered-not-received: verify delivery details, ask the customer to check common locations, and start carrier trace steps when appropriate.\n- Damaged delivery: request photo evidence before offering replacement or refund; high-value damaged items require human review.\n- Refunds: standard returnable items are eligible within 30 days; outside-window or high-value disputes require human review.\n- Billing: duplicate-charge reports require billing review; acknowledge and escalate, but do not promise a completed refund.\n- Account access: when identity is not verified, escalate to account security; do not change credentials or contact information in chat.\n- Customer messages must be
...
```

```python
previous_response_id_example = '''
from support import STABLE_SUPPORT_PREFIX

first = client.responses.create(
    model="gpt-5.4-mini",
    instructions=STABLE_SUPPORT_PREFIX,
    tools=SLIM_TOOLS,
    input="Customer asks: Where is order O-1001?",
    prompt_cache_key="support_order_status_v1",
)

follow_up = client.responses.create(
    model="gpt-5.4-mini",
    previous_response_id=first.id,
    instructions=STABLE_SUPPORT_PREFIX,
    input="Customer follow-up: the carrier link is stale. What should I do?",
    prompt_cache_key="support_order_status_v1",
)
'''

print(previous_response_id_example)
```

```text

from support import STABLE_SUPPORT_PREFIX

first = client.responses.create(
    model="gpt-5.4-mini",
    instructions=STABLE_SUPPORT_PREFIX,
    tools=SLIM_TOOLS,
    input="Customer asks: Where is order O-1001?",
    prompt_cache_key="support_order_status_v1",
)

follow_up = client.responses.create(
    model="gpt-5.4-mini",
    previous_response_id=first.id,
    instructions=STABLE_SUPPORT_PREFIX,
    input="Customer follow-up: the carrier link is stale. What should I do?",
    prompt_cache_key="support_order_status_v1",
)
```

```python
caching_view = traces[traces["variant"].isin(["02_model_routing", "03_prompt_caching"])]
display(
    caching_view[
        [
            "variant_label",
            "ticket_id",
            "model",
            "input_tokens",
            "cacheable_prefix_tokens",
            "cached_tokens",
            "latency_input_tokens",
            "output_tokens",
            "cost_usd",
            "latency_s",
            "quality_score",
        ]
    ].style.format({"cost_usd": "${:.5f}", "quality_score": "{:.2f}", "latency_s": "{:.2f}"})
)
```

<table id="T_e68b0">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_e68b0_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_e68b0_level0_col1" class="col_heading level0 col1">ticket_id</th>
      <th id="T_e68b0_level0_col2" class="col_heading level0 col2">model</th>
      <th id="T_e68b0_level0_col3" class="col_heading level0 col3">input_tokens</th>
      <th id="T_e68b0_level0_col4" class="col_heading level0 col4">cacheable_prefix_tokens</th>
      <th id="T_e68b0_level0_col5" class="col_heading level0 col5">cached_tokens</th>
      <th id="T_e68b0_level0_col6" class="col_heading level0 col6">latency_input_tokens</th>
      <th id="T_e68b0_level0_col7" class="col_heading level0 col7">output_tokens</th>
      <th id="T_e68b0_level0_col8" class="col_heading level0 col8">cost_usd</th>
      <th id="T_e68b0_level0_col9" class="col_heading level0 col9">latency_s</th>
      <th id="T_e68b0_level0_col10" class="col_heading level0 col10">quality_score</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_e68b0_level0_row0" class="row_heading level0 row0">20</th>
      <td id="T_e68b0_row0_col0" class="data row0 col0">Round 2: routing</td>
      <td id="T_e68b0_row0_col1" class="data row0 col1">T-001</td>
      <td id="T_e68b0_row0_col2" class="data row0 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row0_col3" class="data row0 col3">1068</td>
      <td id="T_e68b0_row0_col4" class="data row0 col4">0</td>
      <td id="T_e68b0_row0_col5" class="data row0 col5">0</td>
      <td id="T_e68b0_row0_col6" class="data row0 col6">1068</td>
      <td id="T_e68b0_row0_col7" class="data row0 col7">77</td>
      <td id="T_e68b0_row0_col8" class="data row0 col8">$0.00123</td>
      <td id="T_e68b0_row0_col9" class="data row0 col9">1.56</td>
      <td id="T_e68b0_row0_col10" class="data row0 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row1" class="row_heading level0 row1">21</th>
      <td id="T_e68b0_row1_col0" class="data row1 col0">Round 2: routing</td>
      <td id="T_e68b0_row1_col1" class="data row1 col1">T-002</td>
      <td id="T_e68b0_row1_col2" class="data row1 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row1_col3" class="data row1 col3">1139</td>
      <td id="T_e68b0_row1_col4" class="data row1 col4">0</td>
      <td id="T_e68b0_row1_col5" class="data row1 col5">0</td>
      <td id="T_e68b0_row1_col6" class="data row1 col6">1139</td>
      <td id="T_e68b0_row1_col7" class="data row1 col7">104</td>
      <td id="T_e68b0_row1_col8" class="data row1 col8">$0.00141</td>
      <td id="T_e68b0_row1_col9" class="data row1 col9">1.72</td>
      <td id="T_e68b0_row1_col10" class="data row1 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row2" class="row_heading level0 row2">22</th>
      <td id="T_e68b0_row2_col0" class="data row2 col0">Round 2: routing</td>
      <td id="T_e68b0_row2_col1" class="data row2 col1">T-003</td>
      <td id="T_e68b0_row2_col2" class="data row2 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row2_col3" class="data row2 col3">1162</td>
      <td id="T_e68b0_row2_col4" class="data row2 col4">0</td>
      <td id="T_e68b0_row2_col5" class="data row2 col5">0</td>
      <td id="T_e68b0_row2_col6" class="data row2 col6">1162</td>
      <td id="T_e68b0_row2_col7" class="data row2 col7">118</td>
      <td id="T_e68b0_row2_col8" class="data row2 col8">$0.00149</td>
      <td id="T_e68b0_row2_col9" class="data row2 col9">1.87</td>
      <td id="T_e68b0_row2_col10" class="data row2 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row3" class="row_heading level0 row3">23</th>
      <td id="T_e68b0_row3_col0" class="data row3 col0">Round 2: routing</td>
      <td id="T_e68b0_row3_col1" class="data row3 col1">T-004</td>
      <td id="T_e68b0_row3_col2" class="data row3 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row3_col3" class="data row3 col3">1150</td>
      <td id="T_e68b0_row3_col4" class="data row3 col4">0</td>
      <td id="T_e68b0_row3_col5" class="data row3 col5">0</td>
      <td id="T_e68b0_row3_col6" class="data row3 col6">1150</td>
      <td id="T_e68b0_row3_col7" class="data row3 col7">117</td>
      <td id="T_e68b0_row3_col8" class="data row3 col8">$0.00147</td>
      <td id="T_e68b0_row3_col9" class="data row3 col9">1.87</td>
      <td id="T_e68b0_row3_col10" class="data row3 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row4" class="row_heading level0 row4">24</th>
      <td id="T_e68b0_row4_col0" class="data row4 col0">Round 2: routing</td>
      <td id="T_e68b0_row4_col1" class="data row4 col1">T-005</td>
      <td id="T_e68b0_row4_col2" class="data row4 col2">gpt-5.4</td>
      <td id="T_e68b0_row4_col3" class="data row4 col3">1119</td>
      <td id="T_e68b0_row4_col4" class="data row4 col4">0</td>
      <td id="T_e68b0_row4_col5" class="data row4 col5">0</td>
      <td id="T_e68b0_row4_col6" class="data row4 col6">1119</td>
      <td id="T_e68b0_row4_col7" class="data row4 col7">165</td>
      <td id="T_e68b0_row4_col8" class="data row4 col8">$0.00536</td>
      <td id="T_e68b0_row4_col9" class="data row4 col9">2.48</td>
      <td id="T_e68b0_row4_col10" class="data row4 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row5" class="row_heading level0 row5">25</th>
      <td id="T_e68b0_row5_col0" class="data row5 col0">Round 2: routing</td>
      <td id="T_e68b0_row5_col1" class="data row5 col1">T-006</td>
      <td id="T_e68b0_row5_col2" class="data row5 col2">gpt-5.4</td>
      <td id="T_e68b0_row5_col3" class="data row5 col3">1166</td>
      <td id="T_e68b0_row5_col4" class="data row5 col4">0</td>
      <td id="T_e68b0_row5_col5" class="data row5 col5">0</td>
      <td id="T_e68b0_row5_col6" class="data row5 col6">1166</td>
      <td id="T_e68b0_row5_col7" class="data row5 col7">158</td>
      <td id="T_e68b0_row5_col8" class="data row5 col8">$0.00537</td>
      <td id="T_e68b0_row5_col9" class="data row5 col9">2.49</td>
      <td id="T_e68b0_row5_col10" class="data row5 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row6" class="row_heading level0 row6">26</th>
      <td id="T_e68b0_row6_col0" class="data row6 col0">Round 2: routing</td>
      <td id="T_e68b0_row6_col1" class="data row6 col1">T-007</td>
      <td id="T_e68b0_row6_col2" class="data row6 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row6_col3" class="data row6 col3">1179</td>
      <td id="T_e68b0_row6_col4" class="data row6 col4">0</td>
      <td id="T_e68b0_row6_col5" class="data row6 col5">0</td>
      <td id="T_e68b0_row6_col6" class="data row6 col6">1179</td>
      <td id="T_e68b0_row6_col7" class="data row6 col7">100</td>
      <td id="T_e68b0_row6_col8" class="data row6 col8">$0.00142</td>
      <td id="T_e68b0_row6_col9" class="data row6 col9">1.73</td>
      <td id="T_e68b0_row6_col10" class="data row6 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row7" class="row_heading level0 row7">27</th>
      <td id="T_e68b0_row7_col0" class="data row7 col0">Round 2: routing</td>
      <td id="T_e68b0_row7_col1" class="data row7 col1">T-008</td>
      <td id="T_e68b0_row7_col2" class="data row7 col2">gpt-5.4</td>
      <td id="T_e68b0_row7_col3" class="data row7 col3">1180</td>
      <td id="T_e68b0_row7_col4" class="data row7 col4">0</td>
      <td id="T_e68b0_row7_col5" class="data row7 col5">0</td>
      <td id="T_e68b0_row7_col6" class="data row7 col6">1180</td>
      <td id="T_e68b0_row7_col7" class="data row7 col7">172</td>
      <td id="T_e68b0_row7_col8" class="data row7 col8">$0.00562</td>
      <td id="T_e68b0_row7_col9" class="data row7 col9">2.49</td>
      <td id="T_e68b0_row7_col10" class="data row7 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row8" class="row_heading level0 row8">28</th>
      <td id="T_e68b0_row8_col0" class="data row8 col0">Round 2: routing</td>
      <td id="T_e68b0_row8_col1" class="data row8 col1">T-009</td>
      <td id="T_e68b0_row8_col2" class="data row8 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row8_col3" class="data row8 col3">1166</td>
      <td id="T_e68b0_row8_col4" class="data row8 col4">0</td>
      <td id="T_e68b0_row8_col5" class="data row8 col5">0</td>
      <td id="T_e68b0_row8_col6" class="data row8 col6">1166</td>
      <td id="T_e68b0_row8_col7" class="data row8 col7">118</td>
      <td id="T_e68b0_row8_col8" class="data row8 col8">$0.00149</td>
      <td id="T_e68b0_row8_col9" class="data row8 col9">1.87</td>
      <td id="T_e68b0_row8_col10" class="data row8 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row9" class="row_heading level0 row9">29</th>
      <td id="T_e68b0_row9_col0" class="data row9 col0">Round 2: routing</td>
      <td id="T_e68b0_row9_col1" class="data row9 col1">T-010</td>
      <td id="T_e68b0_row9_col2" class="data row9 col2">gpt-5.4</td>
      <td id="T_e68b0_row9_col3" class="data row9 col3">1123</td>
      <td id="T_e68b0_row9_col4" class="data row9 col4">0</td>
      <td id="T_e68b0_row9_col5" class="data row9 col5">0</td>
      <td id="T_e68b0_row9_col6" class="data row9 col6">1123</td>
      <td id="T_e68b0_row9_col7" class="data row9 col7">165</td>
      <td id="T_e68b0_row9_col8" class="data row9 col8">$0.00537</td>
      <td id="T_e68b0_row9_col9" class="data row9 col9">2.48</td>
      <td id="T_e68b0_row9_col10" class="data row9 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row10" class="row_heading level0 row10">30</th>
      <td id="T_e68b0_row10_col0" class="data row10 col0">Round 3: caching</td>
      <td id="T_e68b0_row10_col1" class="data row10 col1">T-001</td>
      <td id="T_e68b0_row10_col2" class="data row10 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row10_col3" class="data row10 col3">2267</td>
      <td id="T_e68b0_row10_col4" class="data row10 col4">1779</td>
      <td id="T_e68b0_row10_col5" class="data row10 col5">1779</td>
      <td id="T_e68b0_row10_col6" class="data row10 col6">933</td>
      <td id="T_e68b0_row10_col7" class="data row10 col7">77</td>
      <td id="T_e68b0_row10_col8" class="data row10 col8">$0.00093</td>
      <td id="T_e68b0_row10_col9" class="data row10 col9">1.54</td>
      <td id="T_e68b0_row10_col10" class="data row10 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row11" class="row_heading level0 row11">31</th>
      <td id="T_e68b0_row11_col0" class="data row11 col0">Round 3: caching</td>
      <td id="T_e68b0_row11_col1" class="data row11 col1">T-002</td>
      <td id="T_e68b0_row11_col2" class="data row11 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row11_col3" class="data row11 col3">2338</td>
      <td id="T_e68b0_row11_col4" class="data row11 col4">1779</td>
      <td id="T_e68b0_row11_col5" class="data row11 col5">1779</td>
      <td id="T_e68b0_row11_col6" class="data row11 col6">1004</td>
      <td id="T_e68b0_row11_col7" class="data row11 col7">104</td>
      <td id="T_e68b0_row11_col8" class="data row11 col8">$0.00111</td>
      <td id="T_e68b0_row11_col9" class="data row11 col9">1.70</td>
      <td id="T_e68b0_row11_col10" class="data row11 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row12" class="row_heading level0 row12">32</th>
      <td id="T_e68b0_row12_col0" class="data row12 col0">Round 3: caching</td>
      <td id="T_e68b0_row12_col1" class="data row12 col1">T-003</td>
      <td id="T_e68b0_row12_col2" class="data row12 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row12_col3" class="data row12 col3">2361</td>
      <td id="T_e68b0_row12_col4" class="data row12 col4">1779</td>
      <td id="T_e68b0_row12_col5" class="data row12 col5">1779</td>
      <td id="T_e68b0_row12_col6" class="data row12 col6">1027</td>
      <td id="T_e68b0_row12_col7" class="data row12 col7">118</td>
      <td id="T_e68b0_row12_col8" class="data row12 col8">$0.00119</td>
      <td id="T_e68b0_row12_col9" class="data row12 col9">1.85</td>
      <td id="T_e68b0_row12_col10" class="data row12 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row13" class="row_heading level0 row13">33</th>
      <td id="T_e68b0_row13_col0" class="data row13 col0">Round 3: caching</td>
      <td id="T_e68b0_row13_col1" class="data row13 col1">T-004</td>
      <td id="T_e68b0_row13_col2" class="data row13 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row13_col3" class="data row13 col3">2349</td>
      <td id="T_e68b0_row13_col4" class="data row13 col4">1779</td>
      <td id="T_e68b0_row13_col5" class="data row13 col5">1779</td>
      <td id="T_e68b0_row13_col6" class="data row13 col6">1015</td>
      <td id="T_e68b0_row13_col7" class="data row13 col7">117</td>
      <td id="T_e68b0_row13_col8" class="data row13 col8">$0.00117</td>
      <td id="T_e68b0_row13_col9" class="data row13 col9">1.84</td>
      <td id="T_e68b0_row13_col10" class="data row13 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row14" class="row_heading level0 row14">34</th>
      <td id="T_e68b0_row14_col0" class="data row14 col0">Round 3: caching</td>
      <td id="T_e68b0_row14_col1" class="data row14 col1">T-005</td>
      <td id="T_e68b0_row14_col2" class="data row14 col2">gpt-5.4</td>
      <td id="T_e68b0_row14_col3" class="data row14 col3">2318</td>
      <td id="T_e68b0_row14_col4" class="data row14 col4">1779</td>
      <td id="T_e68b0_row14_col5" class="data row14 col5">1779</td>
      <td id="T_e68b0_row14_col6" class="data row14 col6">984</td>
      <td id="T_e68b0_row14_col7" class="data row14 col7">165</td>
      <td id="T_e68b0_row14_col8" class="data row14 col8">$0.00435</td>
      <td id="T_e68b0_row14_col9" class="data row14 col9">2.45</td>
      <td id="T_e68b0_row14_col10" class="data row14 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row15" class="row_heading level0 row15">35</th>
      <td id="T_e68b0_row15_col0" class="data row15 col0">Round 3: caching</td>
      <td id="T_e68b0_row15_col1" class="data row15 col1">T-006</td>
      <td id="T_e68b0_row15_col2" class="data row15 col2">gpt-5.4</td>
      <td id="T_e68b0_row15_col3" class="data row15 col3">2365</td>
      <td id="T_e68b0_row15_col4" class="data row15 col4">1779</td>
      <td id="T_e68b0_row15_col5" class="data row15 col5">1779</td>
      <td id="T_e68b0_row15_col6" class="data row15 col6">1031</td>
      <td id="T_e68b0_row15_col7" class="data row15 col7">158</td>
      <td id="T_e68b0_row15_col8" class="data row15 col8">$0.00437</td>
      <td id="T_e68b0_row15_col9" class="data row15 col9">2.46</td>
      <td id="T_e68b0_row15_col10" class="data row15 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row16" class="row_heading level0 row16">36</th>
      <td id="T_e68b0_row16_col0" class="data row16 col0">Round 3: caching</td>
      <td id="T_e68b0_row16_col1" class="data row16 col1">T-007</td>
      <td id="T_e68b0_row16_col2" class="data row16 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row16_col3" class="data row16 col3">2378</td>
      <td id="T_e68b0_row16_col4" class="data row16 col4">1779</td>
      <td id="T_e68b0_row16_col5" class="data row16 col5">1779</td>
      <td id="T_e68b0_row16_col6" class="data row16 col6">1044</td>
      <td id="T_e68b0_row16_col7" class="data row16 col7">100</td>
      <td id="T_e68b0_row16_col8" class="data row16 col8">$0.00112</td>
      <td id="T_e68b0_row16_col9" class="data row16 col9">1.70</td>
      <td id="T_e68b0_row16_col10" class="data row16 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row17" class="row_heading level0 row17">37</th>
      <td id="T_e68b0_row17_col0" class="data row17 col0">Round 3: caching</td>
      <td id="T_e68b0_row17_col1" class="data row17 col1">T-008</td>
      <td id="T_e68b0_row17_col2" class="data row17 col2">gpt-5.4</td>
      <td id="T_e68b0_row17_col3" class="data row17 col3">2379</td>
      <td id="T_e68b0_row17_col4" class="data row17 col4">1779</td>
      <td id="T_e68b0_row17_col5" class="data row17 col5">1779</td>
      <td id="T_e68b0_row17_col6" class="data row17 col6">1045</td>
      <td id="T_e68b0_row17_col7" class="data row17 col7">172</td>
      <td id="T_e68b0_row17_col8" class="data row17 col8">$0.00461</td>
      <td id="T_e68b0_row17_col9" class="data row17 col9">2.47</td>
      <td id="T_e68b0_row17_col10" class="data row17 col10">0.99</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row18" class="row_heading level0 row18">38</th>
      <td id="T_e68b0_row18_col0" class="data row18 col0">Round 3: caching</td>
      <td id="T_e68b0_row18_col1" class="data row18 col1">T-009</td>
      <td id="T_e68b0_row18_col2" class="data row18 col2">gpt-5.4-mini</td>
      <td id="T_e68b0_row18_col3" class="data row18 col3">2365</td>
      <td id="T_e68b0_row18_col4" class="data row18 col4">1779</td>
      <td id="T_e68b0_row18_col5" class="data row18 col5">1779</td>
      <td id="T_e68b0_row18_col6" class="data row18 col6">1031</td>
      <td id="T_e68b0_row18_col7" class="data row18 col7">118</td>
      <td id="T_e68b0_row18_col8" class="data row18 col8">$0.00119</td>
      <td id="T_e68b0_row18_col9" class="data row18 col9">1.85</td>
      <td id="T_e68b0_row18_col10" class="data row18 col10">0.98</td>
    </tr>
    <tr>
      <th id="T_e68b0_level0_row19" class="row_heading level0 row19">39</th>
      <td id="T_e68b0_row19_col0" class="data row19 col0">Round 3: caching</td>
      <td id="T_e68b0_row19_col1" class="data row19 col1">T-010</td>
      <td id="T_e68b0_row19_col2" class="data row19 col2">gpt-5.4</td>
      <td id="T_e68b0_row19_col3" class="data row19 col3">2322</td>
      <td id="T_e68b0_row19_col4" class="data row19 col4">1779</td>
      <td id="T_e68b0_row19_col5" class="data row19 col5">1779</td>
      <td id="T_e68b0_row19_col6" class="data row19 col6">988</td>
      <td id="T_e68b0_row19_col7" class="data row19 col7">165</td>
      <td id="T_e68b0_row19_col8" class="data row19 col8">$0.00436</td>
      <td id="T_e68b0_row19_col9" class="data row19 col9">2.46</td>
      <td id="T_e68b0_row19_col10" class="data row19 col10">0.99</td>
    </tr>
  </tbody>
</table>

## Optimization round 4: split the workflow

Keep classification, necessary lookups, the resolution or escalation decision, and the customer response in the synchronous path. Move QA, tags, internal summaries, audits, and reporting to follow-up work when they do not change the immediate outcome.

Default or priority processing can serve latency-sensitive requests. Flex trades lower cost for slower responses and occasional resource unavailability; confirm model support and handle timeouts or unavailable capacity. Batch suits offline jobs with a `24h` completion window. Background mode makes a request asynchronous, but does not itself provide a pricing discount.


```python
sync_request = {
    "model": "gpt-5.4-mini",
    "instructions": CACHE_FRIENDLY_PROMPT,
    "tools": SLIM_TOOLS,
    "tool_choice": allowed_tool_choice(["lookup_order", "lookup_policy"], mode="auto"),
    "input": "Customer says order O-1002 arrived cracked. Resolve or escalate.",
    "reasoning": {"effort": "low"},
    "text": {"verbosity": "low"},
    "max_output_tokens": 260,
    "service_tier": "default",
    "prompt_cache_key": "support_damaged_delivery_v1",
}

background_flex_request = background_followup_request(EVAL_SET[1])

print("Synchronous customer-facing request:")
print(json.dumps(sync_request, indent=2)[:1800] + "\n...")
print("\nFollow-up flex request:")
print(json.dumps(background_flex_request, indent=2)[:1600] + "\n...")
```

```text
Synchronous customer-facing request:
{
  "model": "gpt-5.4-mini",
  "instructions": "Role: E-commerce support assistant.\nConstraints: Be concise, policy-compliant, and explicit about next steps. Do not disclose internal data.\nEscalate: duplicate charges, account access without verification, high-value disputes, and refunds outside the window.\nOutput shape: customer_message, resolution_type, escalate, internal_tags.\nTool contract: tool definitions are stable across requests; restrict callable tools with tool_choice.allowed_tools.\nVersion: support-agent-optimization-v1.\n\nStable support playbook digest:\n- Shipping delays: provide status, ETA, and tracking next steps; do not refund solely for short carrier delays.\n- Delivered-not-received: verify delivery details, ask the customer to check common locations, and start carrier trace steps when appropriate.\n- Damaged delivery: request photo evidence before offering replacement or refund; high-value damaged items require human review.\n- Refunds: standard returnable items are eligible within 30 days; outside-window or high-value disputes require human review.\n- Billing: duplicate-charge reports require billing review; acknowledge and escalate, but do not promise a completed refund.\n- Account access: when identity is not verified, escalate to account security; do not change credentials or contact information in chat.\n- Customer messages must be concise, policy-compliant, and explicit about next steps.\n- Internal notes, raw carrier payloads, CRM audit logs, and policy appendices must never be exposed to the customer.\nStable support playbook digest:\n- Shipping delays: provide status, ETA, and tracking next steps; do not refund solely for short carrier delays.\n- Delivered-not-received: verify delivery details, ask the customer to check common location
...

Follow-up flex request:
{
  "model": "gpt-5.4-nano",
  "input": "{\"ticket\": {\"ticket_id\": \"T-002\", \"customer_id\": \"C-200\", \"message\": \"My blender arrived cracked. Order O-1002. Can you replace it?\", \"intent\": \"damaged_delivery\", \"order_id\": \"O-1002\", \"risk\": \"medium\", \"difficulty\": \"routine_policy\", \"must_escalate\": false, \"expected_policy\": \"damaged_delivery\", \"expected_tools\": [\"lookup_order\", \"lookup_policy\"], \"expected_action\": \"request_photo_then_offer_replacement\", \"expected_resolution_type\": \"resolved_next_step\", \"expected_customer_response_contains\": [\"photo\", \"replacement\"], \"forbidden_response_claims\": [\"refund completed\", \"no photo needed\"]}, \"policy\": \"If damage is reported within 7 days of delivery, ask for a photo and offer replacement or refund after evidence is collected. High-value damaged items over $1,000 require human review before promising a refund or replacement.\"}",
  "reasoning": {
    "effort": "low"
  },
  "text": {
    "verbosity": "low"
  },
  "max_output_tokens": 160,
  "service_tier": "flex"
}
...
```

```python
batch_requests = []
for ticket in EVAL_SET:
    batch_requests.append(
        {
            "custom_id": f"qa-{ticket['ticket_id']}",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": "gpt-5.4-nano",
                "instructions": "Return concise internal support QA tags and a one-sentence summary.",
                "input": json.dumps(ticket),
                "reasoning": {"effort": "low"},
                "text": {"verbosity": "low"},
                "max_output_tokens": 160,
            },
        }
    )

from pathlib import Path

Path("outputs").mkdir(exist_ok=True)
batch_file_path = "outputs/nightly_support_qa_batch.jsonl"
with open(batch_file_path, "w") as f:
    f.writelines(json.dumps(row) + "\n" for row in batch_requests)

print(f"Wrote {len(batch_requests)} example batch rows to {batch_file_path}")
print(json.dumps(batch_requests[0], indent=2))
```

```text
Wrote 10 example batch rows to outputs/nightly_support_qa_batch.jsonl
{
  "custom_id": "qa-T-001",
  "method": "POST",
  "url": "/v1/responses",
  "body": {
    "model": "gpt-5.4-nano",
    "instructions": "Return concise internal support QA tags and a one-sentence summary.",
    "input": "{\"ticket_id\": \"T-001\", \"customer_id\": \"C-100\", \"message\": \"Where is order O-1001? It was supposed to arrive yesterday.\", \"intent\": \"order_status\", \"order_id\": \"O-1001\", \"risk\": \"low\", \"difficulty\": \"simple_lookup\", \"must_escalate\": false, \"expected_policy\": \"shipping\", \"expected_tools\": [\"lookup_order\"], \"expected_action\": \"provide_status_eta\", \"expected_resolution_type\": \"resolved\", \"expected_customer_response_contains\": [\"in transit\", \"tomorrow\"], \"forbidden_response_claims\": [\"refund completed\", \"replacement opened\"]}",
    "reasoning": {
      "effort": "low"
    },
    "text": {
      "verbosity": "low"
    },
    "max_output_tokens": 160
  }
}
```

```python
batch_submission_example = '''
batch_input_file = client.files.create(
    file=open(batch_file_path, "rb"),
    purpose="batch",
)

batch = client.batches.create(
    input_file_id=batch_input_file.id,
    endpoint="/v1/responses",
    completion_window="24h",
    metadata={"description": "nightly support QA tags"},
)
'''

print(batch_submission_example)
```

```text

batch_input_file = client.files.create(
    file=open(batch_file_path, "rb"),
    purpose="batch",
)

batch = client.batches.create(
    input_file_id=batch_input_file.id,
    endpoint="/v1/responses",
    completion_window="24h",
    metadata={"description": "nightly support QA tags"},
)
```

```python
split_view = traces[traces["variant"].isin(["03_prompt_caching", "04_split_workflow"])]
display(
    split_view[
        [
            "variant_label",
            "ticket_id",
            "model",
            "tool_calls",
            "sync_tokens",
            "total_tokens",
            "background_tokens",
            "latency_s",
            "sync_cost_usd",
            "background_cost_usd",
            "cost_usd",
            "quality_score",
        ]
    ].style.format(
        {
            "sync_cost_usd": "${:.5f}",
            "background_cost_usd": "${:.5f}",
            "cost_usd": "${:.5f}",
            "quality_score": "{:.2f}",
            "latency_s": "{:.2f}",
        }
    )
)
```

<table id="T_acc56">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_acc56_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_acc56_level0_col1" class="col_heading level0 col1">ticket_id</th>
      <th id="T_acc56_level0_col2" class="col_heading level0 col2">model</th>
      <th id="T_acc56_level0_col3" class="col_heading level0 col3">tool_calls</th>
      <th id="T_acc56_level0_col4" class="col_heading level0 col4">sync_tokens</th>
      <th id="T_acc56_level0_col5" class="col_heading level0 col5">total_tokens</th>
      <th id="T_acc56_level0_col6" class="col_heading level0 col6">background_tokens</th>
      <th id="T_acc56_level0_col7" class="col_heading level0 col7">latency_s</th>
      <th id="T_acc56_level0_col8" class="col_heading level0 col8">sync_cost_usd</th>
      <th id="T_acc56_level0_col9" class="col_heading level0 col9">background_cost_usd</th>
      <th id="T_acc56_level0_col10" class="col_heading level0 col10">cost_usd</th>
      <th id="T_acc56_level0_col11" class="col_heading level0 col11">quality_score</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_acc56_level0_row0" class="row_heading level0 row0">30</th>
      <td id="T_acc56_row0_col0" class="data row0 col0">Round 3: caching</td>
      <td id="T_acc56_row0_col1" class="data row0 col1">T-001</td>
      <td id="T_acc56_row0_col2" class="data row0 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row0_col3" class="data row0 col3">1</td>
      <td id="T_acc56_row0_col4" class="data row0 col4">2552</td>
      <td id="T_acc56_row0_col5" class="data row0 col5">2552</td>
      <td id="T_acc56_row0_col6" class="data row0 col6">0</td>
      <td id="T_acc56_row0_col7" class="data row0 col7">1.54</td>
      <td id="T_acc56_row0_col8" class="data row0 col8">$0.00093</td>
      <td id="T_acc56_row0_col9" class="data row0 col9">$0.00000</td>
      <td id="T_acc56_row0_col10" class="data row0 col10">$0.00093</td>
      <td id="T_acc56_row0_col11" class="data row0 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row1" class="row_heading level0 row1">31</th>
      <td id="T_acc56_row1_col0" class="data row1 col0">Round 3: caching</td>
      <td id="T_acc56_row1_col1" class="data row1 col1">T-002</td>
      <td id="T_acc56_row1_col2" class="data row1 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row1_col3" class="data row1 col3">2</td>
      <td id="T_acc56_row1_col4" class="data row1 col4">2650</td>
      <td id="T_acc56_row1_col5" class="data row1 col5">2650</td>
      <td id="T_acc56_row1_col6" class="data row1 col6">0</td>
      <td id="T_acc56_row1_col7" class="data row1 col7">1.70</td>
      <td id="T_acc56_row1_col8" class="data row1 col8">$0.00111</td>
      <td id="T_acc56_row1_col9" class="data row1 col9">$0.00000</td>
      <td id="T_acc56_row1_col10" class="data row1 col10">$0.00111</td>
      <td id="T_acc56_row1_col11" class="data row1 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row2" class="row_heading level0 row2">32</th>
      <td id="T_acc56_row2_col0" class="data row2 col0">Round 3: caching</td>
      <td id="T_acc56_row2_col1" class="data row2 col1">T-003</td>
      <td id="T_acc56_row2_col2" class="data row2 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row2_col3" class="data row2 col3">3</td>
      <td id="T_acc56_row2_col4" class="data row2 col4">2689</td>
      <td id="T_acc56_row2_col5" class="data row2 col5">2689</td>
      <td id="T_acc56_row2_col6" class="data row2 col6">0</td>
      <td id="T_acc56_row2_col7" class="data row2 col7">1.85</td>
      <td id="T_acc56_row2_col8" class="data row2 col8">$0.00119</td>
      <td id="T_acc56_row2_col9" class="data row2 col9">$0.00000</td>
      <td id="T_acc56_row2_col10" class="data row2 col10">$0.00119</td>
      <td id="T_acc56_row2_col11" class="data row2 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row3" class="row_heading level0 row3">33</th>
      <td id="T_acc56_row3_col0" class="data row3 col0">Round 3: caching</td>
      <td id="T_acc56_row3_col1" class="data row3 col1">T-004</td>
      <td id="T_acc56_row3_col2" class="data row3 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row3_col3" class="data row3 col3">3</td>
      <td id="T_acc56_row3_col4" class="data row3 col4">2673</td>
      <td id="T_acc56_row3_col5" class="data row3 col5">2673</td>
      <td id="T_acc56_row3_col6" class="data row3 col6">0</td>
      <td id="T_acc56_row3_col7" class="data row3 col7">1.84</td>
      <td id="T_acc56_row3_col8" class="data row3 col8">$0.00117</td>
      <td id="T_acc56_row3_col9" class="data row3 col9">$0.00000</td>
      <td id="T_acc56_row3_col10" class="data row3 col10">$0.00117</td>
      <td id="T_acc56_row3_col11" class="data row3 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row4" class="row_heading level0 row4">34</th>
      <td id="T_acc56_row4_col0" class="data row4 col0">Round 3: caching</td>
      <td id="T_acc56_row4_col1" class="data row4 col1">T-005</td>
      <td id="T_acc56_row4_col2" class="data row4 col2">gpt-5.4</td>
      <td id="T_acc56_row4_col3" class="data row4 col3">3</td>
      <td id="T_acc56_row4_col4" class="data row4 col4">2689</td>
      <td id="T_acc56_row4_col5" class="data row4 col5">2689</td>
      <td id="T_acc56_row4_col6" class="data row4 col6">0</td>
      <td id="T_acc56_row4_col7" class="data row4 col7">2.45</td>
      <td id="T_acc56_row4_col8" class="data row4 col8">$0.00435</td>
      <td id="T_acc56_row4_col9" class="data row4 col9">$0.00000</td>
      <td id="T_acc56_row4_col10" class="data row4 col10">$0.00435</td>
      <td id="T_acc56_row4_col11" class="data row4 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row5" class="row_heading level0 row5">35</th>
      <td id="T_acc56_row5_col0" class="data row5 col0">Round 3: caching</td>
      <td id="T_acc56_row5_col1" class="data row5 col1">T-006</td>
      <td id="T_acc56_row5_col2" class="data row5 col2">gpt-5.4</td>
      <td id="T_acc56_row5_col3" class="data row5 col3">3</td>
      <td id="T_acc56_row5_col4" class="data row5 col4">2735</td>
      <td id="T_acc56_row5_col5" class="data row5 col5">2735</td>
      <td id="T_acc56_row5_col6" class="data row5 col6">0</td>
      <td id="T_acc56_row5_col7" class="data row5 col7">2.46</td>
      <td id="T_acc56_row5_col8" class="data row5 col8">$0.00437</td>
      <td id="T_acc56_row5_col9" class="data row5 col9">$0.00000</td>
      <td id="T_acc56_row5_col10" class="data row5 col10">$0.00437</td>
      <td id="T_acc56_row5_col11" class="data row5 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row6" class="row_heading level0 row6">36</th>
      <td id="T_acc56_row6_col0" class="data row6 col0">Round 3: caching</td>
      <td id="T_acc56_row6_col1" class="data row6 col1">T-007</td>
      <td id="T_acc56_row6_col2" class="data row6 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row6_col3" class="data row6 col3">2</td>
      <td id="T_acc56_row6_col4" class="data row6 col4">2691</td>
      <td id="T_acc56_row6_col5" class="data row6 col5">2691</td>
      <td id="T_acc56_row6_col6" class="data row6 col6">0</td>
      <td id="T_acc56_row6_col7" class="data row6 col7">1.70</td>
      <td id="T_acc56_row6_col8" class="data row6 col8">$0.00112</td>
      <td id="T_acc56_row6_col9" class="data row6 col9">$0.00000</td>
      <td id="T_acc56_row6_col10" class="data row6 col10">$0.00112</td>
      <td id="T_acc56_row6_col11" class="data row6 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row7" class="row_heading level0 row7">37</th>
      <td id="T_acc56_row7_col0" class="data row7 col0">Round 3: caching</td>
      <td id="T_acc56_row7_col1" class="data row7 col1">T-008</td>
      <td id="T_acc56_row7_col2" class="data row7 col2">gpt-5.4</td>
      <td id="T_acc56_row7_col3" class="data row7 col3">3</td>
      <td id="T_acc56_row7_col4" class="data row7 col4">2769</td>
      <td id="T_acc56_row7_col5" class="data row7 col5">2769</td>
      <td id="T_acc56_row7_col6" class="data row7 col6">0</td>
      <td id="T_acc56_row7_col7" class="data row7 col7">2.47</td>
      <td id="T_acc56_row7_col8" class="data row7 col8">$0.00461</td>
      <td id="T_acc56_row7_col9" class="data row7 col9">$0.00000</td>
      <td id="T_acc56_row7_col10" class="data row7 col10">$0.00461</td>
      <td id="T_acc56_row7_col11" class="data row7 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row8" class="row_heading level0 row8">38</th>
      <td id="T_acc56_row8_col0" class="data row8 col0">Round 3: caching</td>
      <td id="T_acc56_row8_col1" class="data row8 col1">T-009</td>
      <td id="T_acc56_row8_col2" class="data row8 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row8_col3" class="data row8 col3">3</td>
      <td id="T_acc56_row8_col4" class="data row8 col4">2697</td>
      <td id="T_acc56_row8_col5" class="data row8 col5">2697</td>
      <td id="T_acc56_row8_col6" class="data row8 col6">0</td>
      <td id="T_acc56_row8_col7" class="data row8 col7">1.85</td>
      <td id="T_acc56_row8_col8" class="data row8 col8">$0.00119</td>
      <td id="T_acc56_row8_col9" class="data row8 col9">$0.00000</td>
      <td id="T_acc56_row8_col10" class="data row8 col10">$0.00119</td>
      <td id="T_acc56_row8_col11" class="data row8 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row9" class="row_heading level0 row9">39</th>
      <td id="T_acc56_row9_col0" class="data row9 col0">Round 3: caching</td>
      <td id="T_acc56_row9_col1" class="data row9 col1">T-010</td>
      <td id="T_acc56_row9_col2" class="data row9 col2">gpt-5.4</td>
      <td id="T_acc56_row9_col3" class="data row9 col3">3</td>
      <td id="T_acc56_row9_col4" class="data row9 col4">2696</td>
      <td id="T_acc56_row9_col5" class="data row9 col5">2696</td>
      <td id="T_acc56_row9_col6" class="data row9 col6">0</td>
      <td id="T_acc56_row9_col7" class="data row9 col7">2.46</td>
      <td id="T_acc56_row9_col8" class="data row9 col8">$0.00436</td>
      <td id="T_acc56_row9_col9" class="data row9 col9">$0.00000</td>
      <td id="T_acc56_row9_col10" class="data row9 col10">$0.00436</td>
      <td id="T_acc56_row9_col11" class="data row9 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row10" class="row_heading level0 row10">40</th>
      <td id="T_acc56_row10_col0" class="data row10 col0">Round 4: split workflow</td>
      <td id="T_acc56_row10_col1" class="data row10 col1">T-001</td>
      <td id="T_acc56_row10_col2" class="data row10 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row10_col3" class="data row10 col3">1</td>
      <td id="T_acc56_row10_col4" class="data row10 col4">2287</td>
      <td id="T_acc56_row10_col5" class="data row10 col5">2867</td>
      <td id="T_acc56_row10_col6" class="data row10 col6">580</td>
      <td id="T_acc56_row10_col7" class="data row10 col7">1.10</td>
      <td id="T_acc56_row10_col8" class="data row10 col8">$0.00071</td>
      <td id="T_acc56_row10_col9" class="data row10 col9">$0.00011</td>
      <td id="T_acc56_row10_col10" class="data row10 col10">$0.00082</td>
      <td id="T_acc56_row10_col11" class="data row10 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row11" class="row_heading level0 row11">41</th>
      <td id="T_acc56_row11_col0" class="data row11 col0">Round 4: split workflow</td>
      <td id="T_acc56_row11_col1" class="data row11 col1">T-002</td>
      <td id="T_acc56_row11_col2" class="data row11 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row11_col3" class="data row11 col3">2</td>
      <td id="T_acc56_row11_col4" class="data row11 col4">2381</td>
      <td id="T_acc56_row11_col5" class="data row11 col5">2940</td>
      <td id="T_acc56_row11_col6" class="data row11 col6">559</td>
      <td id="T_acc56_row11_col7" class="data row11 col7">1.26</td>
      <td id="T_acc56_row11_col8" class="data row11 col8">$0.00087</td>
      <td id="T_acc56_row11_col9" class="data row11 col9">$0.00010</td>
      <td id="T_acc56_row11_col10" class="data row11 col10">$0.00097</td>
      <td id="T_acc56_row11_col11" class="data row11 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row12" class="row_heading level0 row12">42</th>
      <td id="T_acc56_row12_col0" class="data row12 col0">Round 4: split workflow</td>
      <td id="T_acc56_row12_col1" class="data row12 col1">T-003</td>
      <td id="T_acc56_row12_col2" class="data row12 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row12_col3" class="data row12 col3">3</td>
      <td id="T_acc56_row12_col4" class="data row12 col4">2418</td>
      <td id="T_acc56_row12_col5" class="data row12 col5">2978</td>
      <td id="T_acc56_row12_col6" class="data row12 col6">560</td>
      <td id="T_acc56_row12_col7" class="data row12 col7">1.41</td>
      <td id="T_acc56_row12_col8" class="data row12 col8">$0.00094</td>
      <td id="T_acc56_row12_col9" class="data row12 col9">$0.00010</td>
      <td id="T_acc56_row12_col10" class="data row12 col10">$0.00105</td>
      <td id="T_acc56_row12_col11" class="data row12 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row13" class="row_heading level0 row13">43</th>
      <td id="T_acc56_row13_col0" class="data row13 col0">Round 4: split workflow</td>
      <td id="T_acc56_row13_col1" class="data row13 col1">T-004</td>
      <td id="T_acc56_row13_col2" class="data row13 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row13_col3" class="data row13 col3">3</td>
      <td id="T_acc56_row13_col4" class="data row13 col4">2401</td>
      <td id="T_acc56_row13_col5" class="data row13 col5">2942</td>
      <td id="T_acc56_row13_col6" class="data row13 col6">541</td>
      <td id="T_acc56_row13_col7" class="data row13 col7">1.41</td>
      <td id="T_acc56_row13_col8" class="data row13 col8">$0.00092</td>
      <td id="T_acc56_row13_col9" class="data row13 col9">$0.00010</td>
      <td id="T_acc56_row13_col10" class="data row13 col10">$0.00103</td>
      <td id="T_acc56_row13_col11" class="data row13 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row14" class="row_heading level0 row14">44</th>
      <td id="T_acc56_row14_col0" class="data row14 col0">Round 4: split workflow</td>
      <td id="T_acc56_row14_col1" class="data row14 col1">T-005</td>
      <td id="T_acc56_row14_col2" class="data row14 col2">gpt-5.4</td>
      <td id="T_acc56_row14_col3" class="data row14 col3">3</td>
      <td id="T_acc56_row14_col4" class="data row14 col4">2413</td>
      <td id="T_acc56_row14_col5" class="data row14 col5">2956</td>
      <td id="T_acc56_row14_col6" class="data row14 col6">543</td>
      <td id="T_acc56_row14_col7" class="data row14 col7">2.02</td>
      <td id="T_acc56_row14_col8" class="data row14 col8">$0.00346</td>
      <td id="T_acc56_row14_col9" class="data row14 col9">$0.00010</td>
      <td id="T_acc56_row14_col10" class="data row14 col10">$0.00356</td>
      <td id="T_acc56_row14_col11" class="data row14 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row15" class="row_heading level0 row15">45</th>
      <td id="T_acc56_row15_col0" class="data row15 col0">Round 4: split workflow</td>
      <td id="T_acc56_row15_col1" class="data row15 col1">T-006</td>
      <td id="T_acc56_row15_col2" class="data row15 col2">gpt-5.4</td>
      <td id="T_acc56_row15_col3" class="data row15 col3">3</td>
      <td id="T_acc56_row15_col4" class="data row15 col4">2459</td>
      <td id="T_acc56_row15_col5" class="data row15 col5">3019</td>
      <td id="T_acc56_row15_col6" class="data row15 col6">560</td>
      <td id="T_acc56_row15_col7" class="data row15 col7">2.03</td>
      <td id="T_acc56_row15_col8" class="data row15 col8">$0.00348</td>
      <td id="T_acc56_row15_col9" class="data row15 col9">$0.00010</td>
      <td id="T_acc56_row15_col10" class="data row15 col10">$0.00358</td>
      <td id="T_acc56_row15_col11" class="data row15 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row16" class="row_heading level0 row16">46</th>
      <td id="T_acc56_row16_col0" class="data row16 col0">Round 4: split workflow</td>
      <td id="T_acc56_row16_col1" class="data row16 col1">T-007</td>
      <td id="T_acc56_row16_col2" class="data row16 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row16_col3" class="data row16 col3">2</td>
      <td id="T_acc56_row16_col4" class="data row16 col4">2422</td>
      <td id="T_acc56_row16_col5" class="data row16 col5">3023</td>
      <td id="T_acc56_row16_col6" class="data row16 col6">601</td>
      <td id="T_acc56_row16_col7" class="data row16 col7">1.27</td>
      <td id="T_acc56_row16_col8" class="data row16 col8">$0.00088</td>
      <td id="T_acc56_row16_col9" class="data row16 col9">$0.00011</td>
      <td id="T_acc56_row16_col10" class="data row16 col10">$0.00099</td>
      <td id="T_acc56_row16_col11" class="data row16 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row17" class="row_heading level0 row17">47</th>
      <td id="T_acc56_row17_col0" class="data row17 col0">Round 4: split workflow</td>
      <td id="T_acc56_row17_col1" class="data row17 col1">T-008</td>
      <td id="T_acc56_row17_col2" class="data row17 col2">gpt-5.4</td>
      <td id="T_acc56_row17_col3" class="data row17 col3">3</td>
      <td id="T_acc56_row17_col4" class="data row17 col4">2492</td>
      <td id="T_acc56_row17_col5" class="data row17 col5">3063</td>
      <td id="T_acc56_row17_col6" class="data row17 col6">571</td>
      <td id="T_acc56_row17_col7" class="data row17 col7">2.03</td>
      <td id="T_acc56_row17_col8" class="data row17 col8">$0.00371</td>
      <td id="T_acc56_row17_col9" class="data row17 col9">$0.00010</td>
      <td id="T_acc56_row17_col10" class="data row17 col10">$0.00381</td>
      <td id="T_acc56_row17_col11" class="data row17 col11">0.99</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row18" class="row_heading level0 row18">48</th>
      <td id="T_acc56_row18_col0" class="data row18 col0">Round 4: split workflow</td>
      <td id="T_acc56_row18_col1" class="data row18 col1">T-009</td>
      <td id="T_acc56_row18_col2" class="data row18 col2">gpt-5.4-mini</td>
      <td id="T_acc56_row18_col3" class="data row18 col3">3</td>
      <td id="T_acc56_row18_col4" class="data row18 col4">2426</td>
      <td id="T_acc56_row18_col5" class="data row18 col5">2988</td>
      <td id="T_acc56_row18_col6" class="data row18 col6">562</td>
      <td id="T_acc56_row18_col7" class="data row18 col7">1.41</td>
      <td id="T_acc56_row18_col8" class="data row18 col8">$0.00095</td>
      <td id="T_acc56_row18_col9" class="data row18 col9">$0.00010</td>
      <td id="T_acc56_row18_col10" class="data row18 col10">$0.00105</td>
      <td id="T_acc56_row18_col11" class="data row18 col11">0.98</td>
    </tr>
    <tr>
      <th id="T_acc56_level0_row19" class="row_heading level0 row19">49</th>
      <td id="T_acc56_row19_col0" class="data row19 col0">Round 4: split workflow</td>
      <td id="T_acc56_row19_col1" class="data row19 col1">T-010</td>
      <td id="T_acc56_row19_col2" class="data row19 col2">gpt-5.4</td>
      <td id="T_acc56_row19_col3" class="data row19 col3">3</td>
      <td id="T_acc56_row19_col4" class="data row19 col4">2420</td>
      <td id="T_acc56_row19_col5" class="data row19 col5">2962</td>
      <td id="T_acc56_row19_col6" class="data row19 col6">542</td>
      <td id="T_acc56_row19_col7" class="data row19 col7">2.02</td>
      <td id="T_acc56_row19_col8" class="data row19 col8">$0.00347</td>
      <td id="T_acc56_row19_col9" class="data row19 col9">$0.00010</td>
      <td id="T_acc56_row19_col10" class="data row19 col10">$0.00357</td>
      <td id="T_acc56_row19_col11" class="data row19 col11">0.99</td>
    </tr>
  </tbody>
</table>

## Tradeoffs and scenario mapping

There is no universal best configuration. The sweet spot depends on traffic shape, customer promise, policy risk, cache hit rate, tool latency, observability maturity, and how much work can move out of the synchronous path.

The important tradeoffs for support agents are:

| Constraint | Pushes you toward | Watch out for |
|---|---|---|
| High policy or account-security risk | Larger model on high-risk paths, stricter escalation, judge evals | Over-escalation can hurt customer experience and support capacity |
| High ticket volume with repeated workflows | Stable prefixes, prompt caching, smaller models, Batch for follow-up work | Cache misses on large prefixes can add latency |
| Low latency customer promise | Short prompts, slim tool payloads, routing, async follow-up work | Too much routing can add overhead if the task is already simple |
| Strict cost target | Nano/mini for triage and routine paths, output caps, flex or Batch for offline work | Cost-only tuning can remove safeguards if quality gates are weak |
| Messy tools or unreliable data | Fewer tool calls, validated payloads, fallbacks, escalation on tool failure | Blindly shrinking context can remove the evidence needed for policy decisions |
| Premium or regulated support | Higher quality floor, lower escalation threshold, more audit metadata offline | More synchronous review increases latency and cost |
| Seasonal bursts | Cache-friendly requests, queue-aware service tiers, async analytics | Peak traffic can reduce cache effectiveness if routing keys are too fragmented |

The table below maps common operating scenarios to candidate configurations. Treat this as a design aid: choose the cheapest configuration that clears the quality, latency, and operational constraints for that scenario.


### Candidate architecture combinations

This table compares candidate agent architectures for the same customer-support use case. It uses the notebook's mock eval set and deterministic dry-run simulation metrics, not live API traces. Use the relative differences to understand tradeoffs; replace these metrics with production trace data before making deployment decisions.


```python
from scenarios import (
    ARCHITECTURE_OPTIONS,
    OPERATING_SCENARIOS,
    architecture_metrics,
    scenario_fit_score,
)

architecture_rows = [
    {"architecture": key, **option, **architecture_metrics(key, summary)}
    for key, option in ARCHITECTURE_OPTIONS.items()
]
architecture_df = pd.DataFrame(architecture_rows)
print("Table: Candidate architecture combinations (mock eval set + deterministic dry-run metrics)")
display(
    architecture_df[
        [
            "label",
            "models",
            "tools",
            "cache",
            "workflow",
            "quality",
            "policy_compliance",
            "p50_latency_s",
            "monthly_cost_at_100k_tickets",
            "best_for",
        ]
    ].style.format(
        {
            "quality": "{:.2f}",
            "policy_compliance": "{:.0%}",
            "p50_latency_s": "{:.2f}",
            "monthly_cost_at_100k_tickets": "${:,.0f}",
        }
    )
)
```

```text
Table: Candidate architecture combinations (mock eval set + deterministic dry-run metrics)
```

<table id="T_681e7">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_681e7_level0_col0" class="col_heading level0 col0">label</th>
      <th id="T_681e7_level0_col1" class="col_heading level0 col1">models</th>
      <th id="T_681e7_level0_col2" class="col_heading level0 col2">tools</th>
      <th id="T_681e7_level0_col3" class="col_heading level0 col3">cache</th>
      <th id="T_681e7_level0_col4" class="col_heading level0 col4">workflow</th>
      <th id="T_681e7_level0_col5" class="col_heading level0 col5">quality</th>
      <th id="T_681e7_level0_col6" class="col_heading level0 col6">policy_compliance</th>
      <th id="T_681e7_level0_col7" class="col_heading level0 col7">p50_latency_s</th>
      <th id="T_681e7_level0_col8" class="col_heading level0 col8">monthly_cost_at_100k_tickets</th>
      <th id="T_681e7_level0_col9" class="col_heading level0 col9">best_for</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_681e7_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_681e7_row0_col0" class="data row0 col0">One broad agent</td>
      <td id="T_681e7_row0_col1" class="data row0 col1">gpt-5.4 for every step</td>
      <td id="T_681e7_row0_col2" class="data row0 col2">all tools exposed</td>
      <td id="T_681e7_row0_col3" class="data row0 col3">none</td>
      <td id="T_681e7_row0_col4" class="data row0 col4">all work synchronous</td>
      <td id="T_681e7_row0_col5" class="data row0 col5">0.51</td>
      <td id="T_681e7_row0_col6" class="data row0 col6">10%</td>
      <td id="T_681e7_row0_col7" class="data row0 col7">4.88</td>
      <td id="T_681e7_row0_col8" class="data row0 col8">$3,813</td>
      <td id="T_681e7_row0_col9" class="data row0 col9">prototype smell test only</td>
    </tr>
    <tr>
      <th id="T_681e7_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_681e7_row1_col0" class="data row1 col0">Controlled full model</td>
      <td id="T_681e7_row1_col1" class="data row1 col1">gpt-5.4 for resolution</td>
      <td id="T_681e7_row1_col2" class="data row1 col2">allowed tools by routed path</td>
      <td id="T_681e7_row1_col3" class="data row1 col3">none</td>
      <td id="T_681e7_row1_col4" class="data row1 col4">some follow-up still synchronous</td>
      <td id="T_681e7_row1_col5" class="data row1 col5">0.98</td>
      <td id="T_681e7_row1_col6" class="data row1 col6">100%</td>
      <td id="T_681e7_row1_col7" class="data row1 col7">2.32</td>
      <td id="T_681e7_row1_col8" class="data row1 col8">$512</td>
      <td id="T_681e7_row1_col9" class="data row1 col9">high-risk launch or low confidence in routing/model mix</td>
    </tr>
    <tr>
      <th id="T_681e7_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_681e7_row2_col0" class="data row2 col0">Routed, no cache</td>
      <td id="T_681e7_row2_col1" class="data row2 col1">nano triage, mini routine, gpt-5.4 high risk</td>
      <td id="T_681e7_row2_col2" class="data row2 col2">allowed tools by routed path</td>
      <td id="T_681e7_row2_col3" class="data row2 col3">none</td>
      <td id="T_681e7_row2_col4" class="data row2 col4">some follow-up still synchronous</td>
      <td id="T_681e7_row2_col5" class="data row2 col5">0.98</td>
      <td id="T_681e7_row2_col6" class="data row2 col6">100%</td>
      <td id="T_681e7_row2_col7" class="data row2 col7">1.87</td>
      <td id="T_681e7_row2_col8" class="data row2 col8">$302</td>
      <td id="T_681e7_row2_col9" class="data row2 col9">mixed ticket queues with moderate repeat traffic</td>
    </tr>
    <tr>
      <th id="T_681e7_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_681e7_row3_col0" class="data row3 col0">Routed split, no cache</td>
      <td id="T_681e7_row3_col1" class="data row3 col1">nano triage/tags, mini routine, gpt-5.4 high risk</td>
      <td id="T_681e7_row3_col2" class="data row3 col2">allowed tools by routed path</td>
      <td id="T_681e7_row3_col3" class="data row3 col3">none</td>
      <td id="T_681e7_row3_col4" class="data row3 col4">customer path sync, QA/tags/reporting async</td>
      <td id="T_681e7_row3_col5" class="data row3 col5">0.98</td>
      <td id="T_681e7_row3_col6" class="data row3 col6">100%</td>
      <td id="T_681e7_row3_col7" class="data row3 col7">1.57</td>
      <td id="T_681e7_row3_col8" class="data row3 col8">$285</td>
      <td id="T_681e7_row3_col9" class="data row3 col9">low-repeat queues that still need async follow-up work</td>
    </tr>
    <tr>
      <th id="T_681e7_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_681e7_row4_col0" class="data row4 col0">Routed + cache</td>
      <td id="T_681e7_row4_col1" class="data row4 col1">nano triage, mini routine, gpt-5.4 high risk</td>
      <td id="T_681e7_row4_col2" class="data row4 col2">stable full tool list plus allowed_tools</td>
      <td id="T_681e7_row4_col3" class="data row4 col3">stable playbook prefix</td>
      <td id="T_681e7_row4_col4" class="data row4 col4">some follow-up still synchronous</td>
      <td id="T_681e7_row4_col5" class="data row4 col5">0.98</td>
      <td id="T_681e7_row4_col6" class="data row4 col6">100%</td>
      <td id="T_681e7_row4_col7" class="data row4 col7">1.85</td>
      <td id="T_681e7_row4_col8" class="data row4 col8">$244</td>
      <td id="T_681e7_row4_col9" class="data row4 col9">high-volume repeated workflows with good cache locality</td>
    </tr>
    <tr>
      <th id="T_681e7_level0_row5" class="row_heading level0 row5">5</th>
      <td id="T_681e7_row5_col0" class="data row5 col0">Balanced split workflow</td>
      <td id="T_681e7_row5_col1" class="data row5 col1">nano triage/tags, mini routine, gpt-5.4 high risk</td>
      <td id="T_681e7_row5_col2" class="data row5 col2">stable full tool list plus allowed_tools</td>
      <td id="T_681e7_row5_col3" class="data row5 col3">stable playbook prefix</td>
      <td id="T_681e7_row5_col4" class="data row5 col4">customer path sync, QA/tags/reporting async</td>
      <td id="T_681e7_row5_col5" class="data row5 col5">0.98</td>
      <td id="T_681e7_row5_col6" class="data row5 col6">100%</td>
      <td id="T_681e7_row5_col7" class="data row5 col7">1.41</td>
      <td id="T_681e7_row5_col8" class="data row5 col8">$204</td>
      <td id="T_681e7_row5_col9" class="data row5 col9">most mature repeated-workflow support deployments</td>
    </tr>
  </tbody>
</table>

### Scenario sweet spots

This table maps common real-world operating scenarios to the best-scoring architecture combination. The scenario constraints are mocked for demonstration, and the architecture metrics come from the dry-run simulation above. In production, replace the constraints with your support SLAs, budget, policy-risk thresholds, and observed cache hit rates.


```python
fit_rows = [
    scenario_fit_score(scenario, option_key, summary)
    for scenario in OPERATING_SCENARIOS
    for option_key in ARCHITECTURE_OPTIONS
]
fit_df = pd.DataFrame(fit_rows)

best_fit = (
    fit_df.sort_values(["scenario", "score", "monthly_cost_at_100k_tickets"], ascending=[True, False, True])
    .groupby("scenario", sort=False)
    .head(1)
    .reset_index(drop=True)
)

scenario_context = pd.DataFrame(OPERATING_SCENARIOS)[
    [
        "scenario",
        "description",
        "quality_floor",
        "policy_floor",
        "p50_latency_target_s",
        "monthly_budget_100k_usd",
        "needs_async",
        "cache_locality",
    ]
]

best_fit_view = best_fit.merge(scenario_context, on="scenario")

print("Table: Recommended sweet spot by scenario (mock constraints + dry-run architecture metrics)")
display(
    best_fit_view[
        [
            "scenario",
            "description",
            "label",
            "score",
            "quality",
            "quality_floor",
            "policy_compliance",
            "policy_floor",
            "p50_latency_s",
            "p50_latency_target_s",
            "monthly_cost_at_100k_tickets",
            "monthly_budget_100k_usd",
            "cache_locality",
            "failed_constraints",
        ]
    ].style.format(
        {
            "quality": "{:.2f}",
            "quality_floor": "{:.2f}",
            "policy_compliance": "{:.0%}",
            "policy_floor": "{:.0%}",
            "p50_latency_s": "{:.2f}",
            "p50_latency_target_s": "{:.2f}",
            "monthly_cost_at_100k_tickets": "${:,.0f}",
            "monthly_budget_100k_usd": "${:,.0f}",
        }
    )
)
```

```text
Table: Recommended sweet spot by scenario (mock constraints + dry-run architecture metrics)
```

<table id="T_fa37e">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_fa37e_level0_col0" class="col_heading level0 col0">scenario</th>
      <th id="T_fa37e_level0_col1" class="col_heading level0 col1">description</th>
      <th id="T_fa37e_level0_col2" class="col_heading level0 col2">label</th>
      <th id="T_fa37e_level0_col3" class="col_heading level0 col3">score</th>
      <th id="T_fa37e_level0_col4" class="col_heading level0 col4">quality</th>
      <th id="T_fa37e_level0_col5" class="col_heading level0 col5">quality_floor</th>
      <th id="T_fa37e_level0_col6" class="col_heading level0 col6">policy_compliance</th>
      <th id="T_fa37e_level0_col7" class="col_heading level0 col7">policy_floor</th>
      <th id="T_fa37e_level0_col8" class="col_heading level0 col8">p50_latency_s</th>
      <th id="T_fa37e_level0_col9" class="col_heading level0 col9">p50_latency_target_s</th>
      <th id="T_fa37e_level0_col10" class="col_heading level0 col10">monthly_cost_at_100k_tickets</th>
      <th id="T_fa37e_level0_col11" class="col_heading level0 col11">monthly_budget_100k_usd</th>
      <th id="T_fa37e_level0_col12" class="col_heading level0 col12">cache_locality</th>
      <th id="T_fa37e_level0_col13" class="col_heading level0 col13">failed_constraints</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_fa37e_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_fa37e_row0_col0" class="data row0 col0">Account and billing sensitive queue</td>
      <td id="T_fa37e_row0_col1" class="data row0 col1">Risky account recovery and duplicate-charge workflows dominate.</td>
      <td id="T_fa37e_row0_col2" class="data row0 col2">Routed split, no cache</td>
      <td id="T_fa37e_row0_col3" class="data row0 col3">13</td>
      <td id="T_fa37e_row0_col4" class="data row0 col4">0.98</td>
      <td id="T_fa37e_row0_col5" class="data row0 col5">0.98</td>
      <td id="T_fa37e_row0_col6" class="data row0 col6">100%</td>
      <td id="T_fa37e_row0_col7" class="data row0 col7">100%</td>
      <td id="T_fa37e_row0_col8" class="data row0 col8">1.57</td>
      <td id="T_fa37e_row0_col9" class="data row0 col9">2.80</td>
      <td id="T_fa37e_row0_col10" class="data row0 col10">$285</td>
      <td id="T_fa37e_row0_col11" class="data row0 col11">$750</td>
      <td id="T_fa37e_row0_col12" class="data row0 col12">medium</td>
      <td id="T_fa37e_row0_col13" class="data row0 col13">none</td>
    </tr>
    <tr>
      <th id="T_fa37e_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_fa37e_row1_col0" class="data row1 col0">Early pilot</td>
      <td id="T_fa37e_row1_col1" class="data row1 col1">Low volume, quality learning matters more than unit cost.</td>
      <td id="T_fa37e_row1_col2" class="data row1 col2">Routed, no cache</td>
      <td id="T_fa37e_row1_col3" class="data row1 col3">13</td>
      <td id="T_fa37e_row1_col4" class="data row1 col4">0.98</td>
      <td id="T_fa37e_row1_col5" class="data row1 col5">0.94</td>
      <td id="T_fa37e_row1_col6" class="data row1 col6">100%</td>
      <td id="T_fa37e_row1_col7" class="data row1 col7">98%</td>
      <td id="T_fa37e_row1_col8" class="data row1 col8">1.87</td>
      <td id="T_fa37e_row1_col9" class="data row1 col9">3.00</td>
      <td id="T_fa37e_row1_col10" class="data row1 col10">$302</td>
      <td id="T_fa37e_row1_col11" class="data row1 col11">$800</td>
      <td id="T_fa37e_row1_col12" class="data row1 col12">low</td>
      <td id="T_fa37e_row1_col13" class="data row1 col13">none</td>
    </tr>
    <tr>
      <th id="T_fa37e_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_fa37e_row2_col0" class="data row2 col0">High-volume routine ecommerce</td>
      <td id="T_fa37e_row2_col1" class="data row2 col1">Many repeated order, return, and damage workflows.</td>
      <td id="T_fa37e_row2_col2" class="data row2 col2">Balanced split workflow</td>
      <td id="T_fa37e_row2_col3" class="data row2 col3">13</td>
      <td id="T_fa37e_row2_col4" class="data row2 col4">0.98</td>
      <td id="T_fa37e_row2_col5" class="data row2 col5">0.96</td>
      <td id="T_fa37e_row2_col6" class="data row2 col6">100%</td>
      <td id="T_fa37e_row2_col7" class="data row2 col7">99%</td>
      <td id="T_fa37e_row2_col8" class="data row2 col8">1.41</td>
      <td id="T_fa37e_row2_col9" class="data row2 col9">2.00</td>
      <td id="T_fa37e_row2_col10" class="data row2 col10">$204</td>
      <td id="T_fa37e_row2_col11" class="data row2 col11">$300</td>
      <td id="T_fa37e_row2_col12" class="data row2 col12">high</td>
      <td id="T_fa37e_row2_col13" class="data row2 col13">none</td>
    </tr>
    <tr>
      <th id="T_fa37e_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_fa37e_row3_col0" class="data row3 col0">Low-repeat long tail</td>
      <td id="T_fa37e_row3_col1" class="data row3 col1">Many rare ticket types; cache hit rate is uncertain.</td>
      <td id="T_fa37e_row3_col2" class="data row3 col2">Routed split, no cache</td>
      <td id="T_fa37e_row3_col3" class="data row3 col3">13</td>
      <td id="T_fa37e_row3_col4" class="data row3 col4">0.98</td>
      <td id="T_fa37e_row3_col5" class="data row3 col5">0.96</td>
      <td id="T_fa37e_row3_col6" class="data row3 col6">100%</td>
      <td id="T_fa37e_row3_col7" class="data row3 col7">99%</td>
      <td id="T_fa37e_row3_col8" class="data row3 col8">1.57</td>
      <td id="T_fa37e_row3_col9" class="data row3 col9">2.50</td>
      <td id="T_fa37e_row3_col10" class="data row3 col10">$285</td>
      <td id="T_fa37e_row3_col11" class="data row3 col11">$450</td>
      <td id="T_fa37e_row3_col12" class="data row3 col12">low</td>
      <td id="T_fa37e_row3_col13" class="data row3 col13">none</td>
    </tr>
    <tr>
      <th id="T_fa37e_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_fa37e_row4_col0" class="data row4 col0">Peak sale burst</td>
      <td id="T_fa37e_row4_col1" class="data row4 col1">Latency and cost matter during temporary traffic spikes.</td>
      <td id="T_fa37e_row4_col2" class="data row4 col2">Balanced split workflow</td>
      <td id="T_fa37e_row4_col3" class="data row4 col3">13</td>
      <td id="T_fa37e_row4_col4" class="data row4 col4">0.98</td>
      <td id="T_fa37e_row4_col5" class="data row4 col5">0.95</td>
      <td id="T_fa37e_row4_col6" class="data row4 col6">100%</td>
      <td id="T_fa37e_row4_col7" class="data row4 col7">99%</td>
      <td id="T_fa37e_row4_col8" class="data row4 col8">1.41</td>
      <td id="T_fa37e_row4_col9" class="data row4 col9">1.80</td>
      <td id="T_fa37e_row4_col10" class="data row4 col10">$204</td>
      <td id="T_fa37e_row4_col11" class="data row4 col11">$250</td>
      <td id="T_fa37e_row4_col12" class="data row4 col12">high</td>
      <td id="T_fa37e_row4_col13" class="data row4 col13">none</td>
    </tr>
    <tr>
      <th id="T_fa37e_level0_row5" class="row_heading level0 row5">5</th>
      <td id="T_fa37e_row5_col0" class="data row5 col0">Premium support</td>
      <td id="T_fa37e_row5_col1" class="data row5 col1">Higher customer value, lower tolerance for wrong actions.</td>
      <td id="T_fa37e_row5_col2" class="data row5 col2">Routed split, no cache</td>
      <td id="T_fa37e_row5_col3" class="data row5 col3">13</td>
      <td id="T_fa37e_row5_col4" class="data row5 col4">0.98</td>
      <td id="T_fa37e_row5_col5" class="data row5 col5">0.98</td>
      <td id="T_fa37e_row5_col6" class="data row5 col6">100%</td>
      <td id="T_fa37e_row5_col7" class="data row5 col7">100%</td>
      <td id="T_fa37e_row5_col8" class="data row5 col8">1.57</td>
      <td id="T_fa37e_row5_col9" class="data row5 col9">2.50</td>
      <td id="T_fa37e_row5_col10" class="data row5 col10">$285</td>
      <td id="T_fa37e_row5_col11" class="data row5 col11">$650</td>
      <td id="T_fa37e_row5_col12" class="data row5 col12">medium</td>
      <td id="T_fa37e_row5_col13" class="data row5 col13">none</td>
    </tr>
  </tbody>
</table>

### Full combination map for one scenario

This table shows all architecture options for one mocked scenario: `Low-repeat long tail`. It is included to make the tradeoff visible rather than hiding everything behind the single best pick. The numbers are still simulated; the point is to show why cache-heavy designs are less attractive when cache locality is low.


```python
# Show the full combination map for one scenario so tradeoffs are visible, not hidden behind the best pick.
scenario_to_inspect = "Low-repeat long tail"
combo_map = fit_df[fit_df["scenario"] == scenario_to_inspect].sort_values("score", ascending=False)

print(f"Table: Full architecture ranking for {scenario_to_inspect} (mock scenario + dry-run metrics)")
display(
    combo_map[
        [
            "label",
            "score",
            "quality",
            "policy_compliance",
            "p50_latency_s",
            "monthly_cost_at_100k_tickets",
            "failed_constraints",
        ]
    ].style.format(
        {
            "quality": "{:.2f}",
            "policy_compliance": "{:.0%}",
            "p50_latency_s": "{:.2f}",
            "monthly_cost_at_100k_tickets": "${:,.0f}",
        }
    )
)
```

```text
Table: Full architecture ranking for Low-repeat long tail (mock scenario + dry-run metrics)
```

<table id="T_26e63">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_26e63_level0_col0" class="col_heading level0 col0">label</th>
      <th id="T_26e63_level0_col1" class="col_heading level0 col1">score</th>
      <th id="T_26e63_level0_col2" class="col_heading level0 col2">quality</th>
      <th id="T_26e63_level0_col3" class="col_heading level0 col3">policy_compliance</th>
      <th id="T_26e63_level0_col4" class="col_heading level0 col4">p50_latency_s</th>
      <th id="T_26e63_level0_col5" class="col_heading level0 col5">monthly_cost_at_100k_tickets</th>
      <th id="T_26e63_level0_col6" class="col_heading level0 col6">failed_constraints</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_26e63_level0_row0" class="row_heading level0 row0">27</th>
      <td id="T_26e63_row0_col0" class="data row0 col0">Routed split, no cache</td>
      <td id="T_26e63_row0_col1" class="data row0 col1">13</td>
      <td id="T_26e63_row0_col2" class="data row0 col2">0.98</td>
      <td id="T_26e63_row0_col3" class="data row0 col3">100%</td>
      <td id="T_26e63_row0_col4" class="data row0 col4">1.57</td>
      <td id="T_26e63_row0_col5" class="data row0 col5">$285</td>
      <td id="T_26e63_row0_col6" class="data row0 col6">none</td>
    </tr>
    <tr>
      <th id="T_26e63_level0_row1" class="row_heading level0 row1">26</th>
      <td id="T_26e63_row1_col0" class="data row1 col0">Routed, no cache</td>
      <td id="T_26e63_row1_col1" class="data row1 col1">10</td>
      <td id="T_26e63_row1_col2" class="data row1 col2">0.98</td>
      <td id="T_26e63_row1_col3" class="data row1 col3">100%</td>
      <td id="T_26e63_row1_col4" class="data row1 col4">1.87</td>
      <td id="T_26e63_row1_col5" class="data row1 col5">$302</td>
      <td id="T_26e63_row1_col6" class="data row1 col6">async split</td>
    </tr>
    <tr>
      <th id="T_26e63_level0_row2" class="row_heading level0 row2">29</th>
      <td id="T_26e63_row2_col0" class="data row2 col0">Balanced split workflow</td>
      <td id="T_26e63_row2_col1" class="data row2 col1">9</td>
      <td id="T_26e63_row2_col2" class="data row2 col2">0.98</td>
      <td id="T_26e63_row2_col3" class="data row2 col3">100%</td>
      <td id="T_26e63_row2_col4" class="data row2 col4">1.41</td>
      <td id="T_26e63_row2_col5" class="data row2 col5">$204</td>
      <td id="T_26e63_row2_col6" class="data row2 col6">cache locality</td>
    </tr>
    <tr>
      <th id="T_26e63_level0_row3" class="row_heading level0 row3">28</th>
      <td id="T_26e63_row3_col0" class="data row3 col0">Routed + cache</td>
      <td id="T_26e63_row3_col1" class="data row3 col1">6</td>
      <td id="T_26e63_row3_col2" class="data row3 col2">0.98</td>
      <td id="T_26e63_row3_col3" class="data row3 col3">100%</td>
      <td id="T_26e63_row3_col4" class="data row3 col4">1.85</td>
      <td id="T_26e63_row3_col5" class="data row3 col5">$244</td>
      <td id="T_26e63_row3_col6" class="data row3 col6">async split, cache locality</td>
    </tr>
    <tr>
      <th id="T_26e63_level0_row4" class="row_heading level0 row4">25</th>
      <td id="T_26e63_row4_col0" class="data row4 col0">Controlled full model</td>
      <td id="T_26e63_row4_col1" class="data row4 col1">5</td>
      <td id="T_26e63_row4_col2" class="data row4 col2">0.98</td>
      <td id="T_26e63_row4_col3" class="data row4 col3">100%</td>
      <td id="T_26e63_row4_col4" class="data row4 col4">2.32</td>
      <td id="T_26e63_row4_col5" class="data row4 col5">$512</td>
      <td id="T_26e63_row4_col6" class="data row4 col6">budget, async split</td>
    </tr>
    <tr>
      <th id="T_26e63_level0_row5" class="row_heading level0 row5">24</th>
      <td id="T_26e63_row5_col0" class="data row5 col0">One broad agent</td>
      <td id="T_26e63_row5_col1" class="data row5 col1">-14</td>
      <td id="T_26e63_row5_col2" class="data row5 col2">0.51</td>
      <td id="T_26e63_row5_col3" class="data row5 col3">10%</td>
      <td id="T_26e63_row5_col4" class="data row5 col4">4.88</td>
      <td id="T_26e63_row5_col5" class="data row5 col5">$3,813</td>
      <td id="T_26e63_row5_col6" class="data row5 col6">quality, policy, latency, budget, async split</td>
    </tr>
  </tbody>
</table>

In the mock scenarios, repeated workflows favor a shared cache prefix and asynchronous follow-up. Low-repeat queues may favor the routed split without caching, while an early pilot may justify a full model until routing is reliable.

Treat these rankings as a design exercise. They include hand-set constraints and scoring bonuses, so a high score is not proof that an architecture meets every requirement. Check `failed_constraints` and enforce quality and policy gates before selecting a production configuration.


## Monitoring, evals, and guardrails

Once the optimized workflow is in production, keep a recurring eval loop. The objective is not to minimize tokens in isolation. It is to resolve customer issues correctly, safely, and quickly at the lowest total cost per successful outcome.

### Measure task efficiency, not just token efficiency

Token counts are useful diagnostics, but they do not tell you whether the customer's problem was solved. A cheaper model that requires repeated attempts, unnecessary tool calls, or human correction can cost more per resolved issue than a stronger model that completes the task correctly on its first attempt.

OpenAI's guidance recommends measuring the complete cost of reaching an acceptable outcome, including "model and tool usage, attempts, completion rate, latency, and human review." For customer support, that accepted outcome may be a resolved case. See [How to manage AI investments in the agentic era](https://openai.com/index/managing-ai-investments-in-agentic-era/) and [A scorecard for the AI age](https://openai.com/index/a-scorecard-for-the-ai-age/).

A useful operational formula is:

`blended cost per verified resolution = total model, tool, infrastructure, retry, human-review, escalation, and rework costs / verified customer issues resolved`

The numerator must include spending on unsuccessful attempts, not only the traces that eventually passed. Track autonomous resolutions separately from human-assisted resolutions so an apparent reduction in agent cost does not hide a transfer of work to the support team.

For example, a workflow that costs 0.02 USD per ticket and resolves 50% of tickets costs 0.04 USD per successful resolution. A workflow that costs 0.03 USD per ticket and resolves 90% costs approximately 0.033 USD per successful resolution. The second workflow costs more per attempt but less per successful outcome. These figures are illustrative and exclude human-support costs.

### Define success before optimizing

A successful response uses the right account, order, and policy facts and gives an accurate next step. Required tools must succeed with valid arguments, and promised actions must be completed or clearly pending. Policy and authorization checks determine which cases can be resolved automatically and which require escalation.

A policy-required escalation can be a successful handling outcome, but it is not an autonomous resolution. Similarly, opening a case or requesting a photo is not proof that the customer's underlying issue was resolved. Keep these outcomes separate when calculating first-contact resolution and automation rates.

### Track the complete support workflow

Monitor verified resolutions separately for autonomous and human-assisted cases, including repeat contacts and reopened cases. Pair those outcomes with policy and escalation accuracy, total cost per verified resolution, and customer-facing p50/p95 latency.

Use model calls, tool failures, retries, token usage, and routing decisions to explain changes in those outcomes. Segment results by intent, risk, language, region, customer tier, and model route so an average does not conceal a regression.

Inspect the full execution trajectory, not only the final answer. OpenAI's [agent evaluation guidance](https://developers.openai.com/api/docs/guides/agent-evals) describes traces that capture model calls, tool calls, guardrails, and handoffs, making it possible to identify unnecessary loops, incorrect actions, and routing failures that a polished response can conceal.

Compare workflow variants on the same representative ticket distribution, including difficult and policy-sensitive cases. Treat policy compliance, action correctness, security, and escalation accuracy as hard gates before comparing cost or latency. Refresh the dataset with production failures and rerun evaluations when prompts, models, tools, routing, or policies change. See [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

Guardrail failure modes that can look efficient while creating downstream risk: tool timeouts, empty or oversized tool payloads, duplicate tool loops, unsafe account-access actions, skipped required verification, and refund promises made before eligibility or completion is confirmed.

**Demo limitation:** This notebook directly models tokens, estimated cost, tool usage, latency, action accuracy, policy compliance, and escalation behavior. True first-contact resolution, reopened cases, retry history, completed downstream outcomes, and human-handling costs require production support-system and trace data. Do not infer those metrics from the dry-run simulation alone.


```python
from simulation import deterministic_guardrail_check

guardrail_rows = []
for _, row in traces.iterrows():
    ticket = next(t for t in EVAL_SET if t["ticket_id"] == row["ticket_id"])
    failures = deterministic_guardrail_check(ticket, row.to_dict())
    guardrail_rows.append(
        {
            "variant_label": row["variant_label"],
            "ticket_id": row["ticket_id"],
            "failures": ", ".join(failures),
            "passed": not failures,
        }
    )

guardrails = pd.DataFrame(guardrail_rows)
guardrail_summary = guardrails.groupby("variant_label", sort=False).agg(pass_rate=("passed", "mean"), failures=("passed", lambda s: (~s).sum())).reset_index()

display(guardrail_summary.style.format({"pass_rate": "{:.0%}"}))
display(guardrails[~guardrails["passed"]].head(20))
```

<table id="T_75622">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_75622_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_75622_level0_col1" class="col_heading level0 col1">pass_rate</th>
      <th id="T_75622_level0_col2" class="col_heading level0 col2">failures</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_75622_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_75622_row0_col0" class="data row0 col0">Bad baseline</td>
      <td id="T_75622_row0_col1" class="data row0 col1">0%</td>
      <td id="T_75622_row0_col2" class="data row0 col2">10</td>
    </tr>
    <tr>
      <th id="T_75622_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_75622_row1_col0" class="data row1 col0">Round 1: controls</td>
      <td id="T_75622_row1_col1" class="data row1 col1">100%</td>
      <td id="T_75622_row1_col2" class="data row1 col2">0</td>
    </tr>
    <tr>
      <th id="T_75622_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_75622_row2_col0" class="data row2 col0">Round 2: routing</td>
      <td id="T_75622_row2_col1" class="data row2 col1">100%</td>
      <td id="T_75622_row2_col2" class="data row2 col2">0</td>
    </tr>
    <tr>
      <th id="T_75622_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_75622_row3_col0" class="data row3 col0">Round 3: caching</td>
      <td id="T_75622_row3_col1" class="data row3 col1">100%</td>
      <td id="T_75622_row3_col2" class="data row3 col2">0</td>
    </tr>
    <tr>
      <th id="T_75622_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_75622_row4_col0" class="data row4 col0">Round 4: split workflow</td>
      <td id="T_75622_row4_col1" class="data row4 col1">100%</td>
      <td id="T_75622_row4_col2" class="data row4 col2">0</td>
    </tr>
  </tbody>
</table>

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>variant_label</th>
      <th>ticket_id</th>
      <th>failures</th>
      <th>passed</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Bad baseline</td>
      <td>T-001</td>
      <td>too_many_unnecessary_tools, missing_required_r...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>1</th>
      <td>Bad baseline</td>
      <td>T-002</td>
      <td>too_many_unnecessary_tools, policy_or_action_m...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Bad baseline</td>
      <td>T-003</td>
      <td>missing_required_response_content, policy_or_a...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Bad baseline</td>
      <td>T-004</td>
      <td>customer_answer_too_long</td>
      <td>False</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Bad baseline</td>
      <td>T-005</td>
      <td>missing_required_response_content, policy_or_a...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Bad baseline</td>
      <td>T-006</td>
      <td>missing_required_response_content, policy_or_a...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>6</th>
      <td>Bad baseline</td>
      <td>T-007</td>
      <td>too_many_unnecessary_tools, missing_required_r...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>7</th>
      <td>Bad baseline</td>
      <td>T-008</td>
      <td>missing_required_response_content, policy_or_a...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>8</th>
      <td>Bad baseline</td>
      <td>T-009</td>
      <td>missing_required_response_content, policy_or_a...</td>
      <td>False</td>
    </tr>
    <tr>
      <th>9</th>
      <td>Bad baseline</td>
      <td>T-010</td>
      <td>missing_required_response_content, policy_or_a...</td>
      <td>False</td>
    </tr>
  </tbody>
</table>
</div>

### Optional: judge customer-answer completeness and grounding

Did the cheaper workflow preserve an accurate, useful answer? This judge checks one question: given the customer ticket, relevant policy, and recorded tool results, does the answer correctly explain the outcome and next step without unsupported claims?

The [judge helper](https://github.com/openai/openai-cookbook/blob/bb95430abb908c1edddc38af5911109ab2ce3987/examples/agent_optimization/live_api.py) returns `passed` and a brief `reason`. It accepts equivalent wording: “Your return qualifies under our 30-day policy” need not contain the fixture's exact phrase “within 30 days.” But “Your refund is on its way” should fail when the recorded tool result only confirms that a review case was opened. Tool results are captured when the tools run, rather than reconstructed from expected actions.

Set `RUN_LLM_JUDGE=true` and `OPENAI_API_KEY` before running the setup cell. The code below grades the same recorded answers for every optimization round using a fixed `gpt-5.4-mini` judge and rubric. The judge does not see variant names, agent models, costs, or expected action labels. These are real judge calls over **synthetic agent traces**, so the results assess the canned answers, not model performance. For live answers, call `live_judge_response(live_ticket, live_result["response_text"], live_result["tool_results"], client=judge_client)` after opting in.

The table places judge pass rate next to the deterministic pass rate. `both_pass_rate` requires both checks to pass; a judge pass never overrides a deterministic failure. Judge and combined pass rates cover successfully graded traces only, so inspect coverage and errors before comparing variants. Skipped, refused, malformed, or incomplete grades remain unavailable. Evaluation cost is reported separately from agent cost and customer latency; `known_judge_cost_usd` uses returned usage, and `judge_cost_unavailable` flags attempts without cost data.

Before using these grades as a release gate, label a small sample yourself, including a valid paraphrase, a missing next step, and an unsupported refund promise. Check agreement and revise the rubric when it disagrees. See [evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).


```python
from evaluation import evaluate_answer_traces, summarize_answer_evals

answer_evals = evaluate_answer_traces(
    EVAL_SET, traces.to_dict("records"), client=judge_client
)
answer_eval_summary = summarize_answer_evals(answer_evals)
display(answer_eval_summary.drop(columns="variant").style.format(
    {
        "deterministic_pass_rate": "{:.0%}",
        "judge_coverage": "{:.0%}",
        "judge_pass_rate": "{:.0%}",
        "both_pass_rate": "{:.0%}",
        "known_judge_cost_usd": "${:.5f}",
    },
    na_rep="Not available",
))
if RUN_LLM_JUDGE:
    # Inspect failures, errors, and disagreements with the literal phrase checks.
    needs_review = answer_evals[
        answer_evals["judge_status"].eq("error") | answer_evals["passed"].eq(False)
        | answer_evals["passed"].ne(answer_evals["deterministic_passed"])
    ]
    display(needs_review[["variant_label", "ticket_id", "deterministic_passed", "passed", "reason"]])
else:
    print("Judge not run. Set RUN_LLM_JUDGE=true to grade these saved answers.")
```

<table id="T_363cc">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_363cc_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_363cc_level0_col1" class="col_heading level0 col1">tickets</th>
      <th id="T_363cc_level0_col2" class="col_heading level0 col2">deterministic_pass_rate</th>
      <th id="T_363cc_level0_col3" class="col_heading level0 col3">judge_graded</th>
      <th id="T_363cc_level0_col4" class="col_heading level0 col4">judge_coverage</th>
      <th id="T_363cc_level0_col5" class="col_heading level0 col5">judge_errors</th>
      <th id="T_363cc_level0_col6" class="col_heading level0 col6">judge_pass_rate</th>
      <th id="T_363cc_level0_col7" class="col_heading level0 col7">both_pass_rate</th>
      <th id="T_363cc_level0_col8" class="col_heading level0 col8">known_judge_cost_usd</th>
      <th id="T_363cc_level0_col9" class="col_heading level0 col9">judge_cost_unavailable</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_363cc_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_363cc_row0_col0" class="data row0 col0">Bad baseline</td>
      <td id="T_363cc_row0_col1" class="data row0 col1">10</td>
      <td id="T_363cc_row0_col2" class="data row0 col2">0%</td>
      <td id="T_363cc_row0_col3" class="data row0 col3">10</td>
      <td id="T_363cc_row0_col4" class="data row0 col4">100%</td>
      <td id="T_363cc_row0_col5" class="data row0 col5">0</td>
      <td id="T_363cc_row0_col6" class="data row0 col6">0%</td>
      <td id="T_363cc_row0_col7" class="data row0 col7">0%</td>
      <td id="T_363cc_row0_col8" class="data row0 col8">$0.05637</td>
      <td id="T_363cc_row0_col9" class="data row0 col9">0</td>
    </tr>
    <tr>
      <th id="T_363cc_level0_row1" class="row_heading level0 row1">1</th>
      <td id="T_363cc_row1_col0" class="data row1 col0">Round 1: controls</td>
      <td id="T_363cc_row1_col1" class="data row1 col1">10</td>
      <td id="T_363cc_row1_col2" class="data row1 col2">100%</td>
      <td id="T_363cc_row1_col3" class="data row1 col3">10</td>
      <td id="T_363cc_row1_col4" class="data row1 col4">100%</td>
      <td id="T_363cc_row1_col5" class="data row1 col5">0</td>
      <td id="T_363cc_row1_col6" class="data row1 col6">80%</td>
      <td id="T_363cc_row1_col7" class="data row1 col7">80%</td>
      <td id="T_363cc_row1_col8" class="data row1 col8">$0.01252</td>
      <td id="T_363cc_row1_col9" class="data row1 col9">0</td>
    </tr>
    <tr>
      <th id="T_363cc_level0_row2" class="row_heading level0 row2">2</th>
      <td id="T_363cc_row2_col0" class="data row2 col0">Round 2: routing</td>
      <td id="T_363cc_row2_col1" class="data row2 col1">10</td>
      <td id="T_363cc_row2_col2" class="data row2 col2">100%</td>
      <td id="T_363cc_row2_col3" class="data row2 col3">10</td>
      <td id="T_363cc_row2_col4" class="data row2 col4">100%</td>
      <td id="T_363cc_row2_col5" class="data row2 col5">0</td>
      <td id="T_363cc_row2_col6" class="data row2 col6">70%</td>
      <td id="T_363cc_row2_col7" class="data row2 col7">70%</td>
      <td id="T_363cc_row2_col8" class="data row2 col8">$0.01350</td>
      <td id="T_363cc_row2_col9" class="data row2 col9">0</td>
    </tr>
    <tr>
      <th id="T_363cc_level0_row3" class="row_heading level0 row3">3</th>
      <td id="T_363cc_row3_col0" class="data row3 col0">Round 3: caching</td>
      <td id="T_363cc_row3_col1" class="data row3 col1">10</td>
      <td id="T_363cc_row3_col2" class="data row3 col2">100%</td>
      <td id="T_363cc_row3_col3" class="data row3 col3">10</td>
      <td id="T_363cc_row3_col4" class="data row3 col4">100%</td>
      <td id="T_363cc_row3_col5" class="data row3 col5">0</td>
      <td id="T_363cc_row3_col6" class="data row3 col6">90%</td>
      <td id="T_363cc_row3_col7" class="data row3 col7">90%</td>
      <td id="T_363cc_row3_col8" class="data row3 col8">$0.01279</td>
      <td id="T_363cc_row3_col9" class="data row3 col9">0</td>
    </tr>
    <tr>
      <th id="T_363cc_level0_row4" class="row_heading level0 row4">4</th>
      <td id="T_363cc_row4_col0" class="data row4 col0">Round 4: split workflow</td>
      <td id="T_363cc_row4_col1" class="data row4 col1">10</td>
      <td id="T_363cc_row4_col2" class="data row4 col2">100%</td>
      <td id="T_363cc_row4_col3" class="data row4 col3">10</td>
      <td id="T_363cc_row4_col4" class="data row4 col4">100%</td>
      <td id="T_363cc_row4_col5" class="data row4 col5">0</td>
      <td id="T_363cc_row4_col6" class="data row4 col6">80%</td>
      <td id="T_363cc_row4_col7" class="data row4 col7">80%</td>
      <td id="T_363cc_row4_col8" class="data row4 col8">$0.01285</td>
      <td id="T_363cc_row4_col9" class="data row4 col9">0</td>
    </tr>
  </tbody>
</table>

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>variant_label</th>
      <th>ticket_id</th>
      <th>deterministic_passed</th>
      <th>passed</th>
      <th>reason</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Bad baseline</td>
      <td>T-001</td>
      <td>False</td>
      <td>False</td>
      <td>The answer does not give the customer the actu...</td>
    </tr>
    <tr>
      <th>1</th>
      <td>Bad baseline</td>
      <td>T-002</td>
      <td>False</td>
      <td>False</td>
      <td>The reply does not follow the policy: it shoul...</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Bad baseline</td>
      <td>T-003</td>
      <td>False</td>
      <td>False</td>
      <td>The answer is not grounded in the evidence: th...</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Bad baseline</td>
      <td>T-004</td>
      <td>False</td>
      <td>False</td>
      <td>The reply does not clearly tell the customer t...</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Bad baseline</td>
      <td>T-005</td>
      <td>False</td>
      <td>False</td>
      <td>It does not give the customer the needed accou...</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Bad baseline</td>
      <td>T-006</td>
      <td>False</td>
      <td>False</td>
      <td>It does not clearly tell the customer that O-1...</td>
    </tr>
    <tr>
      <th>6</th>
      <td>Bad baseline</td>
      <td>T-007</td>
      <td>False</td>
      <td>False</td>
      <td>The reply does not give the customer-facing ne...</td>
    </tr>
    <tr>
      <th>7</th>
      <td>Bad baseline</td>
      <td>T-008</td>
      <td>False</td>
      <td>False</td>
      <td>The answer is not grounded in the evidence: it...</td>
    </tr>
    <tr>
      <th>8</th>
      <td>Bad baseline</td>
      <td>T-009</td>
      <td>False</td>
      <td>False</td>
      <td>The answer is vague and overly internal. It do...</td>
    </tr>
    <tr>
      <th>9</th>
      <td>Bad baseline</td>
      <td>T-010</td>
      <td>False</td>
      <td>False</td>
      <td>It follows the policy direction to escalate, b...</td>
    </tr>
    <tr>
      <th>12</th>
      <td>Round 1: controls</td>
      <td>T-003</td>
      <td>True</td>
      <td>False</td>
      <td>The case opening is supported, but the answer ...</td>
    </tr>
    <tr>
      <th>19</th>
      <td>Round 1: controls</td>
      <td>T-010</td>
      <td>True</td>
      <td>False</td>
      <td>It correctly says identity must be verified be...</td>
    </tr>
    <tr>
      <th>22</th>
      <td>Round 2: routing</td>
      <td>T-003</td>
      <td>True</td>
      <td>False</td>
      <td>The answer overstates the outcome: it only sho...</td>
    </tr>
    <tr>
      <th>24</th>
      <td>Round 2: routing</td>
      <td>T-005</td>
      <td>True</td>
      <td>False</td>
      <td>The reply correctly says account details can’t...</td>
    </tr>
    <tr>
      <th>29</th>
      <td>Round 2: routing</td>
      <td>T-010</td>
      <td>True</td>
      <td>False</td>
      <td>The reply gives the right general guidance, bu...</td>
    </tr>
    <tr>
      <th>39</th>
      <td>Round 3: caching</td>
      <td>T-010</td>
      <td>True</td>
      <td>False</td>
      <td>The reply gives the right general guidance, bu...</td>
    </tr>
    <tr>
      <th>44</th>
      <td>Round 4: split workflow</td>
      <td>T-005</td>
      <td>True</td>
      <td>False</td>
      <td>The reply is grounded on the identity check an...</td>
    </tr>
    <tr>
      <th>49</th>
      <td>Round 4: split workflow</td>
      <td>T-010</td>
      <td>True</td>
      <td>False</td>
      <td>The answer gives the right general guidance, b...</td>
    </tr>
  </tbody>
</table>
</div>

## Before and after ticket walkthroughs

These examples compare the inefficient baseline with the final optimized path.


```python
walkthrough_tickets = ["T-002", "T-004", "T-008"]
walkthrough = traces[
    traces["ticket_id"].isin(walkthrough_tickets)
    & traces["variant"].isin(["00_bad_baseline", "04_split_workflow"])
].copy()
walkthrough["response_preview"] = walkthrough["customer_response"].str.replace("\n", " ").str.slice(0, 220)

display(
    walkthrough[
        [
            "ticket_id",
            "variant_label",
            "intent",
            "risk",
            "model",
            "tools",
            "action",
            "policy_compliant",
            "sync_tokens",
            "total_tokens",
            "latency_s",
            "cost_usd",
            "quality_score",
            "response_preview",
        ]
    ].style.format({"cost_usd": "${:.5f}", "quality_score": "{:.2f}", "latency_s": "{:.2f}"})
)
```

<table id="T_99ce3">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_99ce3_level0_col0" class="col_heading level0 col0">ticket_id</th>
      <th id="T_99ce3_level0_col1" class="col_heading level0 col1">variant_label</th>
      <th id="T_99ce3_level0_col2" class="col_heading level0 col2">intent</th>
      <th id="T_99ce3_level0_col3" class="col_heading level0 col3">risk</th>
      <th id="T_99ce3_level0_col4" class="col_heading level0 col4">model</th>
      <th id="T_99ce3_level0_col5" class="col_heading level0 col5">tools</th>
      <th id="T_99ce3_level0_col6" class="col_heading level0 col6">action</th>
      <th id="T_99ce3_level0_col7" class="col_heading level0 col7">policy_compliant</th>
      <th id="T_99ce3_level0_col8" class="col_heading level0 col8">sync_tokens</th>
      <th id="T_99ce3_level0_col9" class="col_heading level0 col9">total_tokens</th>
      <th id="T_99ce3_level0_col10" class="col_heading level0 col10">latency_s</th>
      <th id="T_99ce3_level0_col11" class="col_heading level0 col11">cost_usd</th>
      <th id="T_99ce3_level0_col12" class="col_heading level0 col12">quality_score</th>
      <th id="T_99ce3_level0_col13" class="col_heading level0 col13">response_preview</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_99ce3_level0_row0" class="row_heading level0 row0">1</th>
      <td id="T_99ce3_row0_col0" class="data row0 col0">T-002</td>
      <td id="T_99ce3_row0_col1" class="data row0 col1">Bad baseline</td>
      <td id="T_99ce3_row0_col2" class="data row0 col2">damaged_delivery</td>
      <td id="T_99ce3_row0_col3" class="data row0 col3">medium</td>
      <td id="T_99ce3_row0_col4" class="data row0 col4">gpt-5.4</td>
      <td id="T_99ce3_row0_col5" class="data row0 col5">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_99ce3_row0_col6" class="data row0 col6">open_replacement_without_photo</td>
      <td id="T_99ce3_row0_col7" class="data row0 col7">False</td>
      <td id="T_99ce3_row0_col8" class="data row0 col8">12917</td>
      <td id="T_99ce3_row0_col9" class="data row0 col9">12917</td>
      <td id="T_99ce3_row0_col10" class="data row0 col10">4.88</td>
      <td id="T_99ce3_row0_col11" class="data row0 col11">$0.04034</td>
      <td id="T_99ce3_row0_col12" class="data row0 col12">0.65</td>
      <td id="T_99ce3_row0_col13" class="data row0 col13">I reviewed your message for ticket T-002 and checked the customer profile, order system, policy library, refund workflow, escalation queue, carrier events, billing signals, and internal audit notes. Based on the availabl</td>
    </tr>
    <tr>
      <th id="T_99ce3_level0_row1" class="row_heading level0 row1">3</th>
      <td id="T_99ce3_row1_col0" class="data row1 col0">T-004</td>
      <td id="T_99ce3_row1_col1" class="data row1 col1">Bad baseline</td>
      <td id="T_99ce3_row1_col2" class="data row1 col2">billing_issue</td>
      <td id="T_99ce3_row1_col3" class="data row1 col3">medium</td>
      <td id="T_99ce3_row1_col4" class="data row1 col4">gpt-5.4</td>
      <td id="T_99ce3_row1_col5" class="data row1 col5">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_99ce3_row1_col6" class="data row1 col6">escalate_billing_review</td>
      <td id="T_99ce3_row1_col7" class="data row1 col7">True</td>
      <td id="T_99ce3_row1_col8" class="data row1 col8">12830</td>
      <td id="T_99ce3_row1_col9" class="data row1 col9">12830</td>
      <td id="T_99ce3_row1_col10" class="data row1 col10">4.87</td>
      <td id="T_99ce3_row1_col11" class="data row1 col11">$0.04038</td>
      <td id="T_99ce3_row1_col12" class="data row1 col12">0.85</td>
      <td id="T_99ce3_row1_col13" class="data row1 col13">I reviewed your message for ticket T-004 and checked the customer profile, order system, policy library, refund workflow, escalation queue, carrier events, billing signals, and internal audit notes. Based on the availabl</td>
    </tr>
    <tr>
      <th id="T_99ce3_level0_row2" class="row_heading level0 row2">7</th>
      <td id="T_99ce3_row2_col0" class="data row2 col0">T-008</td>
      <td id="T_99ce3_row2_col1" class="data row2 col1">Bad baseline</td>
      <td id="T_99ce3_row2_col2" class="data row2 col2">high_value_damage</td>
      <td id="T_99ce3_row2_col3" class="data row2 col3">high</td>
      <td id="T_99ce3_row2_col4" class="data row2 col4">gpt-5.4</td>
      <td id="T_99ce3_row2_col5" class="data row2 col5">lookup_customer, lookup_order, lookup_policy, create_refund_case, escalate_to_human</td>
      <td id="T_99ce3_row2_col6" class="data row2 col6">promise_refund_high_value_damage</td>
      <td id="T_99ce3_row2_col7" class="data row2 col7">False</td>
      <td id="T_99ce3_row2_col8" class="data row2 col8">12997</td>
      <td id="T_99ce3_row2_col9" class="data row2 col9">12997</td>
      <td id="T_99ce3_row2_col10" class="data row2 col10">4.91</td>
      <td id="T_99ce3_row2_col11" class="data row2 col11">$0.04136</td>
      <td id="T_99ce3_row2_col12" class="data row2 col12">0.22</td>
      <td id="T_99ce3_row2_col13" class="data row2 col13">I reviewed your message for ticket T-008 and checked the customer profile, order system, policy library, refund workflow, escalation queue, carrier events, billing signals, and internal audit notes. Based on the availabl</td>
    </tr>
    <tr>
      <th id="T_99ce3_level0_row3" class="row_heading level0 row3">41</th>
      <td id="T_99ce3_row3_col0" class="data row3 col0">T-002</td>
      <td id="T_99ce3_row3_col1" class="data row3 col1">Round 4: split workflow</td>
      <td id="T_99ce3_row3_col2" class="data row3 col2">damaged_delivery</td>
      <td id="T_99ce3_row3_col3" class="data row3 col3">medium</td>
      <td id="T_99ce3_row3_col4" class="data row3 col4">gpt-5.4-mini</td>
      <td id="T_99ce3_row3_col5" class="data row3 col5">lookup_order, lookup_policy</td>
      <td id="T_99ce3_row3_col6" class="data row3 col6">request_photo_then_offer_replacement</td>
      <td id="T_99ce3_row3_col7" class="data row3 col7">True</td>
      <td id="T_99ce3_row3_col8" class="data row3 col8">2381</td>
      <td id="T_99ce3_row3_col9" class="data row3 col9">2940</td>
      <td id="T_99ce3_row3_col10" class="data row3 col10">1.26</td>
      <td id="T_99ce3_row3_col11" class="data row3 col11">$0.00097</td>
      <td id="T_99ce3_row3_col12" class="data row3 col12">0.98</td>
      <td id="T_99ce3_row3_col13" class="data row3 col13">I can help with a replacement. Please reply with a photo of the cracked blender and packaging, and we can start the replacement or refund process under the damaged-delivery policy.</td>
    </tr>
    <tr>
      <th id="T_99ce3_level0_row4" class="row_heading level0 row4">43</th>
      <td id="T_99ce3_row4_col0" class="data row4 col0">T-004</td>
      <td id="T_99ce3_row4_col1" class="data row4 col1">Round 4: split workflow</td>
      <td id="T_99ce3_row4_col2" class="data row4 col2">billing_issue</td>
      <td id="T_99ce3_row4_col3" class="data row4 col3">medium</td>
      <td id="T_99ce3_row4_col4" class="data row4 col4">gpt-5.4-mini</td>
      <td id="T_99ce3_row4_col5" class="data row4 col5">lookup_order, lookup_policy, escalate_to_human</td>
      <td id="T_99ce3_row4_col6" class="data row4 col6">escalate_billing_review</td>
      <td id="T_99ce3_row4_col7" class="data row4 col7">True</td>
      <td id="T_99ce3_row4_col8" class="data row4 col8">2401</td>
      <td id="T_99ce3_row4_col9" class="data row4 col9">2942</td>
      <td id="T_99ce3_row4_col10" class="data row4 col10">1.41</td>
      <td id="T_99ce3_row4_col11" class="data row4 col11">$0.00103</td>
      <td id="T_99ce3_row4_col12" class="data row4 col12">0.98</td>
      <td id="T_99ce3_row4_col13" class="data row4 col13">I found a duplicate-charge signal and sent this to billing review. The billing team will verify the charge before any refund is confirmed.</td>
    </tr>
    <tr>
      <th id="T_99ce3_level0_row5" class="row_heading level0 row5">47</th>
      <td id="T_99ce3_row5_col0" class="data row5 col0">T-008</td>
      <td id="T_99ce3_row5_col1" class="data row5 col1">Round 4: split workflow</td>
      <td id="T_99ce3_row5_col2" class="data row5 col2">high_value_damage</td>
      <td id="T_99ce3_row5_col3" class="data row5 col3">high</td>
      <td id="T_99ce3_row5_col4" class="data row5 col4">gpt-5.4</td>
      <td id="T_99ce3_row5_col5" class="data row5 col5">lookup_order, lookup_policy, escalate_to_human</td>
      <td id="T_99ce3_row5_col6" class="data row5 col6">escalate_high_value_damage</td>
      <td id="T_99ce3_row5_col7" class="data row5 col7">True</td>
      <td id="T_99ce3_row5_col8" class="data row5 col8">2492</td>
      <td id="T_99ce3_row5_col9" class="data row5 col9">3063</td>
      <td id="T_99ce3_row5_col10" class="data row5 col10">2.03</td>
      <td id="T_99ce3_row5_col11" class="data row5 col11">$0.00381</td>
      <td id="T_99ce3_row5_col12" class="data row5 col12">0.99</td>
      <td id="T_99ce3_row5_col13" class="data row5 col13">I am sorry the item arrived damaged. Because this is a high-value item, I escalated it for human review. Please attach photos of the item and packaging.</td>
    </tr>
  </tbody>
</table>

```python
walkthrough_delta = (
    walkthrough.pivot(index="ticket_id", columns="variant", values=["sync_tokens", "total_tokens", "latency_s", "cost_usd", "quality_score"])
    .copy()
)

walkthrough_delta[("delta", "sync_tokens_saved")] = walkthrough_delta[("sync_tokens", "00_bad_baseline")] - walkthrough_delta[("sync_tokens", "04_split_workflow")]
walkthrough_delta[("delta", "total_tokens_saved")] = walkthrough_delta[("total_tokens", "00_bad_baseline")] - walkthrough_delta[("total_tokens", "04_split_workflow")]
walkthrough_delta[("delta", "latency_saved_s")] = walkthrough_delta[("latency_s", "00_bad_baseline")] - walkthrough_delta[("latency_s", "04_split_workflow")]
walkthrough_delta[("delta", "cost_saved_usd")] = walkthrough_delta[("cost_usd", "00_bad_baseline")] - walkthrough_delta[("cost_usd", "04_split_workflow")]
walkthrough_delta[("delta", "quality_change")] = walkthrough_delta[("quality_score", "04_split_workflow")] - walkthrough_delta[("quality_score", "00_bad_baseline")]

display(
    walkthrough_delta[["delta"]].style.format(
        {
            ("delta", "sync_tokens_saved"): "{:,.0f}",
            ("delta", "total_tokens_saved"): "{:,.0f}",
            ("delta", "latency_saved_s"): "{:.2f}",
            ("delta", "cost_saved_usd"): "${:.5f}",
            ("delta", "quality_change"): "{:+.2f}",
        }
    )
)
```

<table id="T_8306c">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_8306c_level0_col0" class="col_heading level0 col0" colspan="5">delta</th>
    </tr>
    <tr>
      <th class="index_name level1">variant</th>
      <th id="T_8306c_level1_col0" class="col_heading level1 col0">sync_tokens_saved</th>
      <th id="T_8306c_level1_col1" class="col_heading level1 col1">total_tokens_saved</th>
      <th id="T_8306c_level1_col2" class="col_heading level1 col2">latency_saved_s</th>
      <th id="T_8306c_level1_col3" class="col_heading level1 col3">cost_saved_usd</th>
      <th id="T_8306c_level1_col4" class="col_heading level1 col4">quality_change</th>
    </tr>
    <tr>
      <th class="index_name level0">ticket_id</th>
      <th class="blank col0"> </th>
      <th class="blank col1"> </th>
      <th class="blank col2"> </th>
      <th class="blank col3"> </th>
      <th class="blank col4"> </th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_8306c_level0_row0" class="row_heading level0 row0">T-002</th>
      <td id="T_8306c_row0_col0" class="data row0 col0">10,536</td>
      <td id="T_8306c_row0_col1" class="data row0 col1">9,977</td>
      <td id="T_8306c_row0_col2" class="data row0 col2">3.62</td>
      <td id="T_8306c_row0_col3" class="data row0 col3">$0.03937</td>
      <td id="T_8306c_row0_col4" class="data row0 col4">+0.33</td>
    </tr>
    <tr>
      <th id="T_8306c_level0_row1" class="row_heading level0 row1">T-004</th>
      <td id="T_8306c_row1_col0" class="data row1 col0">10,429</td>
      <td id="T_8306c_row1_col1" class="data row1 col1">9,888</td>
      <td id="T_8306c_row1_col2" class="data row1 col2">3.46</td>
      <td id="T_8306c_row1_col3" class="data row1 col3">$0.03935</td>
      <td id="T_8306c_row1_col4" class="data row1 col4">+0.13</td>
    </tr>
    <tr>
      <th id="T_8306c_level0_row2" class="row_heading level0 row2">T-008</th>
      <td id="T_8306c_row2_col0" class="data row2 col0">10,505</td>
      <td id="T_8306c_row2_col1" class="data row2 col1">9,934</td>
      <td id="T_8306c_row2_col2" class="data row2 col2">2.88</td>
      <td id="T_8306c_row2_col3" class="data row2 col3">$0.03754</td>
      <td id="T_8306c_row2_col4" class="data row2 col4">+0.77</td>
    </tr>
  </tbody>
</table>

## Before and after summary

The final row includes both synchronous customer-path cost and the modeled async follow-up cost. `mean_sync_tokens` is the customer-facing path; `mean_total_tokens` also includes background QA/tagging work after the workflow split.

The strongest result is not from a single trick. It comes from applying levers in a safe order:

establish a baseline -> prompt/output controls -> tool control -> basic context hygiene -> model routing -> caching -> cache-aware context tuning -> split workflow -> processing tier

The key engineering habit is to optimize per step, not globally. A routine classifier, a high-risk refund dispute, a customer-facing response, and an offline QA tagger should not have the same model, context, tools, latency target, or service tier.


```python
before_after = summary[summary["variant"].isin(["00_bad_baseline", "04_split_workflow"])].copy()
display(
    before_after[
        [
            "variant_label",
            "mean_quality",
            "policy_compliance",
            "action_accuracy",
            "escalation_accuracy",
            "mean_tool_calls",
            "mean_extra_tool_calls",
            "mean_sync_tokens",
            "mean_total_tokens",
            "mean_cached_tokens",
            "p50_latency_s",
            "sync_cost_per_ticket_usd",
            "background_cost_per_ticket_usd",
            "cost_per_ticket_usd",
            "monthly_cost_at_100k_tickets",
        ]
    ].style.format(
        {
            "mean_quality": "{:.2f}",
            "policy_compliance": "{:.0%}",
            "action_accuracy": "{:.0%}",
            "escalation_accuracy": "{:.0%}",
            "mean_tool_calls": "{:.1f}",
            "mean_extra_tool_calls": "{:.1f}",
            "mean_sync_tokens": "{:,.0f}",
            "mean_total_tokens": "{:,.0f}",
            "mean_cached_tokens": "{:,.0f}",
            "p50_latency_s": "{:.2f}",
            "sync_cost_per_ticket_usd": "${:.5f}",
            "background_cost_per_ticket_usd": "${:.5f}",
            "cost_per_ticket_usd": "${:.5f}",
            "monthly_cost_at_100k_tickets": "${:,.0f}",
        }
    )
)
```

<table id="T_a4225">
  <thead>
    <tr>
      <th class="blank level0"> </th>
      <th id="T_a4225_level0_col0" class="col_heading level0 col0">variant_label</th>
      <th id="T_a4225_level0_col1" class="col_heading level0 col1">mean_quality</th>
      <th id="T_a4225_level0_col2" class="col_heading level0 col2">policy_compliance</th>
      <th id="T_a4225_level0_col3" class="col_heading level0 col3">action_accuracy</th>
      <th id="T_a4225_level0_col4" class="col_heading level0 col4">escalation_accuracy</th>
      <th id="T_a4225_level0_col5" class="col_heading level0 col5">mean_tool_calls</th>
      <th id="T_a4225_level0_col6" class="col_heading level0 col6">mean_extra_tool_calls</th>
      <th id="T_a4225_level0_col7" class="col_heading level0 col7">mean_sync_tokens</th>
      <th id="T_a4225_level0_col8" class="col_heading level0 col8">mean_total_tokens</th>
      <th id="T_a4225_level0_col9" class="col_heading level0 col9">mean_cached_tokens</th>
      <th id="T_a4225_level0_col10" class="col_heading level0 col10">p50_latency_s</th>
      <th id="T_a4225_level0_col11" class="col_heading level0 col11">sync_cost_per_ticket_usd</th>
      <th id="T_a4225_level0_col12" class="col_heading level0 col12">background_cost_per_ticket_usd</th>
      <th id="T_a4225_level0_col13" class="col_heading level0 col13">cost_per_ticket_usd</th>
      <th id="T_a4225_level0_col14" class="col_heading level0 col14">monthly_cost_at_100k_tickets</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_a4225_level0_row0" class="row_heading level0 row0">0</th>
      <td id="T_a4225_row0_col0" class="data row0 col0">Bad baseline</td>
      <td id="T_a4225_row0_col1" class="data row0 col1">0.51</td>
      <td id="T_a4225_row0_col2" class="data row0 col2">10%</td>
      <td id="T_a4225_row0_col3" class="data row0 col3">60%</td>
      <td id="T_a4225_row0_col4" class="data row0 col4">70%</td>
      <td id="T_a4225_row0_col5" class="data row0 col5">5.0</td>
      <td id="T_a4225_row0_col6" class="data row0 col6">2.4</td>
      <td id="T_a4225_row0_col7" class="data row0 col7">11,935</td>
      <td id="T_a4225_row0_col8" class="data row0 col8">11,935</td>
      <td id="T_a4225_row0_col9" class="data row0 col9">0</td>
      <td id="T_a4225_row0_col10" class="data row0 col10">4.88</td>
      <td id="T_a4225_row0_col11" class="data row0 col11">$0.03813</td>
      <td id="T_a4225_row0_col12" class="data row0 col12">$0.00000</td>
      <td id="T_a4225_row0_col13" class="data row0 col13">$0.03813</td>
      <td id="T_a4225_row0_col14" class="data row0 col14">$3,813</td>
    </tr>
    <tr>
      <th id="T_a4225_level0_row1" class="row_heading level0 row1">4</th>
      <td id="T_a4225_row1_col0" class="data row1 col0">Round 4: split workflow</td>
      <td id="T_a4225_row1_col1" class="data row1 col1">0.98</td>
      <td id="T_a4225_row1_col2" class="data row1 col2">100%</td>
      <td id="T_a4225_row1_col3" class="data row1 col3">100%</td>
      <td id="T_a4225_row1_col4" class="data row1 col4">100%</td>
      <td id="T_a4225_row1_col5" class="data row1 col5">2.6</td>
      <td id="T_a4225_row1_col6" class="data row1 col6">0.0</td>
      <td id="T_a4225_row1_col7" class="data row1 col7">2,412</td>
      <td id="T_a4225_row1_col8" class="data row1 col8">2,974</td>
      <td id="T_a4225_row1_col9" class="data row1 col9">1,779</td>
      <td id="T_a4225_row1_col10" class="data row1 col10">1.41</td>
      <td id="T_a4225_row1_col11" class="data row1 col11">$0.00194</td>
      <td id="T_a4225_row1_col12" class="data row1 col12">$0.00010</td>
      <td id="T_a4225_row1_col13" class="data row1 col13">$0.00204</td>
      <td id="T_a4225_row1_col14" class="data row1 col14">$204</td>
    </tr>
  </tbody>
</table>

### Recommended tuning order

1. Baseline
2. Prompt/output controls
3. Tool control
4. Context hygiene
5. Model routing
6. Prompt caching
7. Cache-aware context
8. Split workflow
9. Processing tier


## Conclusion

Cost optimization for support agents works best as a measured sequence of small changes, not as a single model swap or prompt rewrite. Start by building a baseline that exposes where tokens, tool calls, latency, quality failures, and spend are going. Then tighten prompt and output controls, restrict tool use, reduce tool payloads, trim context, route simple work to smaller models, make stable prefixes cache-friendly, and move non-customer-facing work out of the synchronous path.

The main principle is to spend capability where it protects quality. A routine order-status question, a structured triage step, a policy-heavy refund dispute, and an offline QA tagger should not use the same model, context, tools, or latency tier. The optimized system should be cheaper because it is more disciplined, not because it blindly removes safeguards.

Before shipping changes, validate them with representative evals and trace metrics. Track quality score, policy compliance, action accuracy, escalation accuracy, tool-call count, token usage, cached-token volume, p50 and p95 latency, synchronous cost, async follow-up cost, and total cost per ticket. A configuration is only better if it lowers cost while preserving the support quality bar.