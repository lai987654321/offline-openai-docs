# Getting Started with OpenAI Models on Amazon Bedrock

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

OpenAI models on Amazon Bedrock expose an OpenAI-compatible Responses API surface for production workflows that need text generation, structured outputs, application tools, direct file inputs, response state, prompt caching, and background work. This cookbook keeps the examples concrete by building a support-assistant workflow for **BrightCart**, a fictional retailer handling delayed and damaged-order replacement requests.

You will use the OpenAI Python SDK for normal application calls and a small raw HTTPS helper when it is useful to inspect the exact request body. The flow starts with setup and a minimal preflight, then layers on response lifecycle, model controls, structured JSON, application tools, file input, state management, caching, background processing, context compaction, operations checks, and cleanup.

You will learn how to:

1. Configure a Bedrock-hosted OpenAI model with Bedrock-specific environment variables.
2. Verify the Responses endpoint and inspect response schema, usage metadata, and normalized errors.
3. Send text requests with both raw HTTPS and the OpenAI SDK.
4. Generate schema-constrained JSON and lighter JSON-mode handoffs.
5. Call application-managed function tools, parallel tools, and custom text tools.
6. Send a direct PDF input, continue stateful and stateless conversations, and carry encrypted reasoning context.
7. Use prompt caching, background mode, compaction, operational smoke checks, and stored-response cleanup.

Prerequisites: a bearer token for OpenAI models on Amazon Bedrock, Python 3.9 or newer, and network access to your Bedrock OpenAI-compatible endpoint.

This guide runs `openai.gpt-5.4` in `us-west-2` by default. To use another supported pairing, change `AWS_REGION`, `BEDROCK_MODEL`, and `BEDROCK_BASE_URL` together before running the setup cells.

| AWS Region | Supported model IDs |
| --- | --- |
| `us-west-2` | `openai.gpt-5.4` |
| `us-east-2` | `openai.gpt-5.5`, `openai.gpt-5.4` |


## 1. Configure Amazon Bedrock

This section prepares the notebook runtime. It installs the small Python stack, reads Bedrock-specific environment variables, creates both a raw HTTPS session and an OpenAI SDK client, discovers model metadata when the endpoint provides it, and defines shared helpers used by later examples.

Set these environment variables before running the notebook. The default pairing is `us-west-2` with `openai.gpt-5.4`.

```bash
export AWS_BEARER_TOKEN_BEDROCK="YOUR_BEDROCK_BEARER_TOKEN"
export AWS_REGION="us-west-2"
export BEDROCK_MODEL="openai.gpt-5.4"
export BEDROCK_BASE_URL="https://bedrock-mantle.${AWS_REGION}.api.aws/openai/v1"
```

The bearer token is read from `AWS_BEARER_TOKEN_BEDROCK`. If it is missing, the setup cell asks for it with a password-style prompt and does not print it.


### 1.1 Install Dependencies

Install the packages used by the notebook. The OpenAI SDK is used for the application examples, `requests` is used for raw HTTPS calls to the Responses endpoint, and `pandas` plus IPython display helpers keep request and response summaries readable in the Cookbook renderer. Inspect the cell output only to confirm the packages installed or were already present.


```python
%pip install -U "openai>=2.28.0" requests pandas ipython --quiet
print("Dependencies installed or already available: openai, requests, pandas, ipython")
```

```text

[1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m24.0[0m[39;49m -> [0m[32;49m26.1.1[0m
[1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49mpip install --upgrade pip[0m
Note: you may need to restart the kernel to use updated packages.
Dependencies installed or already available: openai, requests, pandas, ipython
```

### 1.2 Import Libraries and Defaults

Import the standard libraries, SDK, HTTP client, and display utilities used throughout the notebook. This cell also sets the default Bedrock region and model used when environment variables are not already set. Inspect the printed defaults to confirm the notebook will start from `us-west-2` and `openai.gpt-5.4` unless you override them.


```python
from __future__ import annotations

import base64
import builtins
import html
import json
import os
import shlex
import textwrap
import time
from datetime import date, timedelta
from getpass import getpass
from typing import Any, Callable, Iterable

import pandas as pd
import requests
from IPython.display import HTML, Markdown, display
from openai import OpenAI

DEFAULT_REGION = "us-west-2"
DEFAULT_MODEL = "openai.gpt-5.4"
PREFERRED_MODELS = [DEFAULT_MODEL]


def gpt_version_tuple(model_id: str) -> tuple[int, int] | None:
    normalized = model_id.lower().removeprefix("openai.")
    if not normalized.startswith("gpt-"):
        return None
    version = normalized.removeprefix("gpt-").split("-")[0]
    parts = version.split(".")
    try:
        major = builtins.int(parts[0])
        minor = builtins.int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return None
    return major, minor


def prompt_cache_retention_for_model(model_id: str) -> str:
    version = gpt_version_tuple(model_id)
    if version and version >= (5, 5):
        return "24h"
    return "in_memory"

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", 200)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 160)


def display_wrapped_table(df: pd.DataFrame, *, max_col_width_px: int = 520, index: bool = False) -> None:
    if df.empty:
        display(Markdown("_No rows to display._"))
        return
    table_html = df.to_html(index=index, escape=True, border=0)
    table_html = table_html.replace('<table border="0" class="dataframe">', '<table class="dataframe wrapped-output-table">')
    display(HTML(f"""
    <style>
      .wrapped-output-table {{
        border-collapse: collapse;
        width: 100%;
        table-layout: auto;
        font-size: 13px;
      }}
      .wrapped-output-table th,
      .wrapped-output-table td {{
        border: 1px solid #d0d7de;
        padding: 6px 8px;
        text-align: left;
        vertical-align: top;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        word-break: break-word;
        max-width: {max_col_width_px}px;
      }}
      .wrapped-output-table th {{
        background: #f6f8fa;
        font-weight: 600;
      }}
    </style>
    {table_html}
    """))

print("Imports loaded.")
print("Default region:", DEFAULT_REGION)
print("Default model:", DEFAULT_MODEL)
```

```text
Imports loaded.
Default region: us-west-2
Default model: openai.gpt-5.4
```

### 1.3 Configure Bedrock Credentials and Clients

Read Bedrock configuration from the environment and construct clients. `BEDROCK_BASE_URL` is normalized once, the raw `requests.Session` gets the bearer token in its headers, and the OpenAI SDK client is created explicitly with the same token and base URL. Inspect the rendered table to confirm the selected region, model, endpoint, SDK client configuration, and stored-response cleanup behavior before making live calls.


```python
from __future__ import annotations


def env_value(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def env_flag(name: str, default: bool = False) -> bool:
    value = env_value(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith("/responses"):
        return url[: -len("/responses")]
    return url


def endpoint(path: str) -> str:
    return f"{BEDROCK_BASE_URL}/{path.lstrip('/')}"


def responses_url(base_url: str) -> str:
    return f"{normalize_base_url(base_url)}/responses"


API_TIMEOUT_SECONDS = float(env_value("BEDROCK_REQUEST_TIMEOUT_SECONDS") or "60")
MAX_RETRIES = builtins.int(env_value("BEDROCK_MAX_RETRIES") or "0")
CLEAN_UP_STORED_RESPONSES = env_flag("BEDROCK_CLEANUP_STORED_RESPONSES", True)
FAIL_ON_CHECK_FAILURE = env_flag("BEDROCK_FAIL_ON_CHECK_FAILURE", False)
RUN_RESPONSIVENESS_CHECK = env_flag("BEDROCK_RESPONSIVENESS_CHECK", True)
TRANSIENT_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

AWS_REGION = (env_value("AWS_REGION") or DEFAULT_REGION).strip() or DEFAULT_REGION
BEDROCK_MODEL = (env_value("BEDROCK_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
BEDROCK_BASE_URL = normalize_base_url(
    env_value("BEDROCK_BASE_URL") or f"https://bedrock-mantle.{AWS_REGION}.api.aws/openai/v1"
)
RESPONSES_URL = responses_url(BEDROCK_BASE_URL)
AWS_BEARER_TOKEN_BEDROCK = env_value("AWS_BEARER_TOKEN_BEDROCK")

if not AWS_BEARER_TOKEN_BEDROCK:
    AWS_BEARER_TOKEN_BEDROCK = getpass("Paste your AWS Bedrock bearer token for this kernel session: ").strip()
    if AWS_BEARER_TOKEN_BEDROCK:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = AWS_BEARER_TOKEN_BEDROCK

if not AWS_BEARER_TOKEN_BEDROCK:
    raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK is required to run the live examples.")

http = requests.Session()
http.headers.update({
    "Authorization": f"Bearer {AWS_BEARER_TOKEN_BEDROCK}",
    "Content-Type": "application/json",
})

client = OpenAI(api_key=AWS_BEARER_TOKEN_BEDROCK, base_url=BEDROCK_BASE_URL, max_retries=0)
BASE_URL = BEDROCK_BASE_URL

config_rows = [
    {"setting": "AWS_REGION", "value": AWS_REGION},
    {"setting": "BEDROCK_MODEL", "value": BEDROCK_MODEL},
    {"setting": "BEDROCK_BASE_URL", "value": BEDROCK_BASE_URL},
    {"setting": "SDK client", "value": "OpenAI(api_key=AWS_BEARER_TOKEN_BEDROCK, base_url=BEDROCK_BASE_URL)"},
    {"setting": "cleanup stored responses", "value": CLEAN_UP_STORED_RESPONSES},
]
display_wrapped_table(pd.DataFrame(config_rows), max_col_width_px=680)
```

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>setting</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>AWS_REGION</td>
      <td>us-west-2</td>
    </tr>
    <tr>
      <td>BEDROCK_MODEL</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>BEDROCK_BASE_URL</td>
      <td>https://bedrock-mantle.us-west-2.api.aws/openai/v1</td>
    </tr>
    <tr>
      <td>SDK client</td>
      <td>OpenAI(api_key=AWS_BEARER_TOKEN_BEDROCK, base_url=BEDROCK_BASE_URL)</td>
    </tr>
    <tr>
      <td>cleanup stored responses</td>
      <td>True</td>
    </tr>
  </tbody>
</table>

### 1.4 Discover Available Models

Discover available models when the selected endpoint exposes model-list metadata, then choose the model for the rest of the notebook. If `BEDROCK_MODEL` is set, the notebook uses that value; otherwise it prefers `openai.gpt-5.4`. The model-list call is optional because some compatible endpoints may allow inference even when model metadata is unavailable. Inspect the selected model and any returned catalog rows.


```python
from __future__ import annotations


def list_openai_models(client: OpenAI) -> list[str]:
    return sorted(model.id for model in client.models.list(timeout=API_TIMEOUT_SECONDS).data)


def resolve_model_id(client: OpenAI | None) -> tuple[str, list[str], str | None]:
    configured_model = env_value("BEDROCK_MODEL")
    available_models: list[str] = []
    model_discovery_note: str | None = None

    if client is not None:
        try:
            available_models = list_openai_models(client)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 404:
                model_discovery_note = "This endpoint did not expose model-list metadata. The guide will continue with the configured model."
            else:
                model_discovery_note = f"Model-list metadata could not be listed. The guide will continue with the configured model. Details: {builtins.str(exc)[:240]}"

    if configured_model:
        return configured_model, available_models, model_discovery_note

    for candidate in PREFERRED_MODELS:
        if candidate in available_models:
            return candidate, available_models, model_discovery_note

    for candidate in available_models:
        if candidate.startswith("openai."):
            return candidate, available_models, model_discovery_note

    if available_models:
        return available_models[0], available_models, model_discovery_note

    return PREFERRED_MODELS[0], available_models, model_discovery_note


EXPLICIT_MODEL = env_value("BEDROCK_MODEL")
MODEL_ID, AVAILABLE_MODELS, MODEL_DISCOVERY_NOTE = resolve_model_id(client)
os.environ["BEDROCK_MODEL"] = MODEL_ID
PROMPT_CACHE_RETENTION = prompt_cache_retention_for_model(MODEL_ID)
PROMPT_CACHE_RETENTION_NOTE = (
    "GPT-5.5 and later use 24h extended prompt caching; earlier GPT-5 models can use in_memory."
)

config_rows = [{
    "selected_model": MODEL_ID,
    "model_was_explicit": bool(EXPLICIT_MODEL),
    "model_catalog_status": "listed" if AVAILABLE_MODELS else "using configured model",
    "discovered_model_count": len(AVAILABLE_MODELS),
    "prompt_cache_retention": PROMPT_CACHE_RETENTION,
    "prompt_cache_retention_note": PROMPT_CACHE_RETENTION_NOTE,
    "note": MODEL_DISCOVERY_NOTE or "Model selection is ready.",
}]
display_wrapped_table(pd.DataFrame(config_rows), max_col_width_px=620)

if AVAILABLE_MODELS:
    display_wrapped_table(pd.DataFrame({"available_models": AVAILABLE_MODELS[:25]}), max_col_width_px=520)
else:
    print("Continuing with:", MODEL_ID)
```

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>selected_model</th>
      <th>model_was_explicit</th>
      <th>model_catalog_status</th>
      <th>discovered_model_count</th>
      <th>prompt_cache_retention</th>
      <th>prompt_cache_retention_note</th>
      <th>note</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>openai.gpt-5.4</td>
      <td>False</td>
      <td>using configured model</td>
      <td>0</td>
      <td>in_memory</td>
      <td>GPT-5.5 and later use 24h extended prompt caching; earlier GPT-5 models can use in_memory.</td>
      <td>This endpoint did not expose model-list metadata. The guide will continue with the configured model.</td>
    </tr>
  </tbody>
</table>

```text
Continuing with: openai.gpt-5.4
```

### 1.5 Helper Functions Setup

Define shared helpers for the workflow. These helpers render request shapes, normalize API errors, send raw HTTPS requests, wrap SDK calls with optional retries, extract `output_text`, summarize token usage, track stored response IDs, and display compact tables. The examples below stay focused on each API concept while the helpers handle repeated mechanics. Inspect this cell if you want to understand how response text, usage, errors, and cleanup are processed.


