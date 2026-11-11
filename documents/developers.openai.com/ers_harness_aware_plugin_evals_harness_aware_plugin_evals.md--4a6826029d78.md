# Harness-aware evaluation of plugins

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Overview

A plugin that scores well in your own evaluation can still fail once it runs inside the product it
ships in. The harness around the model accounts for much of that gap, since it controls the prompt
the model sees and the tools it can reach. This article runs one set of test cases at three levels
of fidelity and shows how to trace a difference back to the level that caused it.

Models often need current, specialized data and actions that training alone cannot provide. A
[plugin](https://developers.openai.com/plugins/concepts/plugins) can package skills or an MCP server
with callable tools alongside natural-language instructions. This plugin connects a Codex harness,
now part of the ChatGPT desktop app, to Bureau of Labor Statistics (BLS) data.
Because the [BLS API](https://www.bls.gov/developers/) requires known series IDs, the plugin first
resolves a user's question into ranked candidate series.

A plugin like this one is best evaluated across multiple levels, to balance speed, cost, and
fidelity. The same model can
resolve every ambiguous query correctly in a small, controlled loop, then barely call a tool
once it's running inside a real agent. A score from one setup doesn't transfer to the other, since
it measures the setup as much as it measures the model.

| Approach                           | What it tests                                                                                       | What it misses                                                                                                                                 | What it requires                                                                                            | Cost     | Fidelity                                         |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------ |
| **Direct tool tests**         | Structured inputs sent directly to the tools, ideal for debugging tool logic                        | Natural-language interpretation and tool selection                                                                                             | Tool code and a structured corpus                                                                           | Free     | Lowest                                           |
| **Standalone function-calling loop** | Natural-language interpretation and tool selection in a controlled function-calling loop over MCP   | Product harness behavior                                                                                                                       | A running MCP server, model API access, and the loop code                                                   | Moderate | Moderate                                         |
| **Product harness**           | The same queries run through the [Codex](https://openai.com/codex/) harness with the plugin installed | Client-specific behavior that the evaluation setup might not replicate. Compare representative samples with the target client to identify gaps | A running MCP server, installed plugin, Codex authentication (here with API key), and harness configuration | Highest  | Highest, short of the ChatGPT desktop app itself |

The walkthrough uses a simplified example plugin that runs on synthetic data and deliberately
covers only part of the domain, so evaluation failures show up. It also uses a curated set of five
evaluation cases.

The results chapter reports a separate evaluation of the production BLS plugin, 108 questions
across 56 BLS surveys. Its code and data do not ship with this article.



## Setup

The runnable example for this article ships alongside it. The companion [README](https://github.com/openai/openai-cookbook/blob/main/examples/partners/harness_aware_plugin_evals/README.md) lists the
prerequisites and walks through every step in detail,
while the [Makefile](https://github.com/openai/openai-cookbook/blob/main/examples/partners/harness_aware_plugin_evals/Makefile) wraps each one in a single target.

The BLS domain is too dense to teach evaluation mechanics on directly. From here on,
the article works against a miniature of it, small enough to read in full and
to run on a laptop in minutes.



### Dependencies

The example needs [uv](https://docs.astral.sh/uv/getting-started/installation/),
[Node.js with npm](https://nodejs.org/en/download), and an OpenAI API key for the runs
that call a model.

The Python dependencies install from the shipped lockfile into the kernel's environment:

```python
!uv sync --active --inexact --no-dev --quiet
```

Copy `.env.example` to `.env` and fill in the key. The standalone loop takes its configuration from
`.env`. Codex takes the model and key from `.env` and the server URL from the plugin's
`.mcp.json`.

The direct tool tests do not use `.env` and cost nothing.
The other two approaches require a valid OpenAI API key and make paid model calls.
A run costs roughly $0.01 at API prices with the default settings.
Set `EVAL_MODEL` to a model your key can reach. It is independent of the models compared in
the results chapter.

Because these two approaches call the MCP server over HTTP, the server has to be running
before either eval starts. `make server` runs it in the foreground, so it needs its own terminal.

The notebook that ships with this article costs nothing to run. The direct tool tests run live.
The other two approaches replay the recorded runs under `data/`. With `RUN_LIVE=1`, the
standalone loop and the Codex run without server instructions go live.
The Codex run with server instructions stays recorded unless you
reproduce it by hand.
`prepare()` in `notebook_setup.py` loads `.env` and points Codex at this example. In
live mode, it also checks the key, clears `outputs/`, writes the Codex config, and starts the
server if needed:

```python
from notebook_setup import prepare, stop_server

RUN_LIVE = prepare()
```

[Promptfoo](https://www.promptfoo.dev/) is an open-source eval runner. It loads test cases from a
YAML file, sends each to a provider (the model or script that answers it), and grades the output
with assertions. It runs both the standalone loop and Codex in this example, and its config file
contains the test cases all three approaches share. Install the Node packages, including promptfoo,
from the lockfile:

```python
if RUN_LIVE:
    !npm ci --silent
```

### The example plugin

The article keeps four terms apart:

- Tool: a single function exposed to the model, defined by a schema for its parameters.
- MCP server: a process that implements the Model Context Protocol and publishes callable tools
  to clients.
- Plugin: a package that bundles those parts with the metadata a product needs to install it.
- Harness: everything around the model at run time, including the agent loop, prompt
  formatting, tool call execution, turn limits, and sandbox policy.

The server exposes two tools, both defined in `server.py` and served over HTTP through
[FastMCP](https://gofastmcp.com/). `resolve(indicators)` takes one or more economic indicators
and returns a ranked list of candidate BLS series, each with a confidence score.
`fetch_bls_data(series_ids)` takes series IDs and returns their observations, or an error record
for an ID the catalog does not hold.

Behind those two tools sits synthetic fixture data built to reproduce, in miniature, three
properties of the real domain (a default among several valid answers, a true ambiguity, and a data
gap), with CPI deliberately left out. The series IDs look like real BLS codes,
such as `LNS14000000` and `CES0000000001`, but have no internal structure of their own. Three
indicators represent the three properties:

- `unemployment rate` has a deliberate ambiguity. `resolve` returns the seasonally adjusted
  series and the unadjusted one, ranked, with the adjusted version as the conventional default, and
  leaves the choice to the caller.
- `employment` returns two candidates that measure different things, tied at the same confidence:
  the household survey's employment level and nonfarm payrolls, with no default to fall back on.
- `consumer price index` has no match. The resolver returns an empty candidate list
  alongside a note saying the gap is definitive.

Calling `resolve` directly shows all three at once:

```python
from server import IndicatorQuery, resolve

resolve(indicators=[
    IndicatorQuery(indicator="unemployment rate"),
    IndicatorQuery(indicator="employment"),
    IndicatorQuery(indicator="consumer price index"),
])
```

```text
{'results': [{'indicator': 'unemployment rate',
   'candidates': [{'series_id': 'LNS14000000',
     'title': 'Unemployment Rate - Seasonally Adjusted',
     'confidence': 1.0},
    {'series_id': 'LNU04000000',
     'title': 'Unemployment Rate - Not Seasonally Adjusted',
     'confidence': 0.6}]},
  {'indicator': 'employment',
   'candidates': [{'series_id': 'LNS12000000',
     'title': 'Employment Level - Seasonally Adjusted',
     'confidence': 0.5},
    {'series_id': 'CES0000000001',
     'title': 'All Employees, Total Nonfarm - Seasonally Adjusted',
     'confidence': 0.5}]},
  {'indicator': 'consumer price index',
   'candidates': [],
   'note': 'No series in this catalog covers that indicator. This is a definitive answer, not a transient failure.'}]}
```

### The example dataset

Every case in the example corpus has two forms side by side: a structured field the
deterministic check passes to the resolver, and a natural-language query that a
model has to turn into the same request on its own. `expected_series_ids` is the shared expectation
field. An empty string marks a case
where no series should be fetched. The ambiguous case has one extra field,
`expected_top_ids`: the resolver should return both tied candidates, while the model should
fetch nothing and ask. All five cases are in one file, `promptfooconfig.yaml`, so
every approach reads the same corpus. Three of them appear below:

```yaml
tests:
  - description: unemployment-rate
    vars:
      indicator: unemployment rate
      query: What is the U.S. unemployment rate?
      expected_tools: "resolve,fetch_bls_data"
      expected_series_ids: "LNS14000000"
    metadata:
      mechanism: ambiguous_default
      expected_type: exact

  - description: consumer-price-index
    vars:
      indicator: consumer price index
      query: What is the current consumer price index?
      expected_tools: "resolve"
      expected_series_ids: ""
    metadata:
      mechanism: coverage_gap
      expected_type: gap

  - description: employment-ambiguous
    vars:
      indicator: employment
      query: What is U.S. employment?
      expected_tools: "resolve"
      expected_series_ids: ""
      expected_top_ids: "LNS12000000,CES0000000001"
    metadata:
      mechanism: ambiguous_concept
      expected_type: clarify

```

`mechanism` tags what a case tests and `expected_type` what counts as a correct answer. Both
are stored as promptfoo metadata. The grader does not use them. They show up in the run report
and let you filter a run by those fields:

```shell
npx promptfoo eval -c promptfooconfig.yaml --filter-metadata mechanism=coverage_gap
```

With that filter, you can spot a pattern like "the model only fails on coverage gaps" without reading
every row manually.



## Direct tool tests: A deterministic check with no model in the loop

The direct tool tests run this same example corpus's structured form through the plugin's `resolve`
tool. There is no natural-language question to interpret and no model deciding which tool to
call. The check loads `promptfooconfig.yaml` and calls `resolve` directly from `server.py`, with no
MCP client, promptfoo, or network involved.

```python
import yaml

from server import IndicatorQuery, resolve

with open("promptfooconfig.yaml") as f:
    CASES = [test["vars"] for test in yaml.safe_load(f)["tests"]]


def top_candidates(indicator: str) -> set[str]:
    result = resolve(indicators=[IndicatorQuery(indicator=indicator)])
    candidates = result["results"][0]["candidates"]
    if not candidates:
        return set()
    best = max(candidate["confidence"] for candidate in candidates)
    return {c["series_id"] for c in candidates if c["confidence"] == best}


top_candidates("consumer price index")
```

```text
set()
```

The runner compares that set against each case's expectation and prints one line per case.
The consumer price index case expects no series because it isn't one of the four
indicators the example plugin recognizes. The runner also checks that `resolve` returns an empty
candidate list there instead of guessing.
`level_one.py` runs all five cases in about a second:

```python
%run level_one.py
```

```text
PASS  'unemployment rate'                 -> LNS14000000
PASS  'labor force participation rate'    -> LNS11300000
PASS  'nonfarm payroll employment'        -> CES0000000001
PASS  'consumer price index'              -> None
PASS  'employment'                        -> CES0000000001, LNS12000000

5/5 passed
```

Strengths of the direct tool tests include:

- Fast and free: it needs no API key, network call, or model.
- Deterministic: the same input produces the same output on every run, without the
  run-to-run noise a model would add, and the script exits non-zero when a case fails, so it
  drops into CI.
- Precisely diagnostic: a failure points at the resolver's own logic, with no
  question about whether the model or the harness caused it.

The direct tool tests do not check whether a model can turn a plain-language question into appropriate tool calls and a final answer.
The next two approaches add a model, starting with a standalone function-calling loop on the same five cases.



## A standalone function-calling loop

A standalone evaluation uses a small, application-owned function-calling loop instead of a
full agent harness such as Codex. The model receives the MCP tools, chooses which ones to
call, observes their results, and produces a final answer.

The main advantages are:

- Lower cost: the same query uses fewer tokens than it would inside a full agent
  harness.
- Simple setup: there is no plugin installation, agent home directory, shell, approval
  policy, or containerized Codex runtime.
- Straightforward debugging: no hidden behavior, one configuration file, and failures that
  are easy to isolate.

The code snippets can be adapted to a different MCP server by changing the prompts and the tool
names. Promptfoo runs this example, but another eval runner can implement the same three
approaches.



### The function-calling loop

The loop uses the [Responses API](https://developers.openai.com/api/reference/responses/overview). It exposes
MCP tools and records every call for later inspection. It carries the whole conversation in `input` and sets `store: False`, so it needs no
server-side state and works on a zero-data-retention key.

The tools the server advertises become the tools the model sees:

```python
async with AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]) as openai, Client(mcp_url) as mcp:
    mcp_tools = await mcp.list_tools()
    tools = [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        }
        for tool in mcp_tools
    ]
```

Each step sends the whole conversation, and a response that asks for no tool ends the run:

```python
for step in range(max_steps + 1):
    response = await openai.responses.create(input=conversation, **request)
    function_calls = [item for item in response.output if item.type == "function_call"]
    if not function_calls:
        return {
            "answer": response.output_text,
            "tool_calls": recorded_calls,
            "completed": True,
        }
    if step == max_steps:
        break

    # The API rejects round-tripped items that still carry null-valued fields.
    conversation += [item.model_dump(exclude_none=True) for item in response.output]
    for call in function_calls:
        arguments = json.loads(call.arguments or "{}")
        result = await mcp.call_tool(call.name, arguments)
        recorded_calls.append({"name": call.name, "arguments": arguments, "result": result.structured_content})
```

Each tool result goes back into the conversation as a `function_call_output` item, so the next
step sees it.



### The assertion

The standalone loop and Codex share `grade` in `eval_grading.py`. It checks the tool calls
of a run, not the answer text. A case passes when the expected tools ran, the expected series
were returned, no other series was fetched, and the run finished with a non-empty answer. The
"no other series" rule also catches a made-up ID fetched next to a real one.
For `employment-ambiguous`, it checks that `resolve` was called and neither candidate was
fetched. It cannot tell whether that answer asks the user to clarify, or whether any answer states the
retrieved value. None of these checks proves the answer is correct. A shipped evaluation also
needs an answer-level check, for example one of the [promptfoo assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/).
The five-case counts in the walkthrough come from this grader. The production pass rates come
from a separate LLM rubric judge.

Calling `grade` on a hand-written run that invented a CPI series returns this verdict:

```python
from eval_grading import grade

invented = [{"name": "resolve", "arguments": {"indicators": ["consumer price index"]}, "result": {}},
            {"name": "fetch_bls_data", "arguments": {"series_ids": ["CUUR0000SA0"]}, "result": {}}]
grade(invented, {"expected_tools": "resolve", "expected_series_ids": ""}, "unavailable", completed=True)
```

```text
{'pass': False,
 'score': 0.0,
 'reason': "fetched series outside the expectation: ['CUUR0000SA0']"}
```

### Wiring the dataset to the provider

The dataset is the same `promptfooconfig.yaml` shown in Setup, `tests` block included. Each
case's `vars.query` is the natural-language half of the corpus, and `vars.expected_series_ids`
is the shared verdict. The rest of the file wires that dataset to the provider and the
assertion:

```yaml
description: Standalone BLS MCP function-calling evaluation

providers:
  - id: file://provider.py
    label: standalone-mcp
    config:
      model: "{{ env.EVAL_MODEL }}"
      model_reasoning_effort: "{{ env.EVAL_REASONING_EFFORT | default('medium', true) }}"
      mcp_url: "{{ env.MCP_URL }}"

prompts:
  - "{{query}}"

defaultTest:
  assert:
    - type: python
      value: file://assert_result.py
```



### Running the evaluation

The eval is one promptfoo invocation. `--no-cache` keeps
repeats as real model runs instead of promptfoo replays, and the run writes its whole trace to
`outputs/l2-results.json`:

```python
if RUN_LIVE:
    !npx promptfoo eval -c promptfooconfig.yaml --no-cache --output outputs/l2-results.json
```

A run with failing cases exits non-zero, which the Codex run below does on purpose, so the verdict comes
from the grading further down instead.

![Standalone loop Promptfoo web report](https://developers.openai.com/cookbook/assets/images/harness-aware-level-2-web.png)

*The promptfoo report for the standalone loop's recorded five-case run. Each row is one case, and the
Outputs column holds the model's final answer alongside the recorded tool calls the grader
reads.*

In the included recorded run, all five cases pass, including the consumer price index case.
`resolve` returns no candidate, and the loop's system prompt forbids invented series IDs, so the
model reports the gap. The same case fails under Codex.



## Product harness: Codex

Promptfoo's `openai:codex-sdk` provider sends the same five queries to Codex. It starts Codex
with a Codex home that has the BLS plugin installed, and adds the prefix a user gets by typing
`@BLS` in the desktop app.

The two setups also get different instructions. The standalone loop's system prompt tells the
model not to invent series IDs and to name both candidates when they tie. Codex gets no such
instruction.



### The Codex provider setup

`config.toml` points at the `.codex-home/` marketplace by absolute path and enables the plugin. The repository
ships `config.toml.example`. A live run writes the path for the current checkout, as `make setup`
does for the terminal.

The same file defines a [permission profile](https://developers.openai.com/codex/permissions)
to scope what a run may reach:

```toml
default_permissions = "eval"

[permissions.eval.filesystem]
":workspace_roots" = "deny"
```

The main provider settings are:

```yaml
providers:
  - id: openai:codex-sdk
    config:
      model: "{{ env.EVAL_MODEL }}"
      working_dir: .
      enable_streaming: true
      cli_env:
        CODEX_HOME: "{{ env.CODEX_HOME }}"
```

The rest of the file sets the reasoning effort, disables network access and web search, turns off
approvals and the git repository check, and points `tests` at `level_3_tests.py`, which loads the
shared corpus.

Handing an agent a shell inside the project folder creates a serious evaluation risk.
`promptfooconfig.yaml` holds the expected answers for every test case, and `.env` holds the live
API key. A model with file access could read them and clear each case from the answer
file. The permission profile prevents this. The `deny` rule locks the directory against
reads and writes to keep the measurement about the plugin. The evaluation still runs, because
the filesystem rules do not apply to MCP traffic over HTTP. Explicit `CODEX_HOME` points Codex
at the plugin. Without it, Codex starts from the user's default home, the BLS plugin does
not load, and the model cannot call `resolve` or `fetch_bls_data`.

The prompt itself stays as the natural-language query. The prefix goes in through
`defaultTest.options.prefix`, and the text below matches what Codex sees when the user adds a
`@BLS` mention in the desktop app.

```yaml
prompts:
  - "{{query}}"

defaultTest:
  options:
    prefix: "[@BLS](plugin://BLS@cookbook-plugins) "
```

![ChatGPT desktop app prefix](https://developers.openai.com/cookbook/assets/images/harness-aware-desktop-prefix.png)

`enable_streaming: true` makes promptfoo retain the Codex item stream in the provider response.
The assertion reads `mcp_tool_call` items from that trace, fails the case when any of them failed,
and normalizes them into the same
`{"name", "arguments", "result"}` format the standalone loop records, so both approaches reach the same grader in
`eval_grading.py`.

```python
mcp_items = [item for item in raw.get("items", []) if item.get("type") == "mcp_tool_call"]
for item in mcp_items:
    if item.get("error") or item.get("status") == "failed":
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"MCP tool call failed: {item.get('tool')}",
        }

calls = [
    {
        "name": item.get("tool"),
        "arguments": _arguments(item),
        "result": (item.get("result") or {}).get("structured_content"),
    }
    for item in mcp_items
]
```

The rest of `assert_codex_result.py` pulls the trace out of the provider response and counts a run
as finished when the provider reported no error and the final response is not empty.



### Running the example

With `.env` filled in and the server running, the plugin goes into that same `CODEX_HOME`, and the
evaluation runs against `promptfooconfig.codex.yaml`. `CODEX_HOME` reaches both commands through the
environment loaded in Setup:

```python
import subprocess

if RUN_LIVE:
    subprocess.run(["npx", "codex", "plugin", "add", "BLS@cookbook-plugins"], check=True)
    !npx promptfoo eval -c promptfooconfig.codex.yaml --no-cache --output outputs/l3-results.json
```

A failed install stops the cell. Codex would otherwise reach no tools, and every case would
fail for the wrong reason. The grading would report all five as missing the tools they
expected.

![Codex Promptfoo web report](https://developers.openai.com/cookbook/assets/images/harness-aware-level-3-web.png)

*The same five cases through the Codex harness, before the server publishes any guidance.
`consumer-price-index` fails because it fetched an ID the resolver never returned, and
`employment-ambiguous` because it fetched candidates the resolver did return instead of asking
which one the user wanted.*

In the runs recorded
under `data/`, the standalone loop passes all five cases while Codex scores three out of five. A fresh
live run may produce a different count because both failures depend on the path the model happens to
take.

The example server has no CPI series, and `resolve` correctly returns
nothing. Codex then supplies an ID on its own: it calls `fetch_bls_data` with `CUUR0000SA0`, the
real BLS CPI ID, which the server never returned. The answer Codex writes is true because
it tells the user the figure is unavailable, but the unsupported fetch fails the case.

The employment case fails differently.
Codex may narrow the request to one measure before calling `resolve`,
choose one of the tied candidates afterward, or fetch both.
The exact path can vary from run to run, but each of those retrieves at least one series
instead of stopping to clarify, so the grader fails it.

The server can give Codex the missing instructions. MCP servers send an
`instructions` field during the
[handshake](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle), which the
specification describes as a hint a client may add to the system prompt. Codex passes it
to the model. The standalone loop uses its own system prompt and ignores the field.

The example leaves that field empty, so a fresh run can still show these failures. One string
on the `FastMCP` constructor provides that guidance:

```python
GUIDANCE = """Answer only from this catalog. Call resolve first, passing the indicator the user
asked about without narrowing it. Pass fetch_bls_data only the series IDs that resolve returned,
never one from your own knowledge. If resolve returns no candidate, say the data is unavailable. If
several candidates tie for the best confidence, do not call fetch_bls_data at all. Name them and ask
which one the user wants."""

mcp = FastMCP("BLS evaluation fixture", instructions=GUIDANCE)
```

After editing `server.py`, restart the MCP server and rerun the Codex eval. The server sends
`instructions` only in its `initialize` response, and a running server keeps sending the old,
empty value.

In the recorded run with the instructions (`data/l3-trace-after.json`), all five Codex cases
pass, and neither the tools nor the resolver changed.

In the recorded runs a case took about 10 seconds under Codex and 25 in the standalone loop.



### Replaying the three runs

The three recorded runs are in `data/`. The graders can evaluate them again without an API
key, server, or Codex login. The run with instructions is always loaded from its recording,
because reproducing it live means applying the code change and rerunning the Codex cell.
`replay.py` regrades all three runs, and `make replay` runs it from a terminal:

```python
%run replay.py
```

```text
Standalone loop: 5/5 from data/l2-trace.json
Codex, empty instructions: 3/5 from data/l3-trace-before.json
    consumer-price-index: fetched series outside the expectation: ['CUUR0000SA0']
    employment-ambiguous: fetched series outside the expectation: ['CES0000000001', 'LNS12000000']
Codex, with instructions: 5/5 from data/l3-trace-after.json
```

The notebook stops the server it started:

```python
stop_server()
```

### A spot check against the ChatGPT desktop app

Every product harness number in this article comes from the OpenAI Codex SDK provider, not from the
ChatGPT desktop app itself. A sanity check on this example shows the same tool calls as the Codex
eval, including the inferred `CUUR0000SA0` ID. A thorough check in an actual project should cover a wider set of examples.

![ChatGPT desktop CPI](https://developers.openai.com/cookbook/assets/images/harness-aware-desktop-cpi.png)

*The consumer price index case run by hand in the ChatGPT desktop app.*



## Reading the results: Model-harness compatibility

The example plugin's CPI case illustrated model-harness compatibility on a small scale: the same five
questions produced different results in the standalone loop and under Codex. The production plugin with live
API calls and more tools has a more typical scope, and the evaluation covers 108 questions across 56 BLS surveys.
The benchmark results come from this 108-question corpus and use an LLM
rubric judge rather than the tool-call checks from the five-case example.

| Setting             | Value                                                                                                                   |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Dataset             | Held-out test split of the production corpus, 108 single-turn questions across 56 BLS surveys                           |
| Judge               | LLM rubric over the final answer, `gpt-5.6-sol`                                                                         |
| Versions            | Codex 0.159.2, promptfoo 0.123.1                                                                                        |
| Repeats             | Table 1 uses one run per model, Tables 2 and 3 use three runs, with the response cache disabled                         |

*The production benchmark configuration.*



### Three models, one harness

Three models run through that corpus under Codex, the product harness.
The model is the only variable:

| Model        | Pass rate | Tool calls / question | Reasoning tokens / question |
| ------------ | --------- | --------------------- | --------------------------- |
| GPT-6.1 Sol  | 0.94      | 4.02                  | 19                          |
| GPT-6 Astra  | 0.94      | 3.74                  | 14                          |
| GPT-6 Luna   | 0.88      | 5.54                  | 1,229                       |

*Table 1: Pass rates and costs for the production plugin under Codex, across the 108-question
primary evaluation dataset, with the same grader for all models.*

GPT-6.1 Sol and GPT-6 Astra differ by one question out of the 108 in the corpus in this run. These
results provide too little evidence to rank the two reliably.

GPT-6 Luna scores lower than the larger models
while spending about 40% more tool calls than GPT-6.1 Sol and over 60 times its reasoning tokens per question.



### Observed gap changes

A gap between models also depends on the harness that produced it. GPT-5-mini is a legacy model, kept as a
comparison because it was the cheap baseline the plugin was developed against. Its drop under Codex
prompted the harness comparison in this article. GPT-6 Luna and GPT-5-mini
are far apart under Codex and much closer in the standalone loop:

| Harness                                      | GPT-6 Luna   | GPT-5-mini |
| -------------------------------------------- | ------------ | ---------- |
| Product harness (Codex)                      | 0.88         | 0.43       |
| Standalone function-calling loop             | 0.74         | 0.64       |

*Table 2: The production plugin across two harnesses, the same questions as Table 1.*

In the standalone loop GPT-6 Luna and GPT-5-mini differ by about 10 points on average and by 1 to
19 points in a single run. Under Codex the gap is much larger. GPT-6 Luna gains 14 points and
GPT-5-mini loses 21 compared with the standalone loop.



### Why GPT-5-mini performs worse under Codex

About half of GPT-5-mini's failures there involve the shell. The model calls the agent's
shell and runs commands that do nothing. About half of its answers end with a question to the user.
Across the whole corpus it calls a tool in about 85 in 100 questions under Codex, against nearly
every question for GPT-6 Luna on that same harness. The standalone loop has no shell. On the
identical corpus there, GPT-5-mini calls a tool in about 95 in 100 questions.



### Why GPT-6 Luna performs worse in the standalone loop

GPT-6 Luna fails for a different reason. In the standalone loop most of its failed answers either say the
requested data is unavailable or end at the loop's step limit.
Under Codex those turns continue, which would explain most of
the extra tool calls per question there, though these runs do not isolate the mechanism.



## Accounting for non-determinism

Treat the pass rates in this article as relative measures. Pass rates differed by 14 and 21 percentage points between the standalone loop and Codex. The repeat study below illustrates how results can vary across runs.

The direct tool tests should return the same verdict every time because they run with no model in the loop.
Runs that involve a model, however, can produce different results across runs of the same configuration:

- A model can choose an alternative path to solve the task.
- An LLM judge can evaluate the same answer differently.
- Differences may also be caused by external updates of the models or the harness.

The same Codex configuration, run three times with GPT-6 Luna over the 108 questions
from the benchmark configuration above, gives the following spread:

| Repeat                      | 1     | 2     | 3     |
| --------------------------- | ----- | ----- | ----- |
| Pass rate                   | 0.88  | 0.89  | 0.86  |
| Tool calls / question       | 5.54  | 5.70  | 5.20  |
| Reasoning tokens / question | 1,229 | 1,195 | 1,146 |

*Table 3: Three repeated runs of the production plugin under Codex.*

- The overall pass rate barely moves: a spread of 3 points across all three runs.
- Individual questions move far more than that spread suggests. 23 of the 108 (21%) flipped between
  a pass and a fail somewhere across the three runs while the aggregate stayed steady.
- Tool calls swing just as hard: one question took 5 tool calls in one repeat and 19 in another.



## Practical takeaways

Use the cheapest approach that can expose the issue you are investigating:

- Run the direct tool tests whenever resolver logic or fixture data changes.
- Use the standalone loop while iterating on tool descriptions, prompts, grading, or model choice.
- Run the product harness for each new model instead of assuming the two approaches agree. If
  they do, iterate in the standalone loop and keep the product harness for release checks and
  results for stakeholders.

Write test cases where a plausible answer is wrong, such as when the correct answer is a short list
of series, a request to clarify ("are prices rising?" can mean consumer or producer prices), or no
data at all. Tag each case with what it tests and what counts as correct, as the example's
`mechanism` and `expected_type` do. A run can then be filtered to the slice under development,
and the same tags show which areas need new test cases most.

Compare eval traces with production runs to catch differences the configuration misses, such as
agent instructions, tool availability, or runtime versions. A pass rate measured once can also look
far steadier than the case-by-case reality underneath it.
Repeat the same cases automatically to measure how stable they are, and treat that
stability as a metric of its own. A system whose verdict on the same question swings between runs
may be less useful than one with a slightly lower average score but more predictable behavior.

Cheaper harnesses and smaller models help during fast iteration, but they only
approximate what ships. Production behavior comes from the combination of the deployed harness
and model. A few things to confirm before trusting that final run:

- The model sees the same framing in the eval that it sees in production, and every config value
  meant to reach it does.
- The same configuration has run more than once with caching turned off.
- Tool calls and reasoning tokens per question are checked alongside pass rate.
- A human has reviewed a representative sample of the answers.



### Trying it yourself

The multi-level structure and the pattern of sharing one dataset and grader are reusable,
but adapting them to another plugin requires changes in the individual components:

| Area                 | Files                                                                 | Action  | What to change                                                                                               |
| -------------------- | --------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------ |
| MCP server           | `server.py`                                                         | Replace | Use the target server and update the MCP URLs consumed by the standalone loop and the plugin.                |
| Test cases           | `promptfooconfig.yaml`                                              | Update  | Supply domain-specific queries, structured inputs, expectations, and metadata.                               |
| Evaluation logic     | `level_one.py`, `eval_grading.py`                                 | Update  | Adapt the direct tool tests and shared grading to the target tool schemas and expectations. The grader checks tool names, argument formats, and expected-result fields, so it has to change when those do. |
| Instructions         | `provider.py` and the MCP server's `instructions`                 | Update  | Align the standalone system prompt and product-visible guidance with the intended behavior. A product harness usually supplies its own system prompt, so guidance for it goes in the tool descriptions or the MCP server's instructions. |
| Plugin configuration | `.codex-home/marketplaces/`, `.mcp.json`, `config.toml.example` | Update  | Set the plugin identity, marketplace location, MCP endpoint, and isolated Codex home.                        |
| Evaluation structure | All three approaches                                                  | Retain  | Keep the separation between direct tool tests, a standalone loop, and the product harness.                    |



## Further reading

- [AI Agents That Matter](https://arxiv.org/abs/2407.01502)
  explains how evaluating agents differs from evaluating models.
- [τ-bench](https://arxiv.org/abs/2406.12045)
  introduces `pass^k`, the probability that all `k` independent attempts succeed.
- [Moving from OpenAI Evals to Promptfoo](https://developers.openai.com/cookbook/examples/evaluation/moving-from-openai-evals-to-promptfoo)
  rebuilds an OpenAI Evals suite in promptfoo case by case.
- [Codex sandboxing](https://developers.openai.com/codex/concepts/sandboxing)
  covers the modes a Codex run can execute under and what each one allows.



## Contributors

This cookbook serves as a joint collaboration effort between OpenAI and [deepsense.ai](https://deepsense.ai/), who built and evaluated the BLS connector.

- [Maciej Domagała](https://www.linkedin.com/in/macdomagala/)
- [Łukasz Dragan](https://www.linkedin.com/in/%C5%82ukasz-d-a22b3986/)
- [Michał Rdzany](https://www.linkedin.com/in/micha%C5%82-rdzany-85567a225/)
- [Danny Wigg](https://www.linkedin.com/in/dannywigg/)