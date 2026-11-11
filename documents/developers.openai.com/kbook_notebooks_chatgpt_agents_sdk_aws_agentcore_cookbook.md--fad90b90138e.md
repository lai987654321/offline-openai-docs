# Build a ChatGPT plugin with the OpenAI Agents SDK and Amazon Bedrock AgentCore

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

In this cookbook, you'll build a private flight assistant for a fictional airline and learn how to connect ChatGPT to an OpenAI Agents SDK workflow backed by Amazon Bedrock. The sample airline is called **Eliza Airlines**; its `ELZ` flights use sample data and cannot be booked, changed, or canceled.

By the end, you'll know how to:

- expose read-only tools to ChatGPT and validate their inputs and outputs;
- connect a private tool server through OpenAI Secure MCP Tunnel;
- run an Agents SDK workflow with a Bedrock model and display its results in a ChatGPT widget;
- check the integration locally, evaluate fresh agent responses, and verify where traces arrive.

The default path runs the agent on your workstation. You'll start with checks that need no cloud credentials, then choose whether to run the agent with Bedrock and connect it to ChatGPT. An existing Amazon Bedrock AgentCore Runtime is an optional hosting alternative; this notebook does not deploy one.

A joint cookbook by Eliza and OpenAI.


## How the pieces fit together

**Model Context Protocol (MCP)** lets ChatGPT discover tools, call them with structured inputs, and receive structured results. The **MCP adapter** in this repository is the server that exposes our three flight tools. It checks the request, runs the agent, and validates the response before returning it to ChatGPT.