```python
from __future__ import annotations

RESULTS_SUMMARY: list[dict[str, Any]] = []
EXAMPLE_RESPONSES: list[dict[str, str]] = []
STORED_RESPONSE_IDS: list[str] = []
OUTPUT_WIDTH = 100
MAX_DISPLAY_TEXT_CHARS = builtins.int(env_value("BEDROCK_MAX_DISPLAY_CHARS") or "1200")


def truncate_display_text(text: Any, *, limit: int = MAX_DISPLAY_TEXT_CHARS) -> str:
    rendered = builtins.str(text).strip()
    if len(rendered) <= limit:
        return rendered
    return rendered[:limit].rstrip() + "\n[Display truncated for readability. Inspect the Python variable for the full value.]"


def compact_text(text: Any, limit: int = 220) -> str:
    rendered = " ".join(builtins.str(text).split())
    if len(rendered) <= limit:
        return rendered
    return rendered[:limit].rstrip() + "..."


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValueError(message)


def warn_or_raise(condition: bool, message: str) -> bool:
    if condition:
        return True
    display(HTML(f"<div style=\"border-left:4px solid #d29922; padding:6px 10px;\"><strong>Warning:</strong> {html.escape(message)}</div>"))
    if FAIL_ON_CHECK_FAILURE:
        raise AssertionError(message)
    return False


def display_text_block(label: str, text: Any, *, limit: int = MAX_DISPLAY_TEXT_CHARS) -> None:
    safe_label = html.escape(label)
    safe_text = html.escape(truncate_display_text(text, limit=limit))
    display(HTML(f"""
    <div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">{safe_label}</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{safe_text}</div>
    </div>
    """))


def print_wrapped(text: Any, *, width: int = OUTPUT_WIDTH) -> None:
    print(textwrap.fill(builtins.str(text), width=width, break_long_words=True, break_on_hyphens=False))


def print_json(value: Any, *, width: int = OUTPUT_WIDTH) -> None:
    display_json_block("JSON", value)


def print_label(label: str) -> None:
    display(HTML(f"<div style=\"font-weight:600; margin:8px 0 4px;\">{html.escape(label)}</div>"))


def print_labeled_text(label: str, text: Any) -> None:
    display_text_block(label, text)


def print_labeled_json(label: str, value: Any) -> None:
    display_json_block(label, value)


def display_json_block(label: str, value: Any, *, limit: int = MAX_DISPLAY_TEXT_CHARS) -> None:
    rendered = json.dumps(value, indent=2, default=builtins.str)
    display_text_block(label, rendered, limit=limit)


def summarize_content(content: Any) -> str:
    if isinstance(content, builtins.str):
        return compact_text(content)
    if isinstance(content, builtins.list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, builtins.dict):
                parts.append(compact_text(item, 80))
                continue
            item_type = item.get("type", "item")
            if item_type == "input_text":
                parts.append(f"input_text: {compact_text(item.get('text', ''), 120)}")
            elif item_type == "input_file":
                parts.append(f"input_file: {item.get('filename', '<inline file>')}")
            else:
                parts.append(item_type)
        return "; ".join(parts)
    return compact_text(content)


def summarize_input(input_value: Any) -> str:
    if isinstance(input_value, builtins.str):
        return compact_text(input_value, 260)
    if isinstance(input_value, builtins.list):
        messages: list[str] = []
        for item in input_value[:4]:
            if isinstance(item, builtins.dict):
                role = item.get("role", item.get("type", "item"))
                messages.append(f"{role}: {summarize_content(item.get('content', item))}")
            else:
                messages.append(compact_text(item, 120))
        suffix = f"; +{len(input_value) - 4} more" if len(input_value) > 4 else ""
        return f"{len(input_value)} item(s): " + "; ".join(messages) + suffix
    return compact_text(input_value, 260)


def summarize_text_format(text_config: Any) -> str:
    if not isinstance(text_config, builtins.dict):
        return compact_text(text_config)
    fmt = text_config.get("format")
    if isinstance(fmt, builtins.dict):
        fmt_type = fmt.get("type")
        if fmt_type == "json_schema":
            schema = fmt.get("schema") or {}
            required = schema.get("required") or []
            return f"json_schema: {fmt.get('name')} strict={fmt.get('strict')} required={len(required)} fields"
        if fmt_type:
            return builtins.str(fmt_type)
    return compact_text(text_config)


def request_summary_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    ordered_keys = [
        "model", "max_output_tokens", "store", "background", "service_tier", "previous_response_id",
        "parallel_tool_calls", "prompt_cache_key", "prompt_cache_retention",
    ]
    for key in ordered_keys:
        if key in payload:
            rows.append({"field": key, "value": compact_text(payload[key], 180)})
    if "reasoning" in payload:
        rows.append({"field": "reasoning", "value": compact_text(payload["reasoning"], 180)})
    if "text" in payload:
        rows.append({"field": "text format", "value": summarize_text_format(payload["text"])})
    if "include" in payload:
        rows.append({"field": "include", "value": compact_text(payload["include"], 180)})
    if "tools" in payload:
        tool_names = [tool.get("name", tool.get("type", "tool")) for tool in payload.get("tools", [])]
        rows.append({"field": "tools", "value": ", ".join(tool_names)})
    if "tool_choice" in payload:
        rows.append({"field": "tool_choice", "value": compact_text(payload["tool_choice"], 180)})
    if "input" in payload:
        rows.append({"field": "input", "value": summarize_input(payload["input"])})
    return rows


def print_request_shape(payload: dict[str, Any]) -> None:
    rows = request_summary_rows(redact_payload(payload))
    print_label("Request shape")
    display_wrapped_table(pd.DataFrame(rows), max_col_width_px=520)


def print_response_summary(response_or_summary: Any) -> None:
    summary = response_or_summary if isinstance(response_or_summary, builtins.dict) and "output" not in response_or_summary else summarize_response(response_or_summary)
    preferred = [
        "id", "model", "status", "output_item_types", "input_tokens", "cached_input_tokens",
        "output_tokens", "total_tokens", "reasoning_output_tokens", "service_tier",
    ]
    rows = [{"field": key, "value": compact_text(summary.get(key), 220)} for key in preferred if key in summary]
    print_label("Response summary")
    display_wrapped_table(pd.DataFrame(rows), max_col_width_px=420)


def print_key_takeaway(text: str) -> None:
    display(HTML(f"<div style=\"border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;\"><strong>Key takeaway:</strong> {html.escape(text)}</div>"))


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def redact(value: Any) -> Any:
        if isinstance(value, builtins.dict):
            return {
                key: ("<inline file data redacted for display>" if key == "file_data" else redact(item))
                for key, item in value.items()
            }
        if isinstance(value, builtins.list):
            return [redact(item) for item in value]
        return value

    return json.loads(json.dumps(redact(payload), default=builtins.str))


def compact_detail(detail: Any) -> str:
    if isinstance(detail, (builtins.dict, builtins.list)):
        return compact_text(json.dumps(detail, default=builtins.str), 500)
    return compact_text(detail, 500)


def record_check(name: str, status: str, detail: Any = "") -> None:
    RESULTS_SUMMARY.append({"name": name, "status": status, "detail": compact_detail(detail)})


def record_response(example: str, response_type: str, content: Any, limit: int = 900) -> None:
    if isinstance(content, pd.DataFrame):
        rendered = content.to_json(orient="records", indent=2)
    elif isinstance(content, (builtins.dict, builtins.list)):
        rendered = json.dumps(content, indent=2, default=builtins.str)
    else:
        rendered = builtins.str(content)
    rendered = rendered.strip()
    if len(rendered) > limit:
        rendered = rendered[:limit].rstrip() + chr(10) + "..."
    EXAMPLE_RESPONSES.append({
        "example": example,
        "response_type": response_type,
        "response": rendered,
    })


def print_response_gallery() -> pd.DataFrame:
    gallery = pd.DataFrame(EXAMPLE_RESPONSES)
    if gallery.empty:
        gallery = pd.DataFrame(columns=["example", "response_type", "response"])
    display_wrapped_table(gallery, max_col_width_px=620)
    return gallery


def normalize_error(response: requests.Response, body: Any) -> dict[str, Any]:
    return {
        "exception_class": "HTTPError",
        "status_code": response.status_code,
        "retryable": response.status_code in TRANSIENT_STATUS_CODES,
        "request_id": response.headers.get("x-request-id"),
        "body": body,
    }


def describe_api_error(exc: Exception) -> dict[str, Any]:
    try:
        parsed = json.loads(builtins.str(exc))
        if isinstance(parsed, builtins.dict) and "status_code" in parsed:
            return {
                "exception_class": type(exc).__name__,
                "status_code": parsed.get("status_code"),
                "retryable": parsed.get("retryable"),
                "request_id": parsed.get("request_id"),
                "message": compact_text(parsed.get("body", parsed), 500),
            }
    except Exception:
        pass

    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    request_id = None
    if response is not None:
        headers = getattr(response, "headers", {})
        request_id = headers.get("x-request-id") if hasattr(headers, "get") else None
    return {
        "exception_class": type(exc).__name__,
        "status_code": status_code,
        "retryable": status_code in TRANSIENT_STATUS_CODES,
        "request_id": request_id,
        "message": builtins.str(exc)[:500],
    }


def request_json(method: str, path: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = http.request(
        method,
        endpoint(path),
        json=payload,
        timeout=API_TIMEOUT_SECONDS,
    )
    try:
        body = response.json() if response.text else {}
    except json.JSONDecodeError:
        body = {"raw_text": response.text}
    if response.status_code >= 400:
        raise RuntimeError(json.dumps(normalize_error(response, body), indent=2, default=builtins.str))
    return body


def to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, builtins.list):
        return [to_dict(item) for item in value]
    if isinstance(value, builtins.dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value


def output_text(response: Any) -> str:
    direct = getattr(response, "output_text", None)
    if direct:
        return direct
    data = to_dict(response)
    pieces: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text":
                pieces.append(content.get("text", ""))
    return "".join(pieces)


def response_items(response: Any) -> list[dict[str, Any]]:
    data = to_dict(response)
    return builtins.list(data.get("output", []) or [])


def first_output_item(response: Any, item_type: str) -> dict[str, Any] | None:
    for item in response_items(response):
        if item.get("type") == item_type:
            return item
    return None


def summarize_response(response: Any) -> dict[str, Any]:
    data = to_dict(response)
    usage = data.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "id": data.get("id"),
        "model": data.get("model"),
        "status": data.get("status"),
        "output_item_types": [item.get("type") for item in data.get("output", []) or []],
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cached_input_tokens": input_details.get("cached_tokens"),
        "reasoning_output_tokens": output_details.get("reasoning_tokens"),
        "service_tier": data.get("service_tier"),
    }


def call_with_retries(label: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("timeout", API_TIMEOUT_SECONDS)
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            error = describe_api_error(exc)
            should_retry = bool(error["retryable"] and attempt <= MAX_RETRIES)
            if not should_retry:
                raise
            time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"{label} failed after retries") from last_exc


def create_response(**kwargs: Any) -> Any:
    kwargs.setdefault("model", MODEL_ID)
    return call_with_retries("responses.create", client.responses.create, **kwargs)


def retrieve_response(response_id: str) -> Any:
    return call_with_retries("responses.retrieve", client.responses.retrieve, response_id)


def delete_response(response_id: str) -> Any:
    return call_with_retries("responses.delete", client.responses.delete, response_id)


def remember_stored_response(response: Any) -> None:
    response_id = getattr(response, "id", None) or to_dict(response).get("id")
    if response_id:
        STORED_RESPONSE_IDS.append(response_id)


def handle_example_error(features: str | list[str], exc: Exception) -> None:
    feature_list = [features] if isinstance(features, builtins.str) else features
    error = describe_api_error(exc)
    for feature in feature_list:
        record_check(feature, "warn", error)
    print_labeled_text("Result", "This live call did not complete in this environment.")
    print_labeled_json("Response summary", error)


def build_curl_command(payload: dict[str, Any]) -> str:
    body = json.dumps(payload)
    return " ".join([
        "curl", "-sS", shlex.quote(RESPONSES_URL),
        "-H", shlex.quote("Content-Type: application/json"),
        "-H", shlex.quote("Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK"),
        "-d", shlex.quote(body),
    ])


def run_raw_http_request(payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", "/responses", payload=payload)

print("Helpers ready.")
```

```text
Helpers ready.
```

### 1.6 Verify the Endpoint

The first live call is intentionally tiny. It sends a minimal Responses request with `store=false` and a short text instruction so you can catch setup issues before running richer examples. Inspect the request shape, returned text, status, model, output item types, and token usage.