![Default request flow: ChatGPT sends a tool call through the hosted tunnel and local tunnel-client to the MCP adapter and local Agents SDK agent. The agent calls Amazon Bedrock and exports traces to AWS.](https://developers.openai.com/cookbook/assets/examples/partners/AWS/chatgpt_agents_sdk_aws_agentcore_cookbook/notebooks/images/cookbook-boundaries.svg)

The arrows follow a tool request. The result returns along the same path, and the **widget**, a small HTML view inside ChatGPT, displays the validated result. In MCP, that result is carried in the `structuredContent` field. The widget does not call the flight backend itself.

The `tunnel-client` on your workstation opens an outbound HTTPS connection to OpenAI's hosted tunnel endpoint. That connection lets ChatGPT reach the adapter at `127.0.0.1:8787/mcp`. This address is **loopback**: it is reachable only on the same machine. You do not need a public MCP URL or an inbound firewall rule.

The **OpenAI Agents SDK** runs the Python workflow and its function tools. **Amazon Bedrock** supplies the model through an OpenAI-compatible endpoint. **AgentCore Observability** receives traces, which record the steps, timing, and errors in a run. A **span** records one operation within a trace, such as a model or tool call.

Two options build on the default path shown above:

- An existing **AgentCore Runtime**, AWS's managed agent hosting service, can run the workflow instead of your workstation. Its owner supplies the Runtime's **Amazon Resource Name (ARN)**, an AWS resource identifier, and an invoke-only role. The owner manages deployment, credentials, and operations.
- `COOKBOOK_TRACING_MODE=dual` adds OpenAI Traces alongside AWS observability. It requires a separate OpenAI Platform trace key. The default, `aws`, exports only to AWS.

Your Platform administrator must provision the hosted tunnel and associate it with your OpenAI organization and ChatGPT workspace. Follow the [README permission matrix](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#enterprise-least-privilege-matrix) before any credentialed step. Your team also owns identity, secret delivery, hosting, and retention. The [architecture guide](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/docs/openai-agentkit-cookbook.md#architecture-boundaries) covers those responsibilities in detail.


## Prerequisites

You'll need basic Python and command-line experience, plus:

- Python 3.10 or newer;
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/), which installs and runs the Python environment;
- JupyterLab from the locked development environment, using the [README launch command](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#optional-notebook-and-developer-checks);
- Node.js 24 or newer and npm for the MCP adapter and evaluation tools.

The local checks use sample data and need no cloud credentials. Live steps require the access listed in the [README permission matrix](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#enterprise-least-privilege-matrix) and can incur model, telemetry, or Runtime charges.

The setup cell locates the repository and imports [notebook helpers](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/notebook_helpers.py). Those helpers handle subprocess timeouts, limited output capture, credential filtering, service cleanup, and evaluation reports. The request and response examples stay in the notebook.


```python
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = next(
    (path for path in (Path.cwd(), *Path.cwd().parents)
     if (path / "runtime-agent" / "pyproject.toml").exists()
     and (path / "mcp-adapter" / "package.json").exists()),
    None,
)
if REPO_ROOT is None:
    raise RuntimeError("Run this notebook from the cookbook repository or notebooks directory.")
RUNTIME_DIR, MCP_DIR = REPO_ROOT / "runtime-agent", REPO_ROOT / "mcp-adapter"
sys.path.insert(0, str(RUNTIME_DIR))

from demo_date import demo_travel_date
from notebook_helpers import (
    live_runtime_environment, local_runtime_service, run,
    run_agent_evaluation, selected_environment,
)

DEMO_TRAVEL_DATE = demo_travel_date()
UV, NODE, NPM = (shutil.which(command) for command in ("uv", "node", "npm"))
if not UV or not NODE or not NPM:
    raise RuntimeError("Install uv and Node.js/npm before executing the notebook.")
print("Repository:", REPO_ROOT)
print("Commit:", run(["git", "rev-parse", "HEAD"], REPO_ROOT).stdout.strip())
for name, command in (("uv", UV), ("Node", NODE), ("npm", NPM)):
    print(name + ":", run([command, "--version"], REPO_ROOT).stdout.strip())
```

## 1. Install the pinned dependencies

A **lockfile** records exact dependency versions. The repository includes `uv.lock` and both npm lockfiles so you can reproduce the tested environment. `uv sync --locked` and `npm ci` fail if a manifest disagrees with its lockfile.


```python
run([UV, "sync", "--locked", "--extra", "dev"], RUNTIME_DIR)
run([NPM, "ci"], RUNTIME_DIR)
run([NPM, "ci"], MCP_DIR)
print("Locked dependency environments are ready.")
```

## 2. Follow a request through the agent

A **schema** defines the fields and values a request or response accepts. [RuntimeRequest](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/schemas.py) validates the action and its arguments before any tool runs. For `search_flights`, it requires an origin, destination, and travel date.

[build_agent](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/agent.py) maps that action to a function tool, a Python function exposed to the model through the Agents SDK. It supplies only the tool for the requested action and tells the model to call it once. The core configuration in `agent.py` is:

```python
Agent(
    name="ChatGPT MCP flight cookbook agent",
    instructions="Call the selected read-only function tool exactly once and return its JSON.",
    model=model or os.environ.get(MODEL_ENV, DEFAULT_MODEL),
    output_type=AgentOutputSchema(dict, strict_json_schema=False),
    model_settings=ModelSettings(
        parallel_tool_calls=False,
        tool_choice=tool_choice,
    ),
    tools=tools,
    tool_use_behavior="stop_on_first_tool",
)
```

Here, `tools` contains the selected function and `tool_choice` is its name. `stop_on_first_tool` returns the tool's output without asking the model to rewrite it. During a real run, `build_bedrock_model()` supplies the Bedrock client and `Runner.run_sync()` executes this agent. The runner validates the returned JSON as a `RuntimeResponse`.

First, build a search agent and inspect its tool without calling a model. The sample date defaults to UTC today plus 45 days; `COOKBOOK_DEMO_TRAVEL_DATE` can pin it for repeatable checks.


```python
from agent import build_agent
from schemas import RuntimeRequest

search_request = RuntimeRequest(
    action="search_flights",
    origin="DAL",
    destination="MDW",
    travel_date=DEMO_TRAVEL_DATE,
)
flight_agent = build_agent(search_request, execution_mode="local")
print("Selected tool:", flight_agent.tools[0].name)
print("After the tool returns:", flight_agent.tool_use_behavior)
```

Now run the Python tests, formatting checks, and type checks, then send the same request through the local entrypoint. `COOKBOOK_FORCE_LOCAL_TOOLS=1` calls the sample functions directly, so this check uses neither a model nor AWS. These functions return the same sample results for the same inputs.

`executionMode` identifies the selected route: `local` or `deployed`. The older `provider: "agentcore-runtime"` field remains for compatibility and does not identify where the agent ran.


```python
run([UV, "run", "pytest", "-q"], RUNTIME_DIR)
run([UV, "run", "ruff", "check", "."], RUNTIME_DIR)
run([UV, "run", "ruff", "format", "--check", "."], RUNTIME_DIR)
run([UV, "run", "pyright"], RUNTIME_DIR)

local_env = selected_environment(overrides={
    "COOKBOOK_FORCE_LOCAL_TOOLS": "1",
    "COOKBOOK_EVENT": search_request.model_dump_json(exclude_none=True),
})
smoke = run([UV, "run", "python", "agent.py"], RUNTIME_DIR, local_env)
local_result = json.loads(smoke.stdout)
assert local_result["provider"] == "agentcore-runtime"
assert local_result["executionMode"] == "local"
assert local_result["action"] == "search_flights"
assert local_result["data"]["flights"]
assert all(flight["travelDate"] == DEMO_TRAVEL_DATE for flight in local_result["data"]["flights"])
print(json.dumps(local_result, indent=2))
```

## 3. Call the Runtime HTTP interface locally

The AgentCore Python SDK supplies two HTTP endpoints: `/ping` reports health, and `/invocations` accepts an agent request. The helper starts this server on port 8080 and stops it when the cell finishes, including on failure. The request below takes a flight from the search result and checks its status using the same date.

This tests the deployed Runtime's interface on your workstation using sample tools. Its entrypoint labels responses `executionMode: "deployed"`; that label alone is not evidence of an AWS deployment.


```python
first_flight = local_result["data"]["flights"][0]
with local_runtime_service(UV, RUNTIME_DIR) as health:
    request = urllib.request.Request(
        "http://127.0.0.1:8080/invocations",
        data=json.dumps({
            "action": "get_live_status",
            "flight_number": first_flight["flightNumber"],
            "origin": first_flight["origin"],
            "destination": first_flight["destination"],
            "travel_date": first_flight["travelDate"],
        }).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        invocation = json.loads(response.read())
    assert health["status"] == "Healthy"
    assert invocation["executionMode"] == "deployed"
    assert invocation["action"] == "get_live_status"
    assert invocation["data"]["flight"]["flightNumber"] == "ELZ1234"
    assert invocation["data"]["flight"]["travelDate"] == DEMO_TRAVEL_DATE
    print("Health:", health)
    print("Invocation:", json.dumps(invocation, indent=2))
```

## 4. Check the MCP adapter and widget

The adapter exposes `search_flights`, `get_upcoming_status`, and `get_live_status` over **Streamable HTTP**, the MCP transport used to exchange messages over HTTP. Each tool accepts a defined input schema and returns an action-specific output schema. The tools are **idempotent**: repeating a call does not change the sample data.

The TypeScript tests exercise tool discovery, calls, response validation, and the AWS invocation code with a fake AWS sender. They also check the widget's versioned resource URI, content type (MIME type), and **Content Security Policy (CSP)**, which restricts the resources it can load. The widget uses `textContent` to display result text without treating it as HTML. These tests make no live AWS calls.

The key boundary is in [server.ts](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/mcp-adapter/server.ts): the adapter returns validated data as `structuredContent`, and [flight-widget.html](https://developers.openai.com/cookbook/assets/examples/partners/AWS/chatgpt_agents_sdk_aws_agentcore_cookbook/mcp-adapter/public/flight-widget.html) renders it when it receives `ui/notifications/tool-result`.


```python
run([NPM, "run", "typecheck"], MCP_DIR)
run([NPM, "test"], MCP_DIR)
run([NPM, "run", "build"], MCP_DIR)

widget = (MCP_DIR / "public" / "flight-widget.html").read_text(encoding="utf-8")
assert "ui/notifications/tool-result" in widget
assert "textContent" in widget
assert "<script src=" not in widget
print("Typed MCP server and self-contained widget validated.")
```

## 5. Evaluate responses and verify traces

**Evaluation** checks whether an output meets expectations. **Tracing** records what happened during execution. This cookbook uses Promptfoo to score responses and AgentCore Observability to inspect runs; those are separate checks.

![Promptfoo scores fresh agent responses before release. AWS receives traces by default, with OpenAI Traces available in dual mode. An optional AWS evaluation path scores a dedicated Runtime's completed spans.](https://developers.openai.com/cookbook/assets/examples/partners/AWS/chatgpt_agents_sdk_aws_agentcore_cookbook/notebooks/images/tracing-evaluation-paths.svg)

[Promptfoo](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/promptfooconfig.agent.cjs) sends three flight scenarios through the local Agents SDK workflow, then checks each response's structure and expected behavior. **AWS Distro for OpenTelemetry (ADOT)** instruments the agent to record spans and export them to AWS. `COOKBOOK_TRACING_MODE=aws` is the default; `dual` also sends traces to OpenAI using a separate `OPENAI_TRACE_API_KEY`.

Start with `eval:agent:validate`, which checks the evaluation configuration without invoking an agent. For another credential-free check, `eval:run` replays stored positive and negative examples, called **fixtures**, through an echo provider that returns them unchanged. That checks the assertions against sample responses.

To evaluate fresh agent responses, set `RUN_PROMPTFOO_AGENT_EVALUATION=1` before starting Jupyter. You can select fewer cases with `PROMPTFOO_AGENT_EVALUATION_CASE_IDS`. The helper runs the guarded command and summarizes the new report. Reports stay in the ignored `runtime-agent/evals/results/` directory; Promptfoo sharing, telemetry, and remote generation are disabled. Real agent runs can incur model and telemetry charges.

A passing report does not confirm trace delivery. Run the trace smoke command and use its **correlation ID**, an identifier shared by records from the same invocation, with the [AWS trace checker](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/docs/tracing-and-publication.md#trace-verification-is-a-separate-step). Allow for ingestion delay. In dual mode, a verifier must also find the matching ID in OpenAI Traces; the notebook does not use an undocumented trace-query API.

[AgentCore Evaluations](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/docs/aws-evaluation.md) provides an optional AWS-native alternative. It invokes a dedicated non-production Runtime, waits for completed CloudWatch spans, and scores them with built-in evaluators. Those evaluators need prompt, response, and tool content, so the Runtime owner must approve and enable content capture there. Evaluation runs separately from ordinary ChatGPT requests.


```python
run([NPM, "run", "eval:agent:validate"], RUNTIME_DIR)
print("Promptfoo actual-agent configuration validated.")

if os.getenv("RUN_PROMPTFOO_AGENT_EVALUATION", "0") == "1":
    evaluation_summary = run_agent_evaluation(NODE, RUNTIME_DIR)
    print(json.dumps(evaluation_summary, indent=2))
else:
    print("Skipped fresh agent runs. Set RUN_PROMPTFOO_AGENT_EVALUATION=1 before starting Jupyter.")
```

## 6. Optionally invoke an existing AWS Runtime

Skip this step if you are following the default local path. For an existing Runtime, this cell makes two real `InvokeAgentRuntime` calls through the AWS SDK: a DAL-to-MDW search, followed by a status check for the first result. It validates both responses and checks that the flight and date stay the same. Trace and session identifiers are omitted from this cell's output.

Before starting Jupyter, set `RUN_LIVE_AWS=1` and the `AWS_PROFILE`, `AGENTCORE_RUNTIME_AGENT_ARN`, and `AGENTCORE_RUNTIME_REGION` supplied by the Runtime owner. The [README launch command](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#optional-notebook-and-developer-checks) loads the private root `.env` and preserves values exported by your credential process. Restart the kernel after configuration changes. The [permission matrix](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#enterprise-least-privilege-matrix) lists the required invoke-only access.


```python
if os.getenv("RUN_LIVE_AWS", "0") == "1":
    if not os.getenv("AGENTCORE_RUNTIME_AGENT_ARN", "").strip():
        raise RuntimeError("Set AGENTCORE_RUNTIME_AGENT_ARN before enabling RUN_LIVE_AWS.")
    live_env = live_runtime_environment(DEMO_TRAVEL_DATE)
    # Call the built runner directly to keep unrelated .env credentials out.
    live = run([NODE, "dist/live-smoke.js"], MCP_DIR, live_env, timeout_seconds=300)
    live_result = json.loads(live.stdout.strip().splitlines()[-1])
    assert live_result["provider"] == "agentcore-runtime"
    assert live_result["executionMode"] == "deployed"
    assert live_result["action"] == "get_live_status"
    assert live_result["flight"]["flightNumber"] == "ELZ1234"
    assert live_result["flight"]["travelDate"] == DEMO_TRAVEL_DATE
    print(json.dumps(live_result, indent=2))
else:
    print("Skipped live AWS invocation. Set RUN_LIVE_AWS=1 after configuring a sandbox runtime.")
```

## 7. Test the plugin connection in ChatGPT through Secure MCP Tunnel

Use the [README connection walkthrough](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#7-connect-the-mcp-server-to-chatgpt) after the local checks pass. If you chose an existing Runtime, complete step 6 first.

1. Start the private MCP server with `npm start` from `mcp-adapter/`; it listens on `http://127.0.0.1:8787/mcp`.
2. Confirm that a Platform administrator created the hosted tunnel, associated it with the correct OpenAI organization and ChatGPT workspace, and gave you the complete tunnel ID and a runtime key with **Tunnels Read + Use**. Then configure an OpenAI `tunnel-client` profile with that tunnel ID and the loopback MCP URL.
3. Run `tunnel-client doctor --profile agentcore-cookbook --explain`, then `tunnel-client run --profile agentcore-cookbook`, and wait for `http://127.0.0.1:8080/readyz`.
4. Enable Developer mode under **Settings → Security and login** before opening [ChatGPT Plugins](https://chatgpt.com/plugins). If the setting or Plugins page is unavailable, ask the workspace administrator to check the workspace policy.
5. On the Plugins page, select the plus button, enter a user-facing name and description, then choose **Tunnel** under **Connection** and select or paste the complete tunnel ID.
6. Choose **No authentication**. The tunnel runtime key authenticates `tunnel-client` to the tunnel service; do not paste it into the plugin form. Create the plugin connection and wait for automatic tool discovery to list `search_flights`, `get_upcoming_status`, and `get_live_status`.
7. Add the plugin connection from the tools menu in a new conversation, then test search, upcoming-status, and live-status prompts.
8. Confirm booking requests cannot select a write tool.

The tunnel client opens the connection outbound. Keep the MCP server on loopback; do not publish port 8787 or add an inbound firewall rule. This step tests the connection in ChatGPT; it does not validate other OpenAI product surfaces.

A successful test gives you a working private plugin connection. Before a public release, your team still needs to arrange a public service endpoint and resolve operating and publishing ownership, licensing, privacy and security reviews, and any required submission approval. The repository's MIT License covers the code; it does not provide release approval. See [publication requirements](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/docs/tracing-and-publication.md#private-testing-is-not-public-distribution).


## Conclusion

You have followed a flight request through validated MCP inputs, an Agents SDK workflow, and a widget that displays the result in ChatGPT. The example shows how a private tool server can use a Bedrock model while keeping credentials out of the widget.

The local checks validate the sample logic and integration contracts without cloud credentials. The optional live steps let you evaluate fresh agent responses, verify trace delivery, and test the private ChatGPT connection in your environment.

To adapt the example:

1. Replace the sample functions in [tools.py](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/tools.py) with read-only calls to an approved service, such as an inventory or order-status API.
2. Update the [Python schemas](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/schemas.py), [MCP tool registrations](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/mcp-adapter/server.ts), [MCP response schemas](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/mcp-adapter/schemas/flight.ts), and [widget](https://developers.openai.com/cookbook/assets/examples/partners/AWS/chatgpt_agents_sdk_aws_agentcore_cookbook/mcp-adapter/public/flight-widget.html) together. Preserve strict validation, read-only annotations, and credential isolation.
3. Add representative successes, malformed inputs, and unsupported actions to the [evaluation fixtures](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/runtime-agent/evals/fixtures/flight-status-results.jsonl). Run local checks before evaluating the real agent.
4. Configure your approved Bedrock model, tunnel, and tracing destinations. Your team can keep the agent local or supply an existing Runtime for hosted execution.

Stop the MCP server and tunnel client when you finish testing; see the [operating instructions](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/README.md#10-everyday-operation). The [architecture guide](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/docs/openai-agentkit-cookbook.md) and [AWS IAM guide](https://developers.openai.com/cookbook/examples/partners/aws/chatgpt_agents_sdk_aws_agentcore_cookbook/docs/aws-iam.md) cover the hosting and access decisions for your own service.


## Contributors

This cookbook is a joint collaboration between OpenAI and Eliza.

- [Rohan Awasthi](https://www.linkedin.com/in/rohan-awasthi-4a5208233/) (Eliza)
- [Chuck Hernandez](https://www.linkedin.com/in/chuck-hernandez/) (Eliza)
- [Syed Ahmed](https://www.linkedin.com/in/syed-a-usanaemeaapeastwest/) (OpenAI)
- [Steven McAteer](https://www.linkedin.com/in/steven-mcateer/) (Eliza)