```python
from __future__ import annotations
preflight_payload = {
    "model": MODEL_ID,
    "input": "Reply with exactly: ok",
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(preflight_payload)
try:
    preflight_response = create_response(**preflight_payload)
    require(output_text(preflight_response).strip(), "Preflight response did not return output text.")
    record_check("Endpoint shape", "pass", RESPONSES_URL)
    model_selection_detail = f"{len(AVAILABLE_MODELS)} models discovered" if AVAILABLE_MODELS else "Using configured model; model-list metadata is not required for requests."
    record_check("Model selection", "pass", model_selection_detail)
    preflight_text = output_text(preflight_response).strip()
    record_response("Endpoint verification", "text", preflight_text)
    print_labeled_text("Result", preflight_text)
    print_response_summary(preflight_response)
    print_key_takeaway('A tiny response confirms that the endpoint, key, model, and request shape are working.')
except Exception as exc:
    handle_example_error(["Endpoint shape", "Model selection"], exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Reply with exactly: ok</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">ok</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_gnt2qiavimim2lvfrtosh472mmsodtphk4glbiiefj7joxb4k4ra</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>162</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>5</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>167</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> A tiny response confirms that the endpoint, key, model, and request shape are working.</div>

### 1.7 Normalize API Errors

Production integrations need consistent error logging for status codes, retry decisions, request IDs, and response bodies. This cell documents the normalized error shape used by the notebook without intentionally making a failing request. Later cells use the same shape when a live call fails or returns a non-2xx status.


```python
from __future__ import annotations
error_taxonomy_example = {
    "normalized_fields": ["exception_class", "status_code", "retryable", "request_id", "message"],
    "retryable_status_codes": sorted(TRANSIENT_STATUS_CODES),
    "notes": "call_with_retries(...) uses this taxonomy for transient retry handling.",
}
record_check("Error handling", "pass", error_taxonomy_example)
print_json(error_taxonomy_example)
```

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">JSON</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "normalized_fields": [
    "exception_class",
    "status_code",
    "retryable",
    "request_id",
    "message"
  ],
  "retryable_status_codes": [
    408,
    409,
    429,
    500,
    502,
    503,
    504
  ],
  "notes": "call_with_retries(...) uses this taxonomy for transient retry handling."
}</div>
    </div>

## 2. Make Your First Responses Requests

This section shows the Responses request surface from two angles. First, you inspect and run a raw HTTPS request so the endpoint, headers, and JSON body are visible. Then you use the OpenAI SDK for the same kind of application workflow, which is the path most production code should prefer once configuration is correct.


### 2.1 Inspect the Raw HTTPS Request Shape

Build a minimal Responses payload for a BrightCart support-assistant reply and render a copy-pasteable `curl` command. The command references `$AWS_BEARER_TOKEN_BEDROCK` instead of embedding a token, and the notebook does not execute shell commands that put bearer tokens in process arguments. Inspect the `model`, `input`, `max_output_tokens`, and `store` fields.


```python
from __future__ import annotations
basic_curl_payload = {
    "model": MODEL_ID,
    "input": "BrightCart customer Maya asks why replacement order ORDER-8831 is delayed. Write two labeled plain-text lines for the support agent. Do not use leading hyphens or bold text.",
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(basic_curl_payload)
print_labeled_text("Result", build_curl_command(basic_curl_payload))
print_key_takeaway('The curl command shows the raw HTTPS shape behind the SDK call.')
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>input</td>
      <td>BrightCart customer Maya asks why replacement order ORDER-8831 is delayed. Write two labeled plain-text lines for the support agent. Do not use leading hyphens or bold text.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">curl -sS https://bedrock-mantle.us-west-2.api.aws/openai/v1/responses -H 'Content-Type: application/json' -H 'Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK' -d '{"model": "openai.gpt-5.4", "input": "BrightCart customer Maya asks why replacement order ORDER-8831 is delayed. Write two labeled plain-text lines for the support agent. Do not use leading hyphens or bold text.", "max_output_tokens": 1024, "store": false}'</div>
    </div>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> The curl command shows the raw HTTPS shape behind the SDK call.</div>

### 2.2 Send the Raw HTTPS Request

Send the same request through the raw HTTPS helper. This cell demonstrates the wire-level `POST /responses` path and extracts text from the response body by walking output items. Inspect the returned response ID, model, status, and text output to understand the schema your application receives.


```python
from __future__ import annotations

print_request_shape(basic_curl_payload)
try:
    basic_http_response = run_raw_http_request(basic_curl_payload)
    record_check("Text generation", "pass", basic_http_response.get("id"))
    response_text_parts = []
    for item in basic_http_response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                response_text_parts.append(content.get("text", ""))
    raw_http_output = "".join(response_text_parts).strip()
    record_response("First raw HTTPS request", "text", raw_http_output)
    print_labeled_text("Result", raw_http_output)
    print_labeled_json("Response summary", {
        "id": basic_http_response.get("id"),
        "model": basic_http_response.get("model"),
        "status": basic_http_response.get("status"),
    })
    print_key_takeaway("The response body contains message output that application code can extract as text.")
except Exception as exc:
    handle_example_error("Text generation", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>input</td>
      <td>BrightCart customer Maya asks why replacement order ORDER-8831 is delayed. Write two labeled plain-text lines for the support agent. Do not use leading hyphens or bold text.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Empathy: I’m sorry, Maya — your replacement order ORDER-8831 is delayed because the carrier reported a temporary transit hold at the regional sorting facility.
Action: We’re monitoring the shipment closely and will send you an updated delivery estimate within 24 hours; if there’s no movement by then, we’ll review the next replacement or refund options with you.</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Response summary</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "id": "resp_naythl6fvzhoctlsdogd4vpr673q5ibagqqpiujbast3sy6viroa",
  "model": "openai.gpt-5.4",
  "status": "completed"
}</div>
    </div>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> The response body contains message output that application code can extract as text.</div>

### 2.3 Use the OpenAI SDK

The OpenAI SDK can call OpenAI-compatible APIs when you pass the Bedrock bearer token and base URL explicitly. This cell sends a text-generation request through `client.responses.create`, sets `reasoning.effort` to `low`, and prints a compact response summary. Inspect the output text, token counts, output item types, and any reasoning-token metadata returned by the endpoint.

Official docs: [Reasoning models](https://developers.openai.com/api/docs/guides/reasoning) describes using reasoning effort with the Responses API.


```python
from __future__ import annotations
sdk_text_payload = {
    "model": MODEL_ID,
    "input": "Write a three-sentence overview for a developer building a BrightCart support assistant with the Responses API.",
    "reasoning": {"effort": "low"},
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(sdk_text_payload)
try:
    text_response = create_response(**sdk_text_payload)
    sdk_text = output_text(text_response).strip()
    require(sdk_text, "SDK text response did not return output text.")
    record_check("Text generation", "pass", summarize_response(text_response))
    record_check("Reasoning effort", "pass", summarize_response(text_response))
    record_response("SDK text generation", "text", sdk_text)
    print_labeled_text("Result", sdk_text)
    print_response_summary(text_response)
    print_key_takeaway('The SDK returns a response object with text, status, token usage, and output item metadata.')
except Exception as exc:
    handle_example_error(["Text generation", "Reasoning effort"], exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>reasoning</td>
      <td>{'effort': 'low'}</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Write a three-sentence overview for a developer building a BrightCart support assistant with the Responses API.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Use the Responses API to build a BrightCart support assistant that can answer customer questions, summarize policies, and guide users through common workflows like order tracking, refunds, and account updates. Ground the assistant in BrightCart documentation and connect it to relevant backend tools or APIs so it can retrieve live order data, check account status, and provide accurate, context-aware support responses. Design the experience around clear system instructions, structured tool calling, and conversation state management so the assistant stays on-brand, reliable, and safe when handling customer issues.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_nmvqefzghd5hi67uwy4wfvhwnnzild3lslqsxqor3cat63kmucoq</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['reasoning', 'message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>177</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>129</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>306</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>18</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> The SDK returns a response object with text, status, token usage, and output item metadata.</div>

### 2.4 Create and Retrieve a Response

The Responses API can store a response and retrieve it later by ID. This pattern is useful for audit trails, debugging, and follow-up turns that reference prior context. This cell creates a stored response, tracks the ID for cleanup, retrieves it, and compares the retrieved text and usage metadata.




```python
from __future__ import annotations
lifecycle_payload = {
    "model": MODEL_ID,
    "input": (
        "BrightCart is building a support assistant for delayed replacement orders. "
        "Return exactly three labeled plain-text lines: goal, data needed, and human-review rule. Do not use leading hyphens or bold text."
    ),
    "max_output_tokens": 1024,
    "store": True,
}

print_request_shape(lifecycle_payload)
try:
    lifecycle_response = create_response(**lifecycle_payload)
    remember_stored_response(lifecycle_response)
    retrieved_response = retrieve_response(lifecycle_response.id)
    retrieved_summary = summarize_response(retrieved_response)
    retrieved_text = output_text(retrieved_response).strip()
    require(retrieved_text, "Retrieved response did not contain text output.")

    lifecycle_status = "pass" if retrieved_summary.get("status") in {None, "completed"} else "warn"
    record_check("Responses lifecycle", lifecycle_status, retrieved_response.id)
    record_check("Response schema", "pass", retrieved_summary)
    record_check("Usage metadata", "pass" if retrieved_summary.get("total_tokens") is not None else "warn", retrieved_summary)
    record_response("Create and retrieve response", "text", retrieved_text)

    print_labeled_text("Result", retrieved_text)
    print_labeled_json("Created response summary", summarize_response(lifecycle_response))
    print_response_summary(retrieved_summary)
    print_key_takeaway('store=True lets an application retrieve the response later by ID with usage metadata intact.')
except Exception as exc:
    handle_example_error(["Responses lifecycle", "Response schema", "Usage metadata"], exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>True</td>
    </tr>
    <tr>
      <td>input</td>
      <td>BrightCart is building a support assistant for delayed replacement orders. Return exactly three labeled plain-text lines: goal, data needed, and human-review rule. Do not use leading hyphens or bold text.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">goal: Help support agents explain delayed replacement orders, set expectations, and suggest next steps.
data needed: Order ID, replacement order status, shipment/tracking events, delay reason, estimated ship/delivery date, customer contact history, inventory/backorder status, and applicable refund or reship policy.
human-review rule: Escalate to a human if the delay exceeds policy thresholds, tracking is inconsistent or missing, the order appears lost, the customer is high-risk or highly upset, or any refund/reship exception is requested.</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Created response summary</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "id": "resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia",
  "model": "openai.gpt-5.4",
  "status": "completed",
  "output_item_types": [
    "message"
  ],
  "input_tokens": 198,
  "output_tokens": 109,
  "total_tokens": 307,
  "cached_input_tokens": 0,
  "reasoning_output_tokens": 0,
  "service_tier": "default"
}</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>198</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>109</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>307</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> store=True lets an application retrieve the response later by ID with usage metadata intact.</div>

### 2.5 Add Reasoning Effort, Service Tier, and Prompt Cache Parameters

Model controls travel alongside the normal input. This request combines `reasoning.effort`, `service_tier`, `prompt_cache_key`, and `prompt_cache_retention` so you can see how operational controls and prompt-cache metadata appear in the same response schema as ordinary text output. Inspect `service_tier`, `cached_input_tokens`, reasoning token metadata, and total token usage.

Note: This notebook uses `PROMPT_CACHE_RETENTION` instead of hard-coding `prompt_cache_retention`. The value is `in_memory` for `openai.gpt-5.4`, and `24h` for `openai.gpt-5.5` and later models because those models require extended prompt caching.


```python
from __future__ import annotations
control_payload = {
    "model": MODEL_ID,
    "input": (
        "For the BrightCart support assistant, explain prompt caching in exactly two labeled plain-text lines: "
        "one latency benefit and one consistency benefit."
    ),
    "reasoning": {"effort": "low"},
    "prompt_cache_key": "brightcart-support-policy-guide",
    "prompt_cache_retention": PROMPT_CACHE_RETENTION,
    "service_tier": "auto",
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(control_payload)
try:
    control_response = create_response(**control_payload)
    control_summary = summarize_response(control_response)
    control_text = output_text(control_response).strip()
    require(control_text, "Control response did not return text.")
    status = "pass" if control_summary.get("status") in {None, "completed"} else "warn"
    record_check("Prompt caching", "pass" if control_summary.get("cached_input_tokens") is not None else "warn", control_summary)
    record_check("Service tier", "pass" if control_summary.get("service_tier") is not None else "warn", control_summary)
    record_check("Reasoning effort", status, control_summary)
    record_response("Service tier and prompt cache request", "text", control_text)
    print_labeled_text("Result", control_text)
    print_response_summary(control_summary)
    print_key_takeaway('Model controls travel with the same request as normal input, while returned metadata can vary by endpoint.')
except Exception as exc:
    handle_example_error(["Prompt caching", "Service tier", "Reasoning effort"], exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>auto</td>
    </tr>
    <tr>
      <td>prompt_cache_key</td>
      <td>brightcart-support-policy-guide</td>
    </tr>
    <tr>
      <td>prompt_cache_retention</td>
      <td>in_memory</td>
    </tr>
    <tr>
      <td>reasoning</td>
      <td>{'effort': 'low'}</td>
    </tr>
    <tr>
      <td>input</td>
      <td>For the BrightCart support assistant, explain prompt caching in exactly two labeled plain-text lines: one latency benefit and one consistency benefit.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Latency benefit: Prompt caching lets the BrightCart support assistant reuse previously processed context, reducing response time for repeated or similar requests.
Consistency benefit: Prompt caching helps the BrightCart support assistant return more uniform answers by reusing the same established prompt context across interactions.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_q4akwbeynfwfwnt5i4tdwkpcgsffdu4lqvng7lnwaob53opswvwq</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['reasoning', 'message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>183</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>91</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>274</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>34</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Model controls travel with the same request as normal input, while returned metadata can vary by endpoint.</div>

## 3. Generate Structured JSON

Structured JSON turns model output into data that application code can parse, validate, and route. This section compares strict schema-constrained output with lighter JSON mode. Use Structured Outputs when your application needs a contract; use JSON mode when valid JSON is enough but the exact schema can remain flexible.




### 3.1 Define the Structured Output Schema

Define the support-ticket schema used by the next live request. The schema lists the exact fields the application expects, including category, priority, sentiment, summary, required actions, and escalation status. Inspect the request shape to see how `text.format.type="json_schema"`, `strict=true`, and the JSON Schema are attached to a normal Responses request.


```python
from __future__ import annotations
support_triage_schema = {
    "type": "object",
    "properties": {
        "ticket_id": {"type": "string"},
        "category": {"type": "string", "enum": ["delivery_delay", "return_exchange", "damaged_item", "billing", "account"]},
        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
        "customer_sentiment": {"type": "string"},
        "summary": {"type": "string"},
        "required_actions": {"type": "array", "items": {"type": "string"}, "minItems": 2},
        "escalation_needed": {"type": "boolean"},
    },
    "required": ["ticket_id", "category", "priority", "customer_sentiment", "summary", "required_actions", "escalation_needed"],
    "additionalProperties": False,
}

structured_payload = {
    "model": MODEL_ID,
    "input": (
        "Support ticket TICKET-7429: Maya Chen says ORDER-8831 is a replacement for a damaged standing desk. "
        "The replacement is two days late, the carrier scan has not moved, and she needs the desk before Monday. "
        "She asks for a supervisor callback and refund options. Triage this ticket for the next support agent."
    ),
    "text": {"format": {"type": "json_schema", "name": "support_ticket_triage", "strict": True, "schema": support_triage_schema}},
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(structured_payload)
print_key_takeaway('The schema is part of the request and defines the fields the next cell validates.')
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>text format</td>
      <td>json_schema: support_ticket_triage strict=True required=7 fields</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Support ticket TICKET-7429: Maya Chen says ORDER-8831 is a replacement for a damaged standing desk. The replacement is two days late, the carrier scan has not moved, and she needs the desk before Monday. She asks for a supervisor callback and refund options. T...</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> The schema is part of the request and defines the fields the next cell validates.</div>

### 3.2 Validate Schema-Constrained Output

Call the model with the schema from the previous cell, parse the returned text as JSON, and validate important fields in Python. The API request asks for schema adherence, while application-side validation still checks that the returned object is suitable for downstream routing. Inspect the parsed object and the response summary.


```python
from __future__ import annotations


def validate_support_triage(payload: dict[str, Any]) -> dict[str, Any]:
    require("ticket_id" in payload, "Missing key: ticket_id")
    require(payload.get("ticket_id") == "TICKET-7429", "Ticket ID did not match expected value.")
    require("required_actions" in payload, "Missing key: required_actions")
    require(isinstance(payload.get("required_actions"), builtins.list), "required_actions must be a list.")
    require(len(payload["required_actions"]) >= 2, "required_actions should contain at least two actions.")
    return payload

print_request_shape(structured_payload)
try:
    structured_response = create_response(**structured_payload)
    raw_structured_text = output_text(structured_response).strip()
    try:
        structured_payload_result = validate_support_triage(json.loads(raw_structured_text))
        record_check("Structured Outputs", "pass", structured_payload_result)
        record_response("Structured ticket triage", "json", structured_payload_result)
        print_labeled_json("Result", structured_payload_result)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    except Exception as parse_exc:
        record_check("Structured Outputs", "warn", {"message": "Response did not match the expected schema shape.", "text_sample": raw_structured_text[:600], "error": builtins.str(parse_exc)})
        print_labeled_text("Result", "The request completed, but the returned text did not match the expected schema shape.")
        print_wrapped(raw_structured_text[:1200])
    print_response_summary(structured_response)
    print_key_takeaway('Schema-constrained output gives application code a predictable JSON object to parse and validate.')
except Exception as exc:
    handle_example_error("Structured Outputs", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>text format</td>
      <td>json_schema: support_ticket_triage strict=True required=7 fields</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Support ticket TICKET-7429: Maya Chen says ORDER-8831 is a replacement for a damaged standing desk. The replacement is two days late, the carrier scan has not moved, and she needs the desk before Monday. She asks for a supervisor callback and refund options. T...</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "ticket_id": "TICKET-7429",
  "category": "delivery_delay",
  "priority": "urgent",
  "customer_sentiment": "frustrated and time-sensitive",
  "summary": "Customer Maya Chen reports that ORDER-8831 is a replacement shipment for a previously damaged standing desk. The replacement is now 2 days late, carrier tracking has not updated, and she needs the desk delivered before Monday. She is requesting a supervisor callback and wants to know refund options if the replacement cannot arrive in time.",
  "required_actions": [
    "Review ORDER-8831 shipment status and confirm last carrier scan/update.",
    "Contact carrier or open a trace/escalation for stalled tracking.",
    "Check expedited reshipment or alternative fulfillment options to meet the before-Monday deadline.",
    "Arrange supervisor callback per customer request.",
    "Review and communicate refund options, including refund for replacement order and any prior damaged-item resolution details.",
    "Verify whether replacement shipment should be intercepted/returned if a refund or reshipment is approved."
  ],
  "escalation_needed": true
}</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_rk7y6aobdqx2m2fjpnllihuoyku2n55gj5o2h5jxl7lru77mwwiq</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>328</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>200</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>528</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Schema-constrained output gives application code a predictable JSON object to parse and validate.</div>

### 3.3 Use JSON Mode

JSON mode asks the model to return a valid JSON object without enforcing a strict schema. This is useful for lightweight handoffs where you still want parsable output but can tolerate a looser contract. This cell requests a support handoff object, parses it, and checks for the expected keys.


```python
from __future__ import annotations
json_mode_payload = {
    "model": MODEL_ID,
    "input": (
        "Return JSON for a support chat handoff with keys customer_name, order_id, issue_summary, next_step, "
        "and metrics_to_watch. Context: Maya Chen asks about delayed replacement order ORDER-8831; the carrier scan is stale. "
        "metrics_to_watch should be an array."
    ),
    "text": {"format": {"type": "json_object"}},
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(json_mode_payload)
try:
    json_mode_response = create_response(**json_mode_payload)
    payload = json.loads(output_text(json_mode_response).strip())
    require({"customer_name", "order_id", "issue_summary", "next_step", "metrics_to_watch"}.issubset(payload), "JSON mode response missed required keys.")
    record_check("JSON mode", "pass", payload)
    record_response("JSON support handoff", "json", payload)
    print_labeled_json("Result", payload)
    print_response_summary(json_mode_response)
    print_key_takeaway('JSON mode is useful when valid JSON is enough and a strict schema is not required.')
except Exception as exc:
    handle_example_error("JSON mode", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>text format</td>
      <td>json_object</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Return JSON for a support chat handoff with keys customer_name, order_id, issue_summary, next_step, and metrics_to_watch. Context: Maya Chen asks about delayed replacement order ORDER-8831; the carrier scan is stale. metrics_to_watch should be an array.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "customer_name": "Maya Chen",
  "order_id": "ORDER-8831",
  "issue_summary": "Customer is asking about a delayed replacement order. The carrier tracking scan is stale and has not updated.",
  "next_step": "Handoff to support to investigate the carrier delay, verify shipment status, and provide Maya Chen with an update or resolution.",
  "metrics_to_watch": [
    "tracking_scan_recency",
    "carrier_exception_status",
    "replacement_order_delivery_eta",
    "customer_follow_up_time"
  ]
}</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_2wloqig6bh6sz2ysyiozx7oon7hogdzavqnv4pn7wcmnfkxnmlra</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>212</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>122</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>334</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> JSON mode is useful when valid JSON is enough and a strict schema is not required.</div>

### 3.4 Control Verbosity from Reasoning Effort

Verbosity controls help tune the shape of generated prose, while reasoning effort controls how much reasoning work the model spends before answering. The notebook demonstrates `reasoning.effort` in the SDK and model-control cells above; this cell focuses on `text.verbosity` by sending compact and detailed versions of the same policy topic. Inspect the side-by-side text and token summaries to compare style and usage.


```python
from __future__ import annotations
verbosity_prompt = "Explain BrightCart's delayed-replacement policy to a new support agent."
compact_payload = {
    "model": MODEL_ID,
    "input": verbosity_prompt + " Reply in one sentence under 35 words.",
    "text": {"verbosity": "low"},
    "max_output_tokens": 1024,
    "store": False,
}
detailed_payload = {
    "model": MODEL_ID,
    "input": verbosity_prompt + " Reply in exactly three numbered plain-text lines, each under 18 words. Do not use leading hyphens or bold text.",
    "text": {"verbosity": "high"},
    "max_output_tokens": 1024,
    "store": False,
}

print_labeled_json("Request shape", {
    "compact": redact_payload(compact_payload),
    "detailed": redact_payload(detailed_payload),
})
try:
    compact_response = create_response(**compact_payload)
    detailed_response = create_response(**detailed_payload)
    compact_guidance_text = output_text(compact_response).strip()
    detailed_guidance_text = output_text(detailed_response).strip()
    require(compact_guidance_text and detailed_guidance_text, "Verbosity responses did not return text.")
    compact_summary = summarize_response(compact_response)
    detailed_summary = summarize_response(detailed_response)
    status = "pass" if compact_summary.get("status") in {None, "completed"} and detailed_summary.get("status") in {None, "completed"} else "warn"
    record_check("Verbosity", status, {"compact_chars": len(compact_guidance_text), "detailed_chars": len(detailed_guidance_text)})
    record_response("Compact policy guidance", "text", compact_guidance_text)
    record_response("Detailed policy guidance", "text", detailed_guidance_text)
    print_labeled_text("Result: compact guidance", compact_guidance_text)
    print_labeled_text("Result: detailed guidance", detailed_guidance_text)
    verbosity_summary = pd.DataFrame([
        {"request": "compact", **compact_summary},
        {"request": "detailed", **detailed_summary},
    ])
    print_label("Response summary")
    display_wrapped_table(verbosity_summary, max_col_width_px=420)
    print_key_takeaway('Verbosity controls tune the answer style while the prompt still bounds the output.')
except Exception as exc:
    handle_example_error("Verbosity", exc)
```

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Request shape</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "compact": {
    "model": "openai.gpt-5.4",
    "input": "Explain BrightCart's delayed-replacement policy to a new support agent. Reply in one sentence under 35 words.",
    "text": {
      "verbosity": "low"
    },
    "max_output_tokens": 1024,
    "store": false
  },
  "detailed": {
    "model": "openai.gpt-5.4",
    "input": "Explain BrightCart's delayed-replacement policy to a new support agent. Reply in exactly three numbered plain-text lines, each under 18 words. Do not use leading hyphens or bold text.",
    "text": {
      "verbosity": "high"
    },
    "max_output_tokens": 1024,
    "store": false
  }
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: compact guidance</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">BrightCart’s delayed-replacement policy lets customers keep using the original item until the replacement arrives, then return the defective product within the allowed return window.</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: detailed guidance</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">1. BrightCart sends replacements after customers return the original item and warehouse receipt is confirmed.
2. This delay prevents duplicate shipments, verifies eligibility, and reduces fraud or inventory errors.
3. Agents should explain timelines clearly, offer return instructions, and reassure customers once receipt is logged.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>request</th>
      <th>id</th>
      <th>model</th>
      <th>status</th>
      <th>output_item_types</th>
      <th>input_tokens</th>
      <th>output_tokens</th>
      <th>total_tokens</th>
      <th>cached_input_tokens</th>
      <th>reasoning_output_tokens</th>
      <th>service_tier</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>compact</td>
      <td>resp_m33l24gl3wl55lwqxhnrqkrf34ikc4rex4sazo2pnqpp4malnliq</td>
      <td>openai.gpt-5.4</td>
      <td>completed</td>
      <td>[message]</td>
      <td>180</td>
      <td>34</td>
      <td>214</td>
      <td>0</td>
      <td>0</td>
      <td>default</td>
    </tr>
    <tr>
      <td>detailed</td>
      <td>resp_icqbez74xlmlvw4kl3yf2qtbutfopfefayzftragcwmhu4cohnua</td>
      <td>openai.gpt-5.4</td>
      <td>completed</td>
      <td>[message]</td>
      <td>197</td>
      <td>60</td>
      <td>257</td>
      <td>0</td>
      <td>0</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Verbosity controls tune the answer style while the prompt still bounds the output.</div>

## 4. Add Application-Managed Tools

Function calling lets the model ask your application for data or actions, but your code remains responsible for executing tools and returning results. This section defines local BrightCart tools, then walks through a single function call, multiple independent calls, and a custom text tool. The examples keep tool outputs deterministic so the request loop is easy to inspect.




### 4.1 Define Local Tool Schemas and Functions

Define local sample tools for order status and customer profile lookups. The tool schemas describe the names, descriptions, argument shapes, required fields, and strictness that the model can use when deciding what to call. The Python functions stand in for application systems such as order management, CRM, or policy services.


```python
from __future__ import annotations
function_tools = [
    {
        "type": "function",
        "name": "get_order_status",
        "description": "Look up a sample BrightCart order status.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "An order ID such as ORDER-8831."}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_customer_profile",
        "description": "Look up sample customer context for a BrightCart support interaction.",
        "parameters": {
            "type": "object",
            "properties": {"customer_id": {"type": "string", "description": "A customer ID such as CUST-1042."}},
            "required": ["customer_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def get_order_status(order_id: str) -> dict[str, Any]:
    orders = {
        "ORDER-8831": {
            "order_id": "ORDER-8831",
            "customer_id": "CUST-1042",
            "item": "standing desk replacement",
            "status": "delayed",
            "carrier_scan": "No movement for 36 hours at Denver sort center",
            "promised_delivery": (date.today() + timedelta(days=2)).isoformat(),
            "recommended_policy": "If delay exceeds 48 hours, offer expedited replacement or 15% concession with agent approval.",
        },
        "ORDER-2044": {
            "order_id": "ORDER-2044",
            "customer_id": "CUST-1042",
            "item": "ergonomic chair",
            "status": "delivered",
            "carrier_scan": "Delivered yesterday at front desk",
            "promised_delivery": (date.today() - timedelta(days=1)).isoformat(),
            "recommended_policy": "Confirm delivery details before opening a replacement request.",
        },
    }
    return orders.get(order_id, {"order_id": order_id, "status": "unknown", "customer_id": None})


def get_customer_profile(customer_id: str) -> dict[str, Any]:
    profiles = {
        "CUST-1042": {
            "customer_id": "CUST-1042",
            "name": "Maya Chen",
            "loyalty_tier": "Gold",
            "region": "California",
            "recent_issue": "Damaged standing desk replacement",
            "contact_preference": "email with SMS updates for shipping changes",
        }
    }
    return profiles.get(customer_id, {"customer_id": customer_id, "loyalty_tier": "unknown"})


def dispatch_tool_call(call: dict[str, Any]) -> dict[str, Any]:
    name = call["name"]
    args = json.loads(call["arguments"])
    if name == "get_order_status":
        output = get_order_status(**args)
    elif name == "get_customer_profile":
        output = get_customer_profile(**args)
    else:
        raise ValueError(f"Unsupported tool: {name}")
    return {"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(output)}

print("Sample function tools:")
print_json([tool["name"] for tool in function_tools])
print("\nSample order lookup:")
print_json(get_order_status("ORDER-8831"))
```

```text
Sample function tools:
```

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">JSON</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">[
  "get_order_status",
  "get_customer_profile"
]</div>
    </div>

```text

Sample order lookup:
```

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">JSON</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "order_id": "ORDER-8831",
  "customer_id": "CUST-1042",
  "item": "standing desk replacement",
  "status": "delayed",
  "carrier_scan": "No movement for 36 hours at Denver sort center",
  "promised_delivery": "2026-06-01",
  "recommended_policy": "If delay exceeds 48 hours, offer expedited replacement or 15% concession with agent approval."
}</div>
    </div>

### 4.2 Call a Function Tool

This cell runs the basic function-calling loop. The first request gives the model an order-status tool and asks it to choose arguments. The application parses the returned `function_call`, runs the local Python function, sends a `function_call_output` item back, and asks for the final grounded answer. Inspect the tool arguments, local tool output, final model text, and response metadata.


```python
from __future__ import annotations
function_input = [{"role": "user", "content": "Use get_order_status for ORDER-8831, then explain the next best action for the support agent in two labeled plain-text lines. Do not use leading hyphens or bold text."}]
order_status_tool = [tool for tool in function_tools if tool["name"] == "get_order_status"]
function_request = {
    "model": MODEL_ID,
    "input": function_input,
    "tools": order_status_tool,
    "tool_choice": "required",
    "max_output_tokens": 1024,
    "store": False,
}


def create_tool_plan_with_auto_fallback(request: dict[str, Any]) -> tuple[Any, str]:
    try:
        return create_response(**request), builtins.str(request.get("tool_choice"))
    except Exception as first_exc:
        fallback_request = {**request, "tool_choice": "auto"}
        try:
            return create_response(**fallback_request), "auto"
        except Exception:
            raise first_exc


print_request_shape(function_request)
try:
    function_plan, tool_choice_used = create_tool_plan_with_auto_fallback(function_request)
    function_calls = [item for item in response_items(function_plan) if item.get("type") == "function_call"]

    if function_calls:
        function_call = function_calls[0]
        function_args = json.loads(function_call["arguments"])
        require(function_args.get("order_id") == "ORDER-8831", f"Unexpected function arguments: {function_args}")
        tool_output = dispatch_tool_call(function_call)
        final_response = create_response(
            model=MODEL_ID,
            input=function_input + response_items(function_plan) + [tool_output],
            tools=order_status_tool,
            max_output_tokens=1024,
            store=False,
        )
        final_answer = output_text(final_response).strip()
        tool_output_payload = json.loads(tool_output["output"])
        record_check("Function calling", "pass", {"tool_choice_used": tool_choice_used, "arguments": function_args})
        record_response("Order-status tool answer", "text", final_answer)
        print_labeled_json("Result: tool arguments", function_args)
        print_labeled_json("Result: tool output", tool_output_payload)
        print_labeled_text("Result: final model answer", final_answer)
        print_response_summary(final_response)
        print_key_takeaway('Function calling separates model-selected arguments from application-executed business logic.')
    else:
        fallback_order = get_order_status("ORDER-8831")
        fallback_prompt = (
            "The model response did not include a function_call item. Use this application lookup result "
            "to answer in two labeled plain-text lines without leading hyphens or bold text: " + json.dumps(fallback_order)
        )
        final_response = create_response(
            model=MODEL_ID,
            input=function_input + [{"role": "user", "content": fallback_prompt}],
            max_output_tokens=1024,
            store=False,
        )
        final_answer = output_text(final_response).strip()
        returned_item_types = [item.get("type") for item in response_items(function_plan)]
        record_check("Function calling", "warn", {"tool_choice_used": tool_choice_used, "returned_item_types": returned_item_types})
        record_response("Order-status local fallback answer", "text", final_answer)
        print_labeled_json("Result: returned output item types", returned_item_types)
        print_labeled_json("Result: local tool output", fallback_order)
        print_labeled_text("Result: final model answer", final_answer)
        print_response_summary(final_response)
        print_key_takeaway('The local lookup keeps the function-calling pattern understandable even when the model returns text.')
except Exception as exc:
    handle_example_error("Function calling", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>tools</td>
      <td>get_order_status</td>
    </tr>
    <tr>
      <td>tool_choice</td>
      <td>required</td>
    </tr>
    <tr>
      <td>input</td>
      <td>1 item(s): user: Use get_order_status for ORDER-8831, then explain the next best action for the support agent in two labeled plain-text lines. Do not use leading hyphens or bold text.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: tool arguments</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "order_id": "ORDER-8831"
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: tool output</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "order_id": "ORDER-8831",
  "customer_id": "CUST-1042",
  "item": "standing desk replacement",
  "status": "delayed",
  "carrier_scan": "No movement for 36 hours at Denver sort center",
  "promised_delivery": "2026-06-01",
  "recommended_policy": "If delay exceeds 48 hours, offer expedited replacement or 15% concession with agent approval."
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: final model answer</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Status: ORDER-8831 is delayed; carrier shows no movement for 36 hours at the Denver sort center, with promised delivery on 2026-06-01.
Next best action: Monitor until the 48-hour threshold; if no movement then, contact the customer and offer either an expedited replacement or a 15% concession with agent approval.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_nqjijq6jvanvxdglnj4iuezrkdm2eoizutfiezzxbmm42xtynw6a</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>674</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>75</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>749</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Function calling separates model-selected arguments from application-executed business logic.</div>

### 4.3 Handle Multiple Tool Calls

Parallel tool calls let the model request more than one independent lookup from a single turn. This cell allows two order-status lookups, executes each local function call, and sends both outputs back before asking the model to compare the active shipping issues. Inspect the returned order IDs and final answer to confirm that application data, not model memory, grounds the response.


```python
from __future__ import annotations
parallel_input = [{"role": "user", "content": "Use get_order_status for ORDER-8831 and ORDER-2044, then summarize whether Maya has one shipping problem or multiple active shipping problems in two labeled plain-text lines. Do not use leading hyphens or bold text."}]
parallel_request = {
    "model": MODEL_ID,
    "input": parallel_input,
    "tools": function_tools,
    "tool_choice": "auto",
    "parallel_tool_calls": True,
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(parallel_request)
try:
    parallel_plan = create_response(**parallel_request)
    parallel_calls = [item for item in response_items(parallel_plan) if item.get("type") == "function_call"]
    parallel_outputs = [dispatch_tool_call(call) for call in parallel_calls]
    parallel_order_ids = [json.loads(call["arguments"]).get("order_id") for call in parallel_calls if call.get("name") == "get_order_status"]
    expected_order_ids = ["ORDER-8831", "ORDER-2044"]
    missing_order_ids = [order_id for order_id in expected_order_ids if order_id not in builtins.set(parallel_order_ids)]

    if not missing_order_ids:
        parallel_final = create_response(
            model=MODEL_ID,
            input=parallel_input + response_items(parallel_plan) + parallel_outputs,
            tools=function_tools,
            max_output_tokens=1024,
            store=False,
        )
        parallel_answer = output_text(parallel_final).strip()
        record_check("Parallel tool calls", "pass", {"tool_call_count": len(parallel_calls), "order_ids": parallel_order_ids})
        record_response("Parallel order lookup answer", "text", parallel_answer)
        print_labeled_json("Result: tool calls", {"tool_call_count": len(parallel_calls), "order_ids": parallel_order_ids})
        print_labeled_text("Result: final model answer", parallel_answer)
        print_response_summary(parallel_final)
        print_key_takeaway('Parallel tool calls let the model request multiple lookups, while the application still controls execution.')
    else:
        fallback_orders = [get_order_status(order_id) for order_id in expected_order_ids]
        fallback_prompt = (
            "The model did not request every expected order lookup. Use these application lookup results "
            "to answer in two labeled plain-text lines without leading hyphens or bold text: " + json.dumps(fallback_orders)
        )
        parallel_final = create_response(
            model=MODEL_ID,
            input=parallel_input + [{"role": "user", "content": fallback_prompt}],
            max_output_tokens=1024,
            store=False,
        )
        parallel_answer = output_text(parallel_final).strip()
        record_check("Parallel tool calls", "warn", {"returned_order_ids": parallel_order_ids, "missing_order_ids": missing_order_ids})
        record_response("Parallel order lookup fallback answer", "text", parallel_answer)
        print_labeled_json("Result: returned tool calls", {"tool_call_count": len(parallel_calls), "order_ids": parallel_order_ids})
        print_labeled_json("Result: local tool outputs", fallback_orders)
        print_labeled_text("Result: final model answer", parallel_answer)
        print_response_summary(parallel_final)
        print_key_takeaway('Local lookup outputs keep the parallel-tool pattern understandable if not every call is returned.')
except Exception as exc:
    handle_example_error("Parallel tool calls", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>parallel_tool_calls</td>
      <td>True</td>
    </tr>
    <tr>
      <td>tools</td>
      <td>get_order_status, get_customer_profile</td>
    </tr>
    <tr>
      <td>tool_choice</td>
      <td>auto</td>
    </tr>
    <tr>
      <td>input</td>
      <td>1 item(s): user: Use get_order_status for ORDER-8831 and ORDER-2044, then summarize whether Maya has one shipping problem or multiple active shipping problems in two labeled plain-text lines. Do not use leading hyphens or bold text.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: returned tool calls</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "tool_call_count": 1,
  "order_ids": [
    "ORDER-8831"
  ]
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: local tool outputs</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">[
  {
    "order_id": "ORDER-8831",
    "customer_id": "CUST-1042",
    "item": "standing desk replacement",
    "status": "delayed",
    "carrier_scan": "No movement for 36 hours at Denver sort center",
    "promised_delivery": "2026-06-01",
    "recommended_policy": "If delay exceeds 48 hours, offer expedited replacement or 15% concession with agent approval."
  },
  {
    "order_id": "ORDER-2044",
    "customer_id": "CUST-1042",
    "item": "ergonomic chair",
    "status": "delivered",
    "carrier_scan": "Delivered yesterday at front desk",
    "promised_delivery": "2026-05-29",
    "recommended_policy": "Confirm delivery details before opening a replacement request."
  }
]</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: final model answer</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Order statuses: ORDER-8831 is delayed and ORDER-2044 was delivered yesterday.
Shipping problems: Maya has one active shipping problem, because only ORDER-8831 is currently delayed while ORDER-2044 is already delivered.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_ovmlijo2lf2nmc7udlofbbw7n2xmlxs6mxdpftlp6iamfcjoeerq</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>404</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>50</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>454</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Local lookup outputs keep the parallel-tool pattern understandable if not every call is returned.</div>

### 4.4 Use a Custom Text Tool

Custom tools pass freeform text to application-owned logic instead of requiring a structured JSON argument object. This cell defines a support-note normalizer, requests a custom tool call, and includes a local fallback if the endpoint returns ordinary text instead of a custom call. Inspect the output item types and the normalized note.


```python
from __future__ import annotations
custom_tools = [
    {
        "type": "custom",
        "name": "normalize_support_note",
        "description": "Normalize a freeform support note written by an agent. Input is plain text.",
        "format": {"type": "text"},
    }
]


def normalize_support_note_text(note: str) -> str:
    fields = [part.strip().upper() for part in note.split("|")]
    labels = ["ORDER_ID", "CUSTOMER_ID", "ISSUE", "CUSTOMER_REQUEST", "POLICY_OPTION"]
    return "\n".join(
        f"{label}: {value}"
        for label, value in zip(labels, fields)
        if value
    )


support_note = "order-8831 | cust-1042 | replacement delayed | customer wants supervisor | offer expedited replacement or 15% concession"
custom_input = [{
    "role": "user",
    "content": (
        "Call normalize_support_note with this exact note. Do not answer directly; "
        f"send the note to the custom tool: {support_note}"
    ),
}]
custom_request = {
    "model": MODEL_ID,
    "input": custom_input,
    "tools": custom_tools,
    "tool_choice": {"type": "custom", "name": "normalize_support_note"},
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(custom_request)
print_labeled_text("Result: local fallback normalization", normalize_support_note_text(support_note))
try:
    custom_plan = create_response(**custom_request)
    returned_item_types = [item.get("type") for item in response_items(custom_plan)]
    try:
        custom_call = first_output_item(custom_plan, "custom_tool_call")
        if custom_call is None:
            raise LookupError("No custom_tool_call item returned.")
        tool_input = custom_call.get("input", "").strip()
        normalized_note = normalize_support_note_text(tool_input)
        record_check("Custom tools", "pass", {"output_item_types": returned_item_types, "normalized_note": normalized_note})
        record_response("Normalized support note", "text", normalized_note)
        print_labeled_json("Result: returned output item types", returned_item_types)
        print_labeled_text("Result: custom tool input", tool_input)
        print_labeled_text("Result: application-owned normalized output", normalized_note)
    except LookupError:
        fallback_text = output_text(custom_plan).strip() or "No text content was returned."
        normalized_note = normalize_support_note_text(support_note)
        record_check("Custom tools", "warn", {
            "expected": "custom_tool_call item named normalize_support_note",
            "actual_output_item_types": returned_item_types,
            "meaning": "The model response did not include a custom-tool invocation, so the application fallback normalization is shown for teaching.",
        })
        record_response("Custom tool text fallback", "text", fallback_text)
        record_response("Application-owned normalization fallback", "text", normalized_note)
        print_labeled_json("Result: returned output item types", returned_item_types or ["no typed output items returned"])
        print_labeled_text("Result: model text response", fallback_text)
        print_labeled_text("Result: application-owned normalization", normalized_note)
    print_response_summary(custom_plan)
    print_key_takeaway('Custom tools are useful when the application owns a freeform parsing or execution step.')
except Exception as exc:
    handle_example_error("Custom tools", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>tools</td>
      <td>normalize_support_note</td>
    </tr>
    <tr>
      <td>tool_choice</td>
      <td>{'type': 'custom', 'name': 'normalize_support_note'}</td>
    </tr>
    <tr>
      <td>input</td>
      <td>1 item(s): user: Call normalize_support_note with this exact note. Do not answer directly; send the note to the custom tool: order-8831 | cust-1042 | replacement delayed | customer wants supervisor | offer expedited replacement or 15% co...</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: local fallback normalization</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">ORDER_ID: ORDER-8831
CUSTOMER_ID: CUST-1042
ISSUE: REPLACEMENT DELAYED
CUSTOMER_REQUEST: CUSTOMER WANTS SUPERVISOR
POLICY_OPTION: OFFER EXPEDITED REPLACEMENT OR 15% CONCESSION</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: returned output item types</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">[
  "custom_tool_call"
]</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: custom tool input</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">order-8831 | cust-1042 | replacement delayed | customer wants supervisor | offer expedited replacement or 15% concession</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: application-owned normalized output</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">ORDER_ID: ORDER-8831
CUSTOMER_ID: CUST-1042
ISSUE: REPLACEMENT DELAYED
CUSTOMER_REQUEST: CUSTOMER WANTS SUPERVISOR
POLICY_OPTION: OFFER EXPEDITED REPLACEMENT OR 15% CONCESSION</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_gwyauif44dnxpxrcssrxj4bh57tmgg3zwr67hfcklfswshbbscoa</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['custom_tool_call']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>674</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>37</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>711</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Custom tools are useful when the application owns a freeform parsing or execution step.</div>

## 5. Send Direct File Input

Direct file input is separate from application-managed tools. A file can be included in the current Responses request as an `input_file` item alongside text instructions, which is useful when the model should read the file for this turn without setting up a retrieval index.

### 5.1 Attach a PDF as `input_file`

This cell generates a tiny PDF transcript in memory, attaches it as base64 file data, and asks for exact JSON fields from the document. Inspect the PDF preview, expected fields, parsed response, and usage summary.




```python
from __future__ import annotations
def make_simple_pdf(lines: list[str]) -> bytes:
    def pdf_escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream_lines = ["BT", "/F1 11 Tf", "72 740 Td", "15 TL"]
    for idx, line in enumerate(lines):
        if idx:
            stream_lines.append("T*")
        stream_lines.append(f"({pdf_escape(line)}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + builtins.str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{idx} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    return pdf


file_lines = [
    "BrightCart support transcript",
    "Ticket: TICKET-7429",
    "Customer: Maya Chen",
    "Order: ORDER-8831",
    "Product: Standing desk replacement",
    "Issue: Replacement for a damaged item is delayed and carrier scan has not moved",
    "Customer request: Supervisor callback and refund options",
    "Policy options: expedited replacement or 15% concession with agent approval after 48-hour delay",
]
file_text = "\n".join(file_lines)
pdf_data = base64.b64encode(make_simple_pdf(file_lines)).decode("utf-8")

expected_direct_file_fields = {
    "ticket_id": "TICKET-7429",
    "customer": "Maya Chen",
    "order_id": "ORDER-8831",
    "product": "Standing desk replacement",
}

direct_file_request = {
    "model": MODEL_ID,
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "filename": "brightcart-support-transcript.pdf",
                    "file_data": f"data:application/pdf;base64,{pdf_data}",
                },
                {
                    "type": "input_text",
                    "text": (
                        "Read the attached PDF support transcript and return JSON with keys "
                        "ticket_id, customer, order_id, product, issue, requested_resolution, and policy_options. "
                        "Use exact values from the file. Do not return null for fields that are present in the file."
                    ),
                },
            ],
        }
    ],
    "text": {"format": {"type": "json_object"}},
    "max_output_tokens": 1024,
    "store": False,
}

print_labeled_text("Result: PDF transcript preview", file_text)
print_request_shape(direct_file_request)
print_labeled_json("Result: expected fields", expected_direct_file_fields)
try:
    direct_file_response = create_response(**direct_file_request)
    raw_direct_file_output = output_text(direct_file_response).strip()
    try:
        direct_file_payload = json.loads(raw_direct_file_output)
        missing_or_empty = [
            key for key, expected in expected_direct_file_fields.items()
            if builtins.str(direct_file_payload.get(key, "")).strip().lower() != expected.lower()
        ]
        null_fields = [key for key, value in direct_file_payload.items() if value in {None, "", []}]
        if missing_or_empty or null_fields:
            record_check("Direct file inputs", "warn", {
                "message": "The request completed, but the model did not extract the expected values from the attached PDF.",
                "missing_or_unexpected_fields": missing_or_empty,
                "empty_fields": null_fields,
                "payload": direct_file_payload,
            })
            record_response("Support transcript extraction returned by model", "json", direct_file_payload)
            print_labeled_text("Result", "The request completed, but the model did not extract the expected values from the attached PDF.")
            print_labeled_json("Result: returned JSON", direct_file_payload)
        else:
            record_check("Direct file inputs", "pass", direct_file_payload)
            record_response("Support transcript extraction", "json", direct_file_payload)
            print_labeled_json("Result", direct_file_payload)
    except Exception as parse_exc:
        record_check("Direct file inputs", "warn", {
            "message": "The request completed, but the response was not valid JSON.",
            "text_sample": raw_direct_file_output[:600],
            "error": builtins.str(parse_exc),
        })
        record_response("Support transcript extraction text", "text", raw_direct_file_output[:1200])
        print_labeled_text("Result", raw_direct_file_output[:1200])
    print_response_summary(direct_file_response)
    print_key_takeaway('Direct file input is useful when the file should be read in the current request context.')
except Exception as exc:
    handle_example_error("Direct file inputs", exc)
```

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: PDF transcript preview</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">BrightCart support transcript
Ticket: TICKET-7429
Customer: Maya Chen
Order: ORDER-8831
Product: Standing desk replacement
Issue: Replacement for a damaged item is delayed and carrier scan has not moved
Customer request: Supervisor callback and refund options
Policy options: expedited replacement or 15% concession with agent approval after 48-hour delay</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>text format</td>
      <td>json_object</td>
    </tr>
    <tr>
      <td>input</td>
      <td>1 item(s): user: input_file: brightcart-support-transcript.pdf; input_text: Read the attached PDF support transcript and return JSON with keys ticket_id, customer, order_id, product, issue, reques...</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: expected fields</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "ticket_id": "TICKET-7429",
  "customer": "Maya Chen",
  "order_id": "ORDER-8831",
  "product": "Standing desk replacement"
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{"ticket_id":"TICKET-7429","customer":"Maya Chen","order_id":"ORDER-8831","product":"Standing desk replacement","issue":"Replacement for a damaged item is delayed and carrier scan has not moved","requested_resolution":"Supervisor callback and refund options","policy_options":"expedited replacement or 15% concession with agent approval after 48-hour delay"}</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_colsvndmpjd6qczpemdjscmsbjefmgl5vh6i7alqt52jflentfna</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>713</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>82</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>795</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Direct file input is useful when the file should be read in the current request context.</div>

## 6. Manage Conversation State

Conversation state determines how follow-up turns receive prior context. The Responses API supports stored continuation with `previous_response_id`, and applications can also manage state themselves by resending relevant input history. This section compares both patterns, then shows encrypted reasoning context where supported.



### 6.1 Continue with `previous_response_id`

Use `previous_response_id` to continue from a stored response without resending the full prior prompt. The first request stores the BrightCart case details; the second request passes only the new follow-up instruction plus the previous response ID. Inspect whether the follow-up preserves the order, customer, issue, and next action.


```python
from __future__ import annotations
promised_delivery = (date.today() + timedelta(days=2)).isoformat()
stateful_seed_input = (
    f"Customer Maya Chen opened ticket TICKET-4812 about order ORDER-8831. "
    "The item is a standing desk replacement for a damaged delivery. "
    f"The promised delivery date is {promised_delivery}, but the carrier scan has not moved in 36 hours. "
    "Customer sentiment is frustrated because this is the second attempt. "
    "Support policy says to offer expedited replacement or a 15% concession if the delay exceeds 48 hours. "
    "Escalation owner is Tier 2 Returns."
)
stateful_followup_input = "Return five labeled lines: ticket ID, order ID, customer name, issue, and next best action."
stateful_request_shape = {
    "model": MODEL_ID,
    "input": stateful_followup_input,
    "previous_response_id": "<response-id-from-prior-stored-turn>",
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(stateful_request_shape)
try:
    stateful_turn_1 = create_response(model=MODEL_ID, input=stateful_seed_input, max_output_tokens=1024, store=True)
    remember_stored_response(stateful_turn_1)
    stateful_turn_2 = create_response(model=MODEL_ID, input=stateful_followup_input, previous_response_id=stateful_turn_1.id, max_output_tokens=1024, store=False)
    text = output_text(stateful_turn_2).strip()
    require("order-8831" in text.lower() or "maya" in text.lower(), "Stateful continuation response missed expected support context.")
    record_check("Stateful continuation", "pass", stateful_turn_1.id)
    record_response("Stateful support handoff", "text", text)
    print_labeled_text("Result", text)
    print_response_summary(stateful_turn_2)
    print_key_takeaway('previous_response_id lets a follow-up use stored context without resending the full prior turn.')
except Exception as exc:
    handle_example_error("Stateful continuation", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>previous_response_id</td>
      <td>&#x3C;response-id-from-prior-stored-turn></td>
    </tr>
    <tr>
      <td>input</td>
      <td>Return five labeled lines: ticket ID, order ID, customer name, issue, and next best action.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Ticket ID: TICKET-4812
Order ID: ORDER-8831
Customer Name: Maya Chen
Issue: Replacement standing desk shipment for damaged delivery has had no carrier movement for 36 hours; customer is frustrated because this is the second attempt
Next Best Action: Monitor until 48 hours without movement, then offer expedited replacement or 15% concession and escalate to Tier 2 Returns if needed</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_gkgqadc2gd24747lmhy5waftt5tga7eibtv67k77lndjgbuioo6q</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>715</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>86</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>801</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> previous_response_id lets a follow-up use stored context without resending the full prior turn.</div>

### 6.2 Rebuild Stateless Context

Stateless continuation means the application sends the relevant history on every request. This is a good fit when your product already owns conversation storage, retention policy, or audit requirements. This cell sends a short chat history plus a new handoff instruction and inspects the summary and token usage.


```python
from __future__ import annotations
stateless_history = [
    {"role": "user", "content": "Support chat TICKET-3920: Customer Jordan Lee says ORDER-7718 arrived with a cracked monitor stand."},
    {"role": "assistant", "content": "Captured damaged-item issue for ORDER-7718 and asked for preferred resolution."},
    {"role": "user", "content": "Jordan wants a replacement shipped this week and asks whether the damaged item must be returned first."},
]
stateless_payload = {
    "model": MODEL_ID,
    "input": stateless_history + [{"role": "user", "content": "Summarize this support chat for the next agent in five labeled plain-text lines. Do not use leading hyphens or bold text."}],
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(stateless_payload)
try:
    stateless_response = create_response(**stateless_payload)
    stateless_text = output_text(stateless_response).strip()
    require(stateless_text, "Stateless continuation response did not return text.")
    record_check("Stateless continuation", "pass", summarize_response(stateless_response))
    record_response("Stateless support handoff", "text", stateless_text)
    print_labeled_text("Result", stateless_text)
    print_response_summary(stateless_response)
    print_key_takeaway('Stateless continuation sends the relevant history with each request when the application owns conversation storage.')
except Exception as exc:
    handle_example_error("Stateless continuation", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>input</td>
      <td>4 item(s): user: Support chat TICKET-3920: Customer Jordan Lee says ORDER-7718 arrived with a cracked monitor stand.; assistant: Captured damaged-item issue for ORDER-7718 and asked for preferred resolution.; user: Jordan wants a replacement shipped this week and asks whether the damaged item must be returned first.; user: Summarize this support chat for the next agent in five labeled plain-text lines. Do not use leading hyphens or bold text.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Customer: Jordan Lee reported ORDER-7718 arrived with a cracked monitor stand.
Issue: Damaged item; monitor stand is cracked on arrival.
Requested Resolution: Customer wants a replacement shipped this week.
Open Question: Jordan asked whether the damaged item must be returned before replacement is sent.
Status: Damage claim captured and awaiting next-agent confirmation on replacement timing and return requirement.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_mezt6yqizyswuvujvudnonr34b73ndyyu2qsfncgtjyppzie5vva</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>255</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>78</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>333</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Stateless continuation sends the relevant history with each request when the application owns conversation storage.</div>

### 6.3 Carry Encrypted Reasoning Context

Reasoning-capable models may return reasoning items and encrypted reasoning content when requested. This cell asks for encrypted reasoning metadata, carries prior response items into a follow-up request, and inspects whether encrypted content was returned. The hidden reasoning text is not exposed; the application only carries opaque context forward where supported.

Official docs: [Reasoning models](https://developers.openai.com/api/docs/guides/reasoning) describes reasoning models and reasoning effort in Responses workflows.


```python
from __future__ import annotations
encrypted_history = [
    {"role": "user", "content": "For a customer-support assistant handling names, order IDs, and refund context, compare stateful and stateless continuation in two sentences."}
]
encrypted_turn_payload = {
    "model": MODEL_ID,
    "input": encrypted_history,
    "reasoning": {"effort": "medium"},
    "include": ["reasoning.encrypted_content"],
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(encrypted_turn_payload)
try:
    encrypted_turn_1 = create_response(**encrypted_turn_payload)
    encrypted_turn_2 = create_response(
        model=MODEL_ID,
        input=encrypted_history + response_items(encrypted_turn_1) + [
            {"role": "user", "content": "Based on the prior reasoning context, recommend one approach for a regulated support workflow in two labeled plain-text lines. Do not use leading hyphens or bold text."}
        ],
        max_output_tokens=1024,
        store=False,
    )
    reasoning_items = [item for item in response_items(encrypted_turn_1) if item.get("type") == "reasoning"]
    has_encrypted_content = any(item.get("encrypted_content") for item in reasoning_items)
    record_check("Encrypted reasoning", "pass", {"encrypted_content_returned": has_encrypted_content, "reasoning_item_count": len(reasoning_items)})
    encrypted_answer = output_text(encrypted_turn_2).strip()
    record_response("State strategy recommendation", "text", encrypted_answer)
    print_labeled_json("Result: reasoning metadata", {
        "returned_item_types": [item.get("type") for item in response_items(encrypted_turn_1)],
        "encrypted_reasoning_content_returned": has_encrypted_content,
    })
    print_labeled_text("Result: follow-up answer", encrypted_answer)
    print_response_summary(encrypted_turn_2)
    print_key_takeaway('Encrypted reasoning content can be carried forward where supported without exposing hidden reasoning text.')
except Exception as exc:
    handle_example_error("Encrypted reasoning", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>reasoning</td>
      <td>{'effort': 'medium'}</td>
    </tr>
    <tr>
      <td>include</td>
      <td>['reasoning.encrypted_content']</td>
    </tr>
    <tr>
      <td>input</td>
      <td>1 item(s): user: For a customer-support assistant handling names, order IDs, and refund context, compare stateful and stateless continuation in two sentences.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: reasoning metadata</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "returned_item_types": [
    "reasoning",
    "message"
  ],
  "encrypted_reasoning_content_returned": true
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: follow-up answer</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Recommendation: Stateless continuation
Reason: In a regulated support workflow, requiring names, order IDs, and refund context to be explicitly provided each turn improves controllability, auditability, and data-minimization, reducing the risk of unintended retention or cross-session leakage.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_qmjgoymsxqf32ht3apisbvscrv4d5t5x2tnxeftkxwpyl4eppjka</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>295</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>56</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>351</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Encrypted reasoning content can be carried forward where supported without exposing hidden reasoning text.</div>

## 7. Use Prompt Caching

Prompt caching improves latency and cost when requests share an exact static prefix.

### 7.1 Compare Two Cache-Keyed Requests

This cell places stable BrightCart policy text at the beginning of the input, sends the same request twice with a `prompt_cache_key`, and compares token metadata. Inspect `cached_input_tokens` on the second response when the endpoint returns cache details.

Note: `PROMPT_CACHE_RETENTION` is selected from the active `MODEL_ID`. It uses `24h` for `openai.gpt-5.5` and later models, and `in_memory` for `openai.gpt-5.4`.


```python
from __future__ import annotations
base_support_policy = [
    "BrightCart support policy:",
    "1. Be empathetic, concise, and specific about the customer's order.",
    "2. Do not promise refunds, credits, or delivery dates unless the policy context supports it.",
    "3. For damaged-item replacements, check replacement status before offering concessions.",
    "4. If a replacement delay exceeds 48 hours, offer expedited replacement or a 15% concession subject to agent approval.",
]
policy_reference_paragraph = (
    "Expanded cacheable policy context: BrightCart agents should identify the customer, order ID, replacement status, "
    "carrier scan age, promised delivery window, item category, prior concessions, and supervisor approval needs before "
    "drafting a customer-facing answer. The assistant should preserve a calm tone, avoid unsupported promises, separate "
    "confirmed facts from assumptions, recommend one clear next action, and document why any escalation, expedited "
    "replacement, or concession is appropriate. Repeated policy context like this is intentionally stable across many "
    "requests so prompt caching can reuse the prefix when the same cache key is supplied."
)
expanded_policy_context = "\n".join(
    f"Policy reference paragraph {idx + 1}: {policy_reference_paragraph}"
    for idx in range(32)
)
stable_support_policy = "\n".join(base_support_policy + [expanded_policy_context])
cache_input = [
    {"role": "system", "content": stable_support_policy},
    {"role": "user", "content": "Draft a two-sentence agent reply for Maya Chen about delayed replacement order ORDER-8831."},
]
estimated_cache_input_words = len(json.dumps(cache_input).split())
require(estimated_cache_input_words > 2048, f"Prompt-cache input should be over 2048 words; found {estimated_cache_input_words}.")
cache_payload = {
    "model": MODEL_ID,
    "input": cache_input,
    "prompt_cache_key": "brightcart-support-policy-v1",
    "prompt_cache_retention": PROMPT_CACHE_RETENTION,
    "max_output_tokens": 1024,
    "store": False,
}

print_request_shape(cache_payload)
print_labeled_json("Prompt-cache input size", {"estimated_input_words": estimated_cache_input_words, "target_minimum_tokens": 2048})
try:
    cache_response_1 = create_response(**cache_payload)
    cache_response_2 = create_response(**cache_payload)
    cache_summary_1 = summarize_response(cache_response_1)
    cache_summary_2 = summarize_response(cache_response_2)
    cache_comparison = pd.DataFrame([
        {
            "request": "first",
            "input_tokens": cache_summary_1.get("input_tokens"),
            "cached_input_tokens": cache_summary_1.get("cached_input_tokens"),
            "output_tokens": cache_summary_1.get("output_tokens"),
            "total_tokens": cache_summary_1.get("total_tokens"),
        },
        {
            "request": "second",
            "input_tokens": cache_summary_2.get("input_tokens"),
            "cached_input_tokens": cache_summary_2.get("cached_input_tokens"),
            "output_tokens": cache_summary_2.get("output_tokens"),
            "total_tokens": cache_summary_2.get("total_tokens"),
        },
    ])
    record_check("Prompt caching", "pass" if cache_summary_2.get("cached_input_tokens") is not None else "warn", {"first": cache_summary_1, "second": cache_summary_2})
    cache_reply = output_text(cache_response_2).strip()
    record_response("Prompt-cache token comparison", "table", cache_comparison)
    record_response("Cached support-policy reply", "text", cache_reply)

    print_labeled_text("Result", cache_reply)
    print_labeled_json("First request summary", cache_summary_1)
    print_labeled_json("Second request summary", cache_summary_2)
    print_label("Response summary")
    display_wrapped_table(cache_comparison, max_col_width_px=260)
    print_key_takeaway('cached_input_tokens is the metadata field to inspect for prompt-cache reuse.')
except Exception as exc:
    handle_example_error("Prompt caching", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>prompt_cache_key</td>
      <td>brightcart-support-policy-v1</td>
    </tr>
    <tr>
      <td>prompt_cache_retention</td>
      <td>in_memory</td>
    </tr>
    <tr>
      <td>input</td>
      <td>2 item(s): system: BrightCart support policy: 1. Be empathetic, concise, and specific about the customer's order. 2. Do not promise refunds, credits, or delivery dates unless the policy context supports it. 3. For damaged-item replacements...; user: Draft a two-sentence agent reply for Maya Chen about delayed replacement order ORDER-8831.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Prompt-cache input size</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "estimated_input_words": 3016,
  "target_minimum_tokens": 2048
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">Hi Maya, I’m sorry your replacement order ORDER-8831 is delayed. I’m checking the latest replacement and carrier status now so I can confirm the best next step for you without making you wait longer than necessary.</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">First request summary</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "id": "resp_3w6r6ipbqa5z2max35awv3i23i5sjmfa33zzw3vhpgqxcvchhkgq",
  "model": "openai.gpt-5.4",
  "status": "completed",
  "output_item_types": [
    "message"
  ],
  "input_tokens": 3970,
  "output_tokens": 66,
  "total_tokens": 4036,
  "cached_input_tokens": 0,
  "reasoning_output_tokens": 0,
  "service_tier": "default"
}</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Second request summary</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "id": "resp_zzjeqttoswdjdwwl56xpolvly23w4h2n5dtsdoddgxqwfbkn7npq",
  "model": "openai.gpt-5.4",
  "status": "completed",
  "output_item_types": [
    "message"
  ],
  "input_tokens": 3970,
  "output_tokens": 48,
  "total_tokens": 4018,
  "cached_input_tokens": 0,
  "reasoning_output_tokens": 0,
  "service_tier": "default"
}</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>request</th>
      <th>input_tokens</th>
      <th>cached_input_tokens</th>
      <th>output_tokens</th>
      <th>total_tokens</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>first</td>
      <td>3970</td>
      <td>0</td>
      <td>66</td>
      <td>4036</td>
    </tr>
    <tr>
      <td>second</td>
      <td>3970</td>
      <td>0</td>
      <td>48</td>
      <td>4018</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> cached_input_tokens is the metadata field to inspect for prompt-cache reuse.</div>

## 8. Run Background Work

Background mode starts a response asynchronously and lets the application poll for terminal status.

### 8.1 Submit and Poll a Background Response

This cell sends `background=true`, stores the response ID, polls while status is queued or in progress, and then prints the final manager summary. Inspect the status history, final status, response ID, and token summary.




```python
from __future__ import annotations
backlog = """
Same-day BrightCart support backlog:
1. 18 delayed-order contacts, mostly from the West Coast distribution lane.
2. 7 damaged-item replacement contacts; 3 mention replacement delays.
3. 5 return-window exception requests after holiday promotions.
""".strip()
background_payload = {
    "model": MODEL_ID,
    "input": f"Return exactly three labeled plain-text lines for a support-manager summary: theme, risk, next action. Keep each line under 12 words. Do not use leading hyphens or bold text.\n\n{backlog}",
    "background": True,
    "max_output_tokens": 1024,
    "store": True,
}

print_request_shape(background_payload)
try:
    background_response = create_response(**background_payload)
    remember_stored_response(background_response)
    status_history = [getattr(background_response, "status", None)]
    for _ in range(15):
        if getattr(background_response, "status", None) not in {"queued", "in_progress"}:
            break
        time.sleep(2)
        background_response = retrieve_response(background_response.id)
        status_history.append(getattr(background_response, "status", None))
    background_summary = summarize_response(background_response)
    manager_summary = output_text(background_response).strip()
    require(manager_summary, "Background response did not return text.")
    status = "pass" if background_summary.get("status") in {None, "completed"} else "warn"
    record_check("Background mode", status, {"status_history": status_history, "id": getattr(background_response, "id", None), "final_status": background_summary.get("status")})
    record_response("Background manager summary", "text", manager_summary)
    print_labeled_json("Result: status history", status_history)
    print_labeled_text("Result: manager summary", manager_summary)
    print_response_summary(background_summary)
    print_key_takeaway('Background mode starts work asynchronously and lets the application poll by response ID.')
except Exception as exc:
    handle_example_error("Background mode", exc)
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>True</td>
    </tr>
    <tr>
      <td>background</td>
      <td>True</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Return exactly three labeled plain-text lines for a support-manager summary: theme, risk, next action. Keep each line under 12 words. Do not use leading hyphens or bold text. Same-day BrightCart support backlog: 1. 18 delayed-order contacts, mostly from the We...</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: status history</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">[
  "in_progress",
  "completed"
]</div>
    </div>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result: manager summary</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">theme: Shipping delays dominate, especially West Coast distribution lane.
risk: Rising dissatisfaction from delays, replacements, and return exceptions.
next action: Escalate West Coast lane issues and review holiday return policy.</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>id</td>
      <td>resp_lmmtsvgk3ntolh5ci5vxccmsa6uxcgrsq7v54jpz7oewmociyesa</td>
    </tr>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>status</td>
      <td>completed</td>
    </tr>
    <tr>
      <td>output_item_types</td>
      <td>['message']</td>
    </tr>
    <tr>
      <td>input_tokens</td>
      <td>246</td>
    </tr>
    <tr>
      <td>cached_input_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>output_tokens</td>
      <td>45</td>
    </tr>
    <tr>
      <td>total_tokens</td>
      <td>291</td>
    </tr>
    <tr>
      <td>reasoning_output_tokens</td>
      <td>0</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>default</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Background mode starts work asynchronously and lets the application poll by response ID.</div>

## 9. Compact Long-Running Context

Compaction reduces long conversation state into durable facts, open questions, constraints, and next actions. This cell documents the application-side compaction pattern as a small JSON object so the concept is clear without adding another live feature path. Inspect which facts are kept and which details are omitted before the next turn.




```python
from __future__ import annotations
compaction_note = {
    "feature": "Compaction",
    "how_to_apply": "Summarize older support turns into durable facts, open questions, policy constraints, and next actions before continuing the workflow.",
    "brightcart_example": {
        "durable_facts": ["Customer Maya Chen", "ORDER-8831", "replacement delayed", "carrier scan stale"],
        "policy_constraints": ["Do not promise refund without eligibility", "Offer expedited replacement or 15% concession after 48-hour delay with approval"],
        "next_action": "Check latest carrier scan and supervisor callback status.",
    },
}
record_check("Compaction", "documented", compaction_note)
record_response("Compacted support context", "json", compaction_note)
print_json(compaction_note)
```

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">JSON</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "feature": "Compaction",
  "how_to_apply": "Summarize older support turns into durable facts, open questions, policy constraints, and next actions before continuing the workflow.",
  "brightcart_example": {
    "durable_facts": [
      "Customer Maya Chen",
      "ORDER-8831",
      "replacement delayed",
      "carrier scan stale"
    ],
    "policy_constraints": [
      "Do not promise refund without eligibility",
      "Offer expedited replacement or 15% concession after 48-hour delay with approval"
    ],
    "next_action": "Check latest carrier scan and supervisor callback status."
  }
}</div>
    </div>

## 10. Run Operational Smoke Checks

Operational smoke checks are lightweight setup checks, not a load test or service-level measurement. This cell sends three short requests, measures local elapsed time, summarizes success rate and token usage, and infers the region from the configured Bedrock base URL. Inspect latency, completion status, sample outputs, and token totals.


```python
from __future__ import annotations
def infer_region_from_base_url(base_url: str) -> str | None:
    host = normalize_base_url(base_url).replace("https://", "").split("/")[0]
    for part in host.split("."):
        if part.count("-") >= 2 and any(char.isdigit() for char in part):
            return part
    return None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 3)


operations_features = ["Latency runtime example", "Throughput runtime example", "Reliability runtime example", "Region check"]
operations_payload = {"model": MODEL_ID, "input": "Reply with one short customer-support sentence.", "service_tier": "auto", "max_output_tokens": 1024, "store": False}

print_request_shape(operations_payload)
if not RUN_RESPONSIVENESS_CHECK:
    record_check("Endpoint responsiveness", "skipped", "BEDROCK_RESPONSIVENESS_CHECK is disabled.")
    print_labeled_text("Result", "Responsiveness check disabled.")
else:
    prompts = [
        "Reply in one short sentence: apologize for a delayed replacement order.",
        "Reply with one metric name for support-assistant quality.",
        "Reply in one short sentence: hand off a return exception to a supervisor.",
    ]
    samples = []
    for idx, prompt in enumerate(prompts):
        started = time.perf_counter()
        try:
            response = create_response(model=MODEL_ID, input=prompt, service_tier="auto", max_output_tokens=1024, store=False)
            elapsed = time.perf_counter() - started
            summary = summarize_response(response)
            text = output_text(response).strip()
            samples.append({
                "ok": bool(text),
                "latency_seconds": round(elapsed, 3),
                "output_tokens": summary.get("output_tokens") or 0,
                "total_tokens": summary.get("total_tokens") or 0,
                "status": summary.get("status"),
                "sample_output": text[:140],
            })
        except Exception as exc:
            elapsed = time.perf_counter() - started
            samples.append({"ok": False, "latency_seconds": round(elapsed, 3), "error": describe_api_error(exc)})

    successes = [sample for sample in samples if sample["ok"]]
    completed = [sample for sample in successes if sample.get("status") in {None, "completed"}]
    latencies = [sample["latency_seconds"] for sample in successes]
    responsiveness_summary = {
        "region_hint": infer_region_from_base_url(BASE_URL),
        "base_url_host": normalize_base_url(BASE_URL).replace("https://", "").split("/")[0],
        "sample_count": len(samples),
        "success_rate": len(successes) / len(samples) if samples else 0,
        "completed_rate": len(completed) / len(samples) if samples else 0,
        "avg_latency_seconds": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "p50_latency_seconds": percentile(latencies, 50),
        "p90_latency_seconds": percentile(latencies, 90),
        "total_output_tokens": sum(sample.get("output_tokens", 0) for sample in samples),
        "total_tokens": sum(sample.get("total_tokens", 0) for sample in samples),
    }
    status = "pass" if len(successes) == len(samples) and len(completed) == len(samples) else "warn"
    for feature in operations_features:
        record_check(feature, status, responsiveness_summary)
    record_response("Endpoint responsiveness summary", "json", {**responsiveness_summary, "samples": samples})
    print_labeled_json("Result", responsiveness_summary)
    print_label("Response summary")
    display_wrapped_table(pd.DataFrame(samples), max_col_width_px=360)
    print_key_takeaway('Responsiveness samples are setup checks, not a load test or service-level measurement.')
```

<div style="font-weight:600; margin:8px 0 4px;">Request shape</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>field</th>
      <th>value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>model</td>
      <td>openai.gpt-5.4</td>
    </tr>
    <tr>
      <td>max_output_tokens</td>
      <td>1024</td>
    </tr>
    <tr>
      <td>store</td>
      <td>False</td>
    </tr>
    <tr>
      <td>service_tier</td>
      <td>auto</td>
    </tr>
    <tr>
      <td>input</td>
      <td>Reply with one short customer-support sentence.</td>
    </tr>
  </tbody>
</table>

<div style="border:1px solid #d0d7de; border-radius:6px; margin:8px 0; overflow:hidden; font-size:13px;">
      <div style="padding:6px 8px; font-weight:600;">Result</div>
      <div style="padding:8px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.45;">{
  "region_hint": "us-west-2",
  "base_url_host": "bedrock-mantle.us-west-2.api.aws",
  "sample_count": 3,
  "success_rate": 1.0,
  "completed_rate": 1.0,
  "avg_latency_seconds": 0.362,
  "p50_latency_seconds": 0.377,
  "p90_latency_seconds": 0.4,
  "total_output_tokens": 34,
  "total_tokens": 544
}</div>
    </div>

<div style="font-weight:600; margin:8px 0 4px;">Response summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>ok</th>
      <th>latency_seconds</th>
      <th>output_tokens</th>
      <th>total_tokens</th>
      <th>status</th>
      <th>sample_output</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>True</td>
      <td>0.400</td>
      <td>14</td>
      <td>184</td>
      <td>completed</td>
      <td>We apologize for the delay with your replacement order.</td>
    </tr>
    <tr>
      <td>True</td>
      <td>0.310</td>
      <td>6</td>
      <td>174</td>
      <td>completed</td>
      <td>Resolution Rate</td>
    </tr>
    <tr>
      <td>True</td>
      <td>0.377</td>
      <td>14</td>
      <td>186</td>
      <td>completed</td>
      <td>I’m escalating the return exception to a supervisor.</td>
    </tr>
  </tbody>
</table>

<div style="border-left:4px solid #1f6feb; padding:6px 10px; margin:8px 0;"><strong>Key takeaway:</strong> Responsiveness samples are setup checks, not a load test or service-level measurement.</div>

## 11. Clean Up and Review Results

Stored responses created by lifecycle, stateful continuation, and background examples are tracked in `STORED_RESPONSE_IDS`. This final cell attempts to delete stored responses when cleanup is enabled, then prints the run summary and example-response gallery. Inspect warnings first; they usually identify endpoint configuration, model availability, or feature-support differences.


```python
from __future__ import annotations

cleanup_rows = []
tracked_ids = list(dict.fromkeys(STORED_RESPONSE_IDS))

if not tracked_ids:
    cleanup_rows.append({"response_id": "none", "status": "no stored responses tracked", "detail": ""})
elif not CLEAN_UP_STORED_RESPONSES:
    for stored_id in tracked_ids:
        cleanup_rows.append({"response_id": stored_id, "status": "skipped", "detail": "BEDROCK_CLEANUP_STORED_RESPONSES is disabled"})
    record_check("Stored response cleanup", "skipped", cleanup_rows)
else:
    for stored_id in tracked_ids:
        try:
            delete_result = delete_response(stored_id)
            cleanup_rows.append({"response_id": stored_id, "status": "deleted", "detail": compact_text(to_dict(delete_result), 240)})
        except Exception as exc:
            cleanup_rows.append({"response_id": stored_id, "status": "warn", "detail": describe_api_error(exc)})
    cleanup_status = "pass" if all(row["status"] == "deleted" for row in cleanup_rows) else "warn"
    record_check("Stored response cleanup", cleanup_status, cleanup_rows)

print_label("Stored response cleanup")
display_wrapped_table(pd.DataFrame(cleanup_rows), max_col_width_px=520)

summary_df = pd.DataFrame(RESULTS_SUMMARY)
print_label("Run summary")
display_wrapped_table(summary_df, max_col_width_px=620)

print_label("Example responses")
print_response_gallery()
```

<div style="font-weight:600; margin:8px 0 4px;">Stored response cleanup</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>response_id</th>
      <th>status</th>
      <th>detail</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia</td>
      <td>warn</td>
      <td>{'exception_class': 'AuthenticationError', 'status_code': 401, 'retryable': False, 'request_id': 'req_gkni5zyr7lkjkz2vfiwvkev2qgxs76crcwz5whhjrdkma7up3yta', 'message': 'Error code: 401 - {'error': {'code': 'invalid_api_key', 'message': 'The security token included in the request is invalid.', 'param': None, 'type': 'permission_denied_error'}}'}</td>
    </tr>
    <tr>
      <td>resp_vjrtvnakcgxjhnq5b7cj7rtowtdh7chkkf3aqwbdkynhjqiklp3a</td>
      <td>warn</td>
      <td>{'exception_class': 'AuthenticationError', 'status_code': 401, 'retryable': False, 'request_id': 'req_vvwhsmp2rkrzwbkajqdpdod2o4j5xo2vxelzxbcp2fjan2ybwc2a', 'message': 'Error code: 401 - {'error': {'code': 'invalid_api_key', 'message': 'The security token included in the request is invalid.', 'param': None, 'type': 'permission_denied_error'}}'}</td>
    </tr>
    <tr>
      <td>resp_lmmtsvgk3ntolh5ci5vxccmsa6uxcgrsq7v54jpz7oewmociyesa</td>
      <td>warn</td>
      <td>{'exception_class': 'AuthenticationError', 'status_code': 401, 'retryable': False, 'request_id': 'req_btgbpxspnokm3wzfndybnfuv3kjudxt3r2ihlsmru7ziisn52goa', 'message': 'Error code: 401 - {'error': {'code': 'invalid_api_key', 'message': 'The security token included in the request is invalid.', 'param': None, 'type': 'permission_denied_error'}}'}</td>
    </tr>
  </tbody>
</table>

<div style="font-weight:600; margin:8px 0 4px;">Run summary</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>name</th>
      <th>status</th>
      <th>detail</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Endpoint shape</td>
      <td>pass</td>
      <td>https://bedrock-mantle.us-west-2.api.aws/openai/v1/responses</td>
    </tr>
    <tr>
      <td>Model selection</td>
      <td>pass</td>
      <td>Using configured model; model-list metadata is not required for requests.</td>
    </tr>
    <tr>
      <td>Error handling</td>
      <td>pass</td>
      <td>{"normalized_fields": ["exception_class", "status_code", "retryable", "request_id", "message"], "retryable_status_codes": [408, 409, 429, 500, 502, 503, 504], "notes": "call_with_retries(...) uses this taxonomy for transient retry handling."}</td>
    </tr>
    <tr>
      <td>Text generation</td>
      <td>pass</td>
      <td>resp_naythl6fvzhoctlsdogd4vpr673q5ibagqqpiujbast3sy6viroa</td>
    </tr>
    <tr>
      <td>Text generation</td>
      <td>pass</td>
      <td>{"id": "resp_nmvqefzghd5hi67uwy4wfvhwnnzild3lslqsxqor3cat63kmucoq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["reasoning", "message"], "input_tokens": 177, "output_tokens": 129, "total_tokens": 306, "cached_input_tokens": 0, "reasoning_output_tokens": 18, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Reasoning effort</td>
      <td>pass</td>
      <td>{"id": "resp_nmvqefzghd5hi67uwy4wfvhwnnzild3lslqsxqor3cat63kmucoq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["reasoning", "message"], "input_tokens": 177, "output_tokens": 129, "total_tokens": 306, "cached_input_tokens": 0, "reasoning_output_tokens": 18, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Responses lifecycle</td>
      <td>pass</td>
      <td>resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia</td>
    </tr>
    <tr>
      <td>Response schema</td>
      <td>pass</td>
      <td>{"id": "resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["message"], "input_tokens": 198, "output_tokens": 109, "total_tokens": 307, "cached_input_tokens": 0, "reasoning_output_tokens": 0, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Usage metadata</td>
      <td>pass</td>
      <td>{"id": "resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["message"], "input_tokens": 198, "output_tokens": 109, "total_tokens": 307, "cached_input_tokens": 0, "reasoning_output_tokens": 0, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Prompt caching</td>
      <td>pass</td>
      <td>{"id": "resp_q4akwbeynfwfwnt5i4tdwkpcgsffdu4lqvng7lnwaob53opswvwq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["reasoning", "message"], "input_tokens": 183, "output_tokens": 91, "total_tokens": 274, "cached_input_tokens": 0, "reasoning_output_tokens": 34, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Service tier</td>
      <td>pass</td>
      <td>{"id": "resp_q4akwbeynfwfwnt5i4tdwkpcgsffdu4lqvng7lnwaob53opswvwq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["reasoning", "message"], "input_tokens": 183, "output_tokens": 91, "total_tokens": 274, "cached_input_tokens": 0, "reasoning_output_tokens": 34, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Reasoning effort</td>
      <td>pass</td>
      <td>{"id": "resp_q4akwbeynfwfwnt5i4tdwkpcgsffdu4lqvng7lnwaob53opswvwq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["reasoning", "message"], "input_tokens": 183, "output_tokens": 91, "total_tokens": 274, "cached_input_tokens": 0, "reasoning_output_tokens": 34, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Structured Outputs</td>
      <td>pass</td>
      <td>{"ticket_id": "TICKET-7429", "category": "delivery_delay", "priority": "urgent", "customer_sentiment": "frustrated and time-sensitive", "summary": "Customer Maya Chen reports that ORDER-8831 is a replacement shipment for a previously damaged standing desk. The replacement is now 2 days late, carrier tracking has not updated, and she needs the desk delivered before Monday. She is requesting a supervisor callback and wants to know refund options if the replacement cannot arrive in time.", "require...</td>
    </tr>
    <tr>
      <td>JSON mode</td>
      <td>pass</td>
      <td>{"customer_name": "Maya Chen", "order_id": "ORDER-8831", "issue_summary": "Customer is asking about a delayed replacement order. The carrier tracking scan is stale and has not updated.", "next_step": "Handoff to support to investigate the carrier delay, verify shipment status, and provide Maya Chen with an update or resolution.", "metrics_to_watch": ["tracking_scan_recency", "carrier_exception_status", "replacement_order_delivery_eta", "customer_follow_up_time"]}</td>
    </tr>
    <tr>
      <td>Verbosity</td>
      <td>pass</td>
      <td>{"compact_chars": 182, "detailed_chars": 332}</td>
    </tr>
    <tr>
      <td>Function calling</td>
      <td>pass</td>
      <td>{"tool_choice_used": "required", "arguments": {"order_id": "ORDER-8831"}}</td>
    </tr>
    <tr>
      <td>Parallel tool calls</td>
      <td>warn</td>
      <td>{"returned_order_ids": ["ORDER-8831"], "missing_order_ids": ["ORDER-2044"]}</td>
    </tr>
    <tr>
      <td>Custom tools</td>
      <td>pass</td>
      <td>{"output_item_types": ["custom_tool_call"], "normalized_note": "ORDER_ID: ORDER-8831\nCUSTOMER_ID: CUST-1042\nISSUE: REPLACEMENT DELAYED\nCUSTOMER_REQUEST: CUSTOMER WANTS SUPERVISOR\nPOLICY_OPTION: OFFER EXPEDITED REPLACEMENT OR 15% CONCESSION"}</td>
    </tr>
    <tr>
      <td>Direct file inputs</td>
      <td>warn</td>
      <td>{"message": "The request completed, but the response was not valid JSON.", "text_sample": "{\"ticket_id\":\"TICKET-7429\",\"customer\":\"Maya Chen\",\"order_id\":\"ORDER-8831\",\"product\":\"Standing desk replacement\",\"issue\":\"Replacement for a damaged item is delayed and carrier scan has not moved\",\"requested_resolution\":\"Supervisor callback and refund options\",\"policy_options\":\"expedited replacement or 15% concession with agent approval after 48-hour delay\"}", "error": "unhashable...</td>
    </tr>
    <tr>
      <td>Stateful continuation</td>
      <td>pass</td>
      <td>resp_vjrtvnakcgxjhnq5b7cj7rtowtdh7chkkf3aqwbdkynhjqiklp3a</td>
    </tr>
    <tr>
      <td>Stateless continuation</td>
      <td>pass</td>
      <td>{"id": "resp_mezt6yqizyswuvujvudnonr34b73ndyyu2qsfncgtjyppzie5vva", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["message"], "input_tokens": 255, "output_tokens": 78, "total_tokens": 333, "cached_input_tokens": 0, "reasoning_output_tokens": 0, "service_tier": "default"}</td>
    </tr>
    <tr>
      <td>Encrypted reasoning</td>
      <td>pass</td>
      <td>{"encrypted_content_returned": true, "reasoning_item_count": 1}</td>
    </tr>
    <tr>
      <td>Prompt caching</td>
      <td>pass</td>
      <td>{"first": {"id": "resp_3w6r6ipbqa5z2max35awv3i23i5sjmfa33zzw3vhpgqxcvchhkgq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["message"], "input_tokens": 3970, "output_tokens": 66, "total_tokens": 4036, "cached_input_tokens": 0, "reasoning_output_tokens": 0, "service_tier": "default"}, "second": {"id": "resp_zzjeqttoswdjdwwl56xpolvly23w4h2n5dtsdoddgxqwfbkn7npq", "model": "openai.gpt-5.4", "status": "completed", "output_item_types": ["message"], "input_tokens": 3970, "outp...</td>
    </tr>
    <tr>
      <td>Background mode</td>
      <td>pass</td>
      <td>{"status_history": ["in_progress", "completed"], "id": "resp_lmmtsvgk3ntolh5ci5vxccmsa6uxcgrsq7v54jpz7oewmociyesa", "final_status": "completed"}</td>
    </tr>
    <tr>
      <td>Compaction</td>
      <td>documented</td>
      <td>{"feature": "Compaction", "how_to_apply": "Summarize older support turns into durable facts, open questions, policy constraints, and next actions before continuing the workflow.", "brightcart_example": {"durable_facts": ["Customer Maya Chen", "ORDER-8831", "replacement delayed", "carrier scan stale"], "policy_constraints": ["Do not promise refund without eligibility", "Offer expedited replacement or 15% concession after 48-hour delay with approval"], "next_action": "Check latest carrier scan and...</td>
    </tr>
    <tr>
      <td>Latency runtime example</td>
      <td>pass</td>
      <td>{"region_hint": "us-west-2", "base_url_host": "bedrock-mantle.us-west-2.api.aws", "sample_count": 3, "success_rate": 1.0, "completed_rate": 1.0, "avg_latency_seconds": 0.362, "p50_latency_seconds": 0.377, "p90_latency_seconds": 0.4, "total_output_tokens": 34, "total_tokens": 544}</td>
    </tr>
    <tr>
      <td>Throughput runtime example</td>
      <td>pass</td>
      <td>{"region_hint": "us-west-2", "base_url_host": "bedrock-mantle.us-west-2.api.aws", "sample_count": 3, "success_rate": 1.0, "completed_rate": 1.0, "avg_latency_seconds": 0.362, "p50_latency_seconds": 0.377, "p90_latency_seconds": 0.4, "total_output_tokens": 34, "total_tokens": 544}</td>
    </tr>
    <tr>
      <td>Reliability runtime example</td>
      <td>pass</td>
      <td>{"region_hint": "us-west-2", "base_url_host": "bedrock-mantle.us-west-2.api.aws", "sample_count": 3, "success_rate": 1.0, "completed_rate": 1.0, "avg_latency_seconds": 0.362, "p50_latency_seconds": 0.377, "p90_latency_seconds": 0.4, "total_output_tokens": 34, "total_tokens": 544}</td>
    </tr>
    <tr>
      <td>Region check</td>
      <td>pass</td>
      <td>{"region_hint": "us-west-2", "base_url_host": "bedrock-mantle.us-west-2.api.aws", "sample_count": 3, "success_rate": 1.0, "completed_rate": 1.0, "avg_latency_seconds": 0.362, "p50_latency_seconds": 0.377, "p90_latency_seconds": 0.4, "total_output_tokens": 34, "total_tokens": 544}</td>
    </tr>
    <tr>
      <td>Stored response cleanup</td>
      <td>warn</td>
      <td>[{"response_id": "resp_cvhvh7y5ghwrpa35snvk4bzgcgthgxp4tgwkllmf5mrhs7dikfia", "status": "warn", "detail": {"exception_class": "AuthenticationError", "status_code": 401, "retryable": false, "request_id": "req_gkni5zyr7lkjkz2vfiwvkev2qgxs76crcwz5whhjrdkma7up3yta", "message": "Error code: 401 - {'error': {'code': 'invalid_api_key', 'message': 'The security token included in the request is invalid.', 'param': None, 'type': 'permission_denied_error'}}"}}, {"response_id": "resp_vjrtvnakcgxjhnq5b7cj7rt...</td>
    </tr>
  </tbody>
</table>

<div style="font-weight:600; margin:8px 0 4px;">Example responses</div>

<table class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th>example</th>
      <th>response_type</th>
      <th>response</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Endpoint verification</td>
      <td>text</td>
      <td>ok</td>
    </tr>
    <tr>
      <td>First raw HTTPS request</td>
      <td>text</td>
      <td>Empathy: I’m sorry, Maya — your replacement order ORDER-8831 is delayed because the carrier reported a temporary transit hold at the regional sorting facility.\nAction: We’re monitoring the shipment closely and will send you an updated delivery estimate within 24 hours; if there’s no movement by then, we’ll review the next replacement or refund options with you.</td>
    </tr>
    <tr>
      <td>SDK text generation</td>
      <td>text</td>
      <td>Use the Responses API to build a BrightCart support assistant that can answer customer questions, summarize policies, and guide users through common workflows like order tracking, refunds, and account updates. Ground the assistant in BrightCart documentation and connect it to relevant backend tools or APIs so it can retrieve live order data, check account status, and provide accurate, context-aware support responses. Design the experience around clear system instructions, structured tool calling, and conversation state management so the assistant stays on-brand, reliable, and safe when handling customer issues.</td>
    </tr>
    <tr>
      <td>Create and retrieve response</td>
      <td>text</td>
      <td>goal: Help support agents explain delayed replacement orders, set expectations, and suggest next steps.\ndata needed: Order ID, replacement order status, shipment/tracking events, delay reason, estimated ship/delivery date, customer contact history, inventory/backorder status, and applicable refund or reship policy.\nhuman-review rule: Escalate to a human if the delay exceeds policy thresholds, tracking is inconsistent or missing, the order appears lost, the customer is high-risk or highly upset, or any refund/reship exception is requested.</td>
    </tr>
    <tr>
      <td>Service tier and prompt cache request</td>
      <td>text</td>
      <td>Latency benefit: Prompt caching lets the BrightCart support assistant reuse previously processed context, reducing response time for repeated or similar requests.\nConsistency benefit: Prompt caching helps the BrightCart support assistant return more uniform answers by reusing the same established prompt context across interactions.</td>
    </tr>
    <tr>
      <td>Structured ticket triage</td>
      <td>json</td>
      <td>{\n  "ticket_id": "TICKET-7429",\n  "category": "delivery_delay",\n  "priority": "urgent",\n  "customer_sentiment": "frustrated and time-sensitive",\n  "summary": "Customer Maya Chen reports that ORDER-8831 is a replacement shipment for a previously damaged standing desk. The replacement is now 2 days late, carrier tracking has not updated, and she needs the desk delivered before Monday. She is requesting a supervisor callback and wants to know refund options if the replacement cannot arrive in time.",\n  "required_actions": [\n    "Review ORDER-8831 shipment status and confirm last carrier scan/update.",\n    "Contact carrier or open a trace/escalation for stalled tracking.",\n    "Check expedited reshipment or alternative fulfillment options to meet the before-Monday deadline.",\n    "Arrange supervisor callback per customer request.",\n    "Review and communicate refund options, including refund\n...</td>
    </tr>
    <tr>
      <td>JSON support handoff</td>
      <td>json</td>
      <td>{\n  "customer_name": "Maya Chen",\n  "order_id": "ORDER-8831",\n  "issue_summary": "Customer is asking about a delayed replacement order. The carrier tracking scan is stale and has not updated.",\n  "next_step": "Handoff to support to investigate the carrier delay, verify shipment status, and provide Maya Chen with an update or resolution.",\n  "metrics_to_watch": [\n    "tracking_scan_recency",\n    "carrier_exception_status",\n    "replacement_order_delivery_eta",\n    "customer_follow_up_time"\n  ]\n}</td>
    </tr>
    <tr>
      <td>Compact policy guidance</td>
      <td>text</td>
      <td>BrightCart’s delayed-replacement policy lets customers keep using the original item until the replacement arrives, then return the defective product within the allowed return window.</td>
    </tr>
    <tr>
      <td>Detailed policy guidance</td>
      <td>text</td>
      <td>1. BrightCart sends replacements after customers return the original item and warehouse receipt is confirmed.\n2. This delay prevents duplicate shipments, verifies eligibility, and reduces fraud or inventory errors.\n3. Agents should explain timelines clearly, offer return instructions, and reassure customers once receipt is logged.</td>
    </tr>
    <tr>
      <td>Order-status tool answer</td>
      <td>text</td>
      <td>Status: ORDER-8831 is delayed; carrier shows no movement for 36 hours at the Denver sort center, with promised delivery on 2026-06-01.\nNext best action: Monitor until the 48-hour threshold; if no movement then, contact the customer and offer either an expedited replacement or a 15% concession with agent approval.</td>
    </tr>
    <tr>
      <td>Parallel order lookup fallback answer</td>
      <td>text</td>
      <td>Order statuses: ORDER-8831 is delayed and ORDER-2044 was delivered yesterday.\nShipping problems: Maya has one active shipping problem, because only ORDER-8831 is currently delayed while ORDER-2044 is already delivered.</td>
    </tr>
    <tr>
      <td>Normalized support note</td>
      <td>text</td>
      <td>ORDER_ID: ORDER-8831\nCUSTOMER_ID: CUST-1042\nISSUE: REPLACEMENT DELAYED\nCUSTOMER_REQUEST: CUSTOMER WANTS SUPERVISOR\nPOLICY_OPTION: OFFER EXPEDITED REPLACEMENT OR 15% CONCESSION</td>
    </tr>
    <tr>
      <td>Support transcript extraction text</td>
      <td>text</td>
      <td>{"ticket_id":"TICKET-7429","customer":"Maya Chen","order_id":"ORDER-8831","product":"Standing desk replacement","issue":"Replacement for a damaged item is delayed and carrier scan has not moved","requested_resolution":"Supervisor callback and refund options","policy_options":"expedited replacement or 15% concession with agent approval after 48-hour delay"}</td>
    </tr>
    <tr>
      <td>Stateful support handoff</td>
      <td>text</td>
      <td>Ticket ID: TICKET-4812\nOrder ID: ORDER-8831\nCustomer Name: Maya Chen\nIssue: Replacement standing desk shipment for damaged delivery has had no carrier movement for 36 hours; customer is frustrated because this is the second attempt\nNext Best Action: Monitor until 48 hours without movement, then offer expedited replacement or 15% concession and escalate to Tier 2 Returns if needed</td>
    </tr>
    <tr>
      <td>Stateless support handoff</td>
      <td>text</td>
      <td>Customer: Jordan Lee reported ORDER-7718 arrived with a cracked monitor stand.\nIssue: Damaged item; monitor stand is cracked on arrival.\nRequested Resolution: Customer wants a replacement shipped this week.\nOpen Question: Jordan asked whether the damaged item must be returned before replacement is sent.\nStatus: Damage claim captured and awaiting next-agent confirmation on replacement timing and return requirement.</td>
    </tr>
    <tr>
      <td>State strategy recommendation</td>
      <td>text</td>
      <td>Recommendation: Stateless continuation\nReason: In a regulated support workflow, requiring names, order IDs, and refund context to be explicitly provided each turn improves controllability, auditability, and data-minimization, reducing the risk of unintended retention or cross-session leakage.</td>
    </tr>
    <tr>
      <td>Prompt-cache token comparison</td>
      <td>table</td>
      <td>[\n  {\n    "request":"first",\n    "input_tokens":3970,\n    "cached_input_tokens":0,\n    "output_tokens":66,\n    "total_tokens":4036\n  },\n  {\n    "request":"second",\n    "input_tokens":3970,\n    "cached_input_tokens":0,\n    "output_tokens":48,\n    "total_tokens":4018\n  }\n]</td>
    </tr>
    <tr>
      <td>Cached support-policy reply</td>
      <td>text</td>
      <td>Hi Maya, I’m sorry your replacement order ORDER-8831 is delayed. I’m checking the latest replacement and carrier status now so I can confirm the best next step for you without making you wait longer than necessary.</td>
    </tr>
    <tr>
      <td>Background manager summary</td>
      <td>text</td>
      <td>theme: Shipping delays dominate, especially West Coast distribution lane.\nrisk: Rising dissatisfaction from delays, replacements, and return exceptions.\nnext action: Escalate West Coast lane issues and review holiday return policy.</td>
    </tr>
    <tr>
      <td>Compacted support context</td>
      <td>json</td>
      <td>{\n  "feature": "Compaction",\n  "how_to_apply": "Summarize older support turns into durable facts, open questions, policy constraints, and next actions before continuing the workflow.",\n  "brightcart_example": {\n    "durable_facts": [\n      "Customer Maya Chen",\n      "ORDER-8831",\n      "replacement delayed",\n      "carrier scan stale"\n    ],\n    "policy_constraints": [\n      "Do not promise refund without eligibility",\n      "Offer expedited replacement or 15% concession after 48-hour delay with approval"\n    ],\n    "next_action": "Check latest carrier scan and supervisor callback status."\n  }\n}</td>
    </tr>
    <tr>
      <td>Endpoint responsiveness summary</td>
      <td>json</td>
      <td>{\n  "region_hint": "us-west-2",\n  "base_url_host": "bedrock-mantle.us-west-2.api.aws",\n  "sample_count": 3,\n  "success_rate": 1.0,\n  "completed_rate": 1.0,\n  "avg_latency_seconds": 0.362,\n  "p50_latency_seconds": 0.377,\n  "p90_latency_seconds": 0.4,\n  "total_output_tokens": 34,\n  "total_tokens": 544,\n  "samples": [\n    {\n      "ok": true,\n      "latency_seconds": 0.4,\n      "output_tokens": 14,\n      "total_tokens": 184,\n      "status": "completed",\n      "sample_output": "We apologize for the delay with your replacement order."\n    },\n    {\n      "ok": true,\n      "latency_seconds": 0.31,\n      "output_tokens": 6,\n      "total_tokens": 174,\n      "status": "completed",\n      "sample_output": "Resolution Rate"\n    },\n    {\n      "ok": true,\n      "latency_seconds": 0.377,\n      "output_tokens": 14,\n      "total_tokens": 186,\n      "status": "completed",\n      "sample_output": "I\u2019m e\n...</td>
    </tr>
  </tbody>
</table>

<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>example</th>
      <th>response_type</th>
      <th>response</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Endpoint verification</td>
      <td>text</td>
      <td>ok</td>
    </tr>
    <tr>
      <th>1</th>
      <td>First raw HTTPS request</td>
      <td>text</td>
      <td>Empathy: I’m sorry, Maya — your replacement order ORDER-8831 is delayed because the carrier reported a temporary transit hold at the regional sorting facility.\nAction: We’re monitoring the shipment closely and will send you an updated delivery estimate within 24 hours; if there’s no movement by then, we’ll review the next replacement or refund options with you.</td>
    </tr>
    <tr>
      <th>2</th>
      <td>SDK text generation</td>
      <td>text</td>
      <td>Use the Responses API to build a BrightCart support assistant that can answer customer questions, summarize policies, and guide users through common workflows like order tracking, refunds, and account updates. Ground the assistant in BrightCart documentation and connect it to relevant backend tools or APIs so it can retrieve live order data, check account status, and provide accurate, context-aware support responses. Design the experience around clear system instructions, structured tool calling, and conversation state management so the assistant stays on-brand, reliable, and safe when handling customer issues.</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Create and retrieve response</td>
      <td>text</td>
      <td>goal: Help support agents explain delayed replacement orders, set expectations, and suggest next steps.\ndata needed: Order ID, replacement order status, shipment/tracking events, delay reason, estimated ship/delivery date, customer contact history, inventory/backorder status, and applicable refund or reship policy.\nhuman-review rule: Escalate to a human if the delay exceeds policy thresholds, tracking is inconsistent or missing, the order appears lost, the customer is high-risk or highly upset, or any refund/reship exception is requested.</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Service tier and prompt cache request</td>
      <td>text</td>
      <td>Latency benefit: Prompt caching lets the BrightCart support assistant reuse previously processed context, reducing response time for repeated or similar requests.\nConsistency benefit: Prompt caching helps the BrightCart support assistant return more uniform answers by reusing the same established prompt context across interactions.</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Structured ticket triage</td>
      <td>json</td>
      <td>{\n  "ticket_id": "TICKET-7429",\n  "category": "delivery_delay",\n  "priority": "urgent",\n  "customer_sentiment": "frustrated and time-sensitive",\n  "summary": "Customer Maya Chen reports that ORDER-8831 is a replacement shipment for a previously damaged standing desk. The replacement is now 2 days late, carrier tracking has not updated, and she needs the desk delivered before Monday. She is requesting a supervisor callback and wants to know refund options if the replacement cannot arrive in time.",\n  "required_actions": [\n    "Review ORDER-8831 shipment status and confirm last carrier scan/update.",\n    "Contact carrier or open a trace/escalation for stalled tracking.",\n    "Check expedited reshipment or alternative fulfillment options to meet the before-Monday deadline.",\n    "Arrange supervisor callback per customer request.",\n    "Review and communicate refund options, including refund\n...</td>
    </tr>
    <tr>
      <th>6</th>
      <td>JSON support handoff</td>
      <td>json</td>
      <td>{\n  "customer_name": "Maya Chen",\n  "order_id": "ORDER-8831",\n  "issue_summary": "Customer is asking about a delayed replacement order. The carrier tracking scan is stale and has not updated.",\n  "next_step": "Handoff to support to investigate the carrier delay, verify shipment status, and provide Maya Chen with an update or resolution.",\n  "metrics_to_watch": [\n    "tracking_scan_recency",\n    "carrier_exception_status",\n    "replacement_order_delivery_eta",\n    "customer_follow_up_time"\n  ]\n}</td>
    </tr>
    <tr>
      <th>7</th>
      <td>Compact policy guidance</td>
      <td>text</td>
      <td>BrightCart’s delayed-replacement policy lets customers keep using the original item until the replacement arrives, then return the defective product within the allowed return window.</td>
    </tr>
    <tr>
      <th>8</th>
      <td>Detailed policy guidance</td>
      <td>text</td>
      <td>1. BrightCart sends replacements after customers return the original item and warehouse receipt is confirmed.\n2. This delay prevents duplicate shipments, verifies eligibility, and reduces fraud or inventory errors.\n3. Agents should explain timelines clearly, offer return instructions, and reassure customers once receipt is logged.</td>
    </tr>
    <tr>
      <th>9</th>
      <td>Order-status tool answer</td>
      <td>text</td>
      <td>Status: ORDER-8831 is delayed; carrier shows no movement for 36 hours at the Denver sort center, with promised delivery on 2026-06-01.\nNext best action: Monitor until the 48-hour threshold; if no movement then, contact the customer and offer either an expedited replacement or a 15% concession with agent approval.</td>
    </tr>
    <tr>
      <th>10</th>
      <td>Parallel order lookup fallback answer</td>
      <td>text</td>
      <td>Order statuses: ORDER-8831 is delayed and ORDER-2044 was delivered yesterday.\nShipping problems: Maya has one active shipping problem, because only ORDER-8831 is currently delayed while ORDER-2044 is already delivered.</td>
    </tr>
    <tr>
      <th>11</th>
      <td>Normalized support note</td>
      <td>text</td>
      <td>ORDER_ID: ORDER-8831\nCUSTOMER_ID: CUST-1042\nISSUE: REPLACEMENT DELAYED\nCUSTOMER_REQUEST: CUSTOMER WANTS SUPERVISOR\nPOLICY_OPTION: OFFER EXPEDITED REPLACEMENT OR 15% CONCESSION</td>
    </tr>
    <tr>
      <th>12</th>
      <td>Support transcript extraction text</td>
      <td>text</td>
      <td>{"ticket_id":"TICKET-7429","customer":"Maya Chen","order_id":"ORDER-8831","product":"Standing desk replacement","issue":"Replacement for a damaged item is delayed and carrier scan has not moved","requested_resolution":"Supervisor callback and refund options","policy_options":"expedited replacement or 15% concession with agent approval after 48-hour delay"}</td>
    </tr>
    <tr>
      <th>13</th>
      <td>Stateful support handoff</td>
      <td>text</td>
      <td>Ticket ID: TICKET-4812\nOrder ID: ORDER-8831\nCustomer Name: Maya Chen\nIssue: Replacement standing desk shipment for damaged delivery has had no carrier movement for 36 hours; customer is frustrated because this is the second attempt\nNext Best Action: Monitor until 48 hours without movement, then offer expedited replacement or 15% concession and escalate to Tier 2 Returns if needed</td>
    </tr>
    <tr>
      <th>14</th>
      <td>Stateless support handoff</td>
      <td>text</td>
      <td>Customer: Jordan Lee reported ORDER-7718 arrived with a cracked monitor stand.\nIssue: Damaged item; monitor stand is cracked on arrival.\nRequested Resolution: Customer wants a replacement shipped this week.\nOpen Question: Jordan asked whether the damaged item must be returned before replacement is sent.\nStatus: Damage claim captured and awaiting next-agent confirmation on replacement timing and return requirement.</td>
    </tr>
    <tr>
      <th>15</th>
      <td>State strategy recommendation</td>
      <td>text</td>
      <td>Recommendation: Stateless continuation\nReason: In a regulated support workflow, requiring names, order IDs, and refund context to be explicitly provided each turn improves controllability, auditability, and data-minimization, reducing the risk of unintended retention or cross-session leakage.</td>
    </tr>
    <tr>
      <th>16</th>
      <td>Prompt-cache token comparison</td>
      <td>table</td>
      <td>[\n  {\n    "request":"first",\n    "input_tokens":3970,\n    "cached_input_tokens":0,\n    "output_tokens":66,\n    "total_tokens":4036\n  },\n  {\n    "request":"second",\n    "input_tokens":3970,\n    "cached_input_tokens":0,\n    "output_tokens":48,\n    "total_tokens":4018\n  }\n]</td>
    </tr>
    <tr>
      <th>17</th>
      <td>Cached support-policy reply</td>
      <td>text</td>
      <td>Hi Maya, I’m sorry your replacement order ORDER-8831 is delayed. I’m checking the latest replacement and carrier status now so I can confirm the best next step for you without making you wait longer than necessary.</td>
    </tr>
    <tr>
      <th>18</th>
      <td>Background manager summary</td>
      <td>text</td>
      <td>theme: Shipping delays dominate, especially West Coast distribution lane.\nrisk: Rising dissatisfaction from delays, replacements, and return exceptions.\nnext action: Escalate West Coast lane issues and review holiday return policy.</td>
    </tr>
    <tr>
      <th>19</th>
      <td>Compacted support context</td>
      <td>json</td>
      <td>{\n  "feature": "Compaction",\n  "how_to_apply": "Summarize older support turns into durable facts, open questions, policy constraints, and next actions before continuing the workflow.",\n  "brightcart_example": {\n    "durable_facts": [\n      "Customer Maya Chen",\n      "ORDER-8831",\n      "replacement delayed",\n      "carrier scan stale"\n    ],\n    "policy_constraints": [\n      "Do not promise refund without eligibility",\n      "Offer expedited replacement or 15% concession after 48-hour delay with approval"\n    ],\n    "next_action": "Check latest carrier scan and supervisor callback status."\n  }\n}</td>
    </tr>
    <tr>
      <th>20</th>
      <td>Endpoint responsiveness summary</td>
      <td>json</td>
      <td>{\n  "region_hint": "us-west-2",\n  "base_url_host": "bedrock-mantle.us-west-2.api.aws",\n  "sample_count": 3,\n  "success_rate": 1.0,\n  "completed_rate": 1.0,\n  "avg_latency_seconds": 0.362,\n  "p50_latency_seconds": 0.377,\n  "p90_latency_seconds": 0.4,\n  "total_output_tokens": 34,\n  "total_tokens": 544,\n  "samples": [\n    {\n      "ok": true,\n      "latency_seconds": 0.4,\n      "output_tokens": 14,\n      "total_tokens": 184,\n      "status": "completed",\n      "sample_output": "We apologize for the delay with your replacement order."\n    },\n    {\n      "ok": true,\n      "latency_seconds": 0.31,\n      "output_tokens": 6,\n      "total_tokens": 174,\n      "status": "completed",\n      "sample_output": "Resolution Rate"\n    },\n    {\n      "ok": true,\n      "latency_seconds": 0.377,\n      "output_tokens": 14,\n      "total_tokens": 186,\n      "status": "completed",\n      "sample_output": "I\u2019m e\n...</td>
    </tr>
  </tbody>
</table>
</div>