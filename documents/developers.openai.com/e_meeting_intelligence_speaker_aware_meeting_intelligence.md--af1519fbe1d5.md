# Build a Speaker-Aware Meeting Intelligence Pipeline with Audio Diarization

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Many organizations already record important conversations, but a plain transcript often is not enough for reliable follow-up. The missing layer is speaker attribution: knowing who raised a concern, who made a commitment, and where the evidence appears in the recording. A speaker-aware transcript lets you separate customer needs from seller follow-up, keep structured evidence references next to action items, and route sensitive commitments into a review workflow before they land in a CRM, ticketing system, or knowledge base.

This pattern is useful whenever the downstream workflow depends on who said what:

- Sales discovery and solution consulting: capture customer requirements, seller commitments, decision criteria, blockers, and next steps with evidence.
- Customer success and account management: turn QBRs, renewal calls, and onboarding sessions into sourced risks, product asks, and follow-up plans.
- Support escalations and incident reviews: preserve the timeline, reported symptoms, owner commitments, and unresolved questions before creating tickets or postmortems.
- Recruiting and interview loops: summarize candidate or interviewer feedback while keeping quotes tied to the right speaker.
- Regulated or high-stakes reviews: add redaction, evidence checks, and human review before storing notes from healthcare, financial services, legal, or compliance-heavy conversations.

For revenue teams, the impact is usually less about generating another summary and more about reducing leakage between the conversation and the system of record. A pipeline like this can help teams capture CRM-ready next steps faster, identify renewal or expansion risks earlier, preserve evidence behind forecast updates, and coach reps or support teams from sourced examples instead of anecdotal notes. The goal is not to automate judgment away; it is to make handoffs, reviews, and follow-up actions more complete and auditable.

This notebook shows how to build a production-style, post-call meeting intelligence pipeline with OpenAI audio diarization. You will:

1. Accept a recorded meeting audio file.
2. Optionally map known speakers using short reference clips.
3. Call `gpt-4o-transcribe-diarize` with `response_format="diarized_json"`.
4. Normalize the speaker-labeled segments into JSON and Markdown with stable segment IDs.
5. Use structured outputs to extract a meeting brief, decisions, risks, explicit questions, suggested follow-ups, action items, evidence references, and a follow-up email draft.
6. Write reviewable artifacts and a local guardrail report.

The default cells run without an API key using a synthetic diarized transcript. Real audio calls are opt-in so the notebook is safe to review top-to-bottom.


## Architecture

![Architecture diagram](https://developers.openai.com/cookbook/assets/examples/audio/speaker_aware_meeting_intelligence/images/architecture.svg)

| Layer | Responsibility | Output |
| --- | --- | --- |
| Audio intake | Accept a call recording and optional known-speaker clips. | `meeting.wav`, `Agent=agent.wav` |
| Pipeline runner | Validate inputs, encode references as data URLs, call OpenAI, and write artifacts. | Run metadata and output directory |
| Diarization | Call `gpt-4o-transcribe-diarize` with `response_format="diarized_json"` and `chunking_strategy="auto"`. | Speaker-labeled segments |
| Transcript normalization | Convert API output into consistent JSON and Markdown with stable segment IDs. | `transcript_segments.json`, `speaker_labeled_transcript.md` |
| Meeting intelligence | Extract summary, decisions, actions, risks, explicit questions, suggested follow-ups, quotes, and follow-up email with structured evidence references. | `meeting_intelligence.json`, `meeting_brief.md` |
| Guardrails and review gate | Redact sensitive fields, verify evidence references, optionally moderate content, and route risky outputs for review. | `guardrail_report.json` |

This is intentionally request-based. The Realtime API is a better fit for live voice UX, browser capture, or telephony streaming. For durable post-call diarization, this pattern uses the Transcriptions API and then runs structured extraction over the speaker-labeled transcript.


## Why speaker-aware transcripts matter

The first version of meeting intelligence is often "send a transcript to a model and summarize it." That works for demos, but it breaks down in customer workflows because it loses who said what. A customer may state a requirement, a seller may make a commitment, and a manager may need the difference to be explicit.

Speaker-aware diarization gives the rest of the application better structure:

- Action items can include the speaker who committed to them.
- Risks can quote the exact customer concern.
- Follow-up email drafts can avoid attributing seller commitments to the customer.
- QA reviewers can spot-check speaker attribution by segment ID and timestamp.
- CRM sync jobs can store mechanically verifiable evidence rather than opaque summaries.


## Security and guardrails

Meeting intelligence should be treated as a sensitive-data workflow, not just a transcription or summarization task. Raw recordings can contain customer names, commercial terms, support details, health or financial information, and internal strategy. Speaker reference clips can also be sensitive because they are tied to a person's voice. Once the pipeline turns that audio into structured outputs, those outputs may flow into CRM records, support tickets, account plans, dashboards, or review queues.

Security and guardrails matter most when the output can influence a business process. A sales call summary may capture pricing or contractual commitments. A support escalation may include production-impacting incidents or customer credentials. A recruiting debrief may include candidate feedback. A regulated-industry meeting may contain data that needs retention, access-control, or redaction policies. For these workflows, the safest pattern is to minimize raw audio retention, redact sensitive content where appropriate, require evidence-backed outputs, and route risky or low-confidence outputs through human review before downstream writes.

The included regex redaction is intentionally illustrative: it masks basic email and phone patterns only. It is not a complete PII or DLP system. For names, addresses, account identifiers, credentials, health data, financial data, or regulated workflows, use a policy-approved PII/DLP detector and keep a human review gate before downstream writes.

For the structured extraction step, this notebook sets `store=False` on the Responses API call so the generated meeting intelligence response is not stored as application state. `store=False` is a useful request-level control, but it is not the same as enabling Zero Data Retention for an organization or project. If your workflow requires stricter retention guarantees, review OpenAI's [data controls documentation](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint) and confirm the right retention configuration for your use case.

| Risk | Guardrail |
| --- | --- |
| Recording or speaker-reference misuse | Require consent and policy approval before recording, diarization, or reference-clip use. Treat speaker references as sensitive biometric-adjacent data. |
| Over-retention of raw audio | Do not save the raw transcription response by default. Keep raw audio and reference clips only as long as needed. Encrypt and restrict access if retained. |
| Prompt injection inside transcripts | Treat transcript text as untrusted evidence. Keep instructions in the system message and require the model to use only transcript-backed facts. |
| Unsupported action items or decisions | Use strict structured outputs and require evidence references that point to real segment IDs and quotes. |
| Sensitive content in generated notes | Run redaction before summarization where possible, then run post-generation checks on the transcript and brief. |
| Harmful or policy-sensitive content | Optionally call the Moderation API with `omni-moderation-latest` on transcript text and generated brief text. Moderation detects harmful content; it is not a replacement for privacy review. |
| Unsafe downstream writes | Do not write directly to CRM, ticketing, or analytics systems from the model output. Put a human review gate in front of medium/high risks, missing evidence, moderation flags, or raw-response retention. |
| Silent quality drift | Log model versions, prompt versions, schema versions, audio duration, redaction state, moderation state, and reviewer decisions. Sample calls for evals. |


## Prerequisites

- Python 3.10 or later.
- An OpenAI API key in `OPENAI_API_KEY` for real audio runs.
- A meeting recording in a supported audio format for real audio runs.
- Audio uploads must be 25 MB or smaller. Supported input formats are `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav`, and `webm`.
- Optional: up to four short, single-speaker reference clips. The speech-to-text guide recommends 2-10 second references, encoded as data URLs when sent with multipart form data.

### Run the notebook locally

From a local clone of the Cookbook repository, create a virtual environment, install Jupyter and the OpenAI SDK, then launch this notebook:

```bash
git clone https://github.com/openai/openai-cookbook.git
cd openai-cookbook
python3 -m venv .venv
source .venv/bin/activate
python -m pip install jupyter "openai>=1.93.0"
export OPENAI_API_KEY="your-api-key"
jupyter notebook examples/audio/speaker_aware_meeting_intelligence/speaker_aware_meeting_intelligence.ipynb
```

The synthetic demo below uses only the Python standard library and does not call the API. For real audio, you can also install the OpenAI SDK from inside an existing notebook environment:

```python
%pip install "openai>=1.93.0"
```


## Core diarization request

The core API request is intentionally small:

```python
client = OpenAI(timeout=30 * 60)

with open("meeting.wav", "rb") as audio_file:
    stream = client.audio.transcriptions.create(
        model="gpt-4o-transcribe-diarize",
        file=audio_file,
        response_format="diarized_json",
        chunking_strategy="auto",
        stream=True,
        extra_body={
            "known_speaker_names": ["Agent"],
            "known_speaker_references": [to_data_url(Path("agent_reference.wav"))],
        },
    )
    for event in stream:
        if event.type == "transcript.text.segment":
            print(event.speaker, event.text, event.start, event.end)
```

The important details are:

- Use `response_format="diarized_json"` when you need segment-level speaker metadata.
- Use `chunking_strategy="auto"` for audio longer than 30 seconds.
- Use `stream=True` for completed recordings when you want finalized diarized segments as they become available.
- The Python SDK defaults to a 10-minute read timeout; the helper below uses 30 minutes for longer recordings.
- Pass known speaker names and references together, in the same order.
- Keep reference clips short and single-speaker.


## Diarization vs speaker identification

Diarization answers "which voice spoke each segment?" It separates voices inside one recording, but it does not create a permanent identity profile or remember that `speaker_0` from one call is the same person as `speaker_0` in a later call. Without references, generic labels are still useful because they preserve attribution: the pipeline can distinguish the speaker who raised a requirement from the speaker who made a commitment.

Known-speaker references add an optional identity hint for the current request:

| Input | Result |
| --- | --- |
| Meeting audio only | The model separates voices, usually with generic labels such as `speaker_0` and `speaker_1`. |
| Meeting audio plus a named reference clip | Matching segments can use the supplied name; unmatched speakers can remain generic. |
| A later or historical recording | Pass the reference clip again. Labels do not carry across recordings automatically. |

### Pass a reference clip with the meeting recording

The meeting recording and the reference clip are separate inputs in one transcription request. Do not concatenate the reference clip onto the meeting audio. The meeting is uploaded as `file=...`; each reference clip is encoded as a data URL and sent through `known_speaker_references` with a name in the same position in `known_speaker_names`.

The helper below wraps that request shape. For example, this passes a meeting recording plus a separate short clip of an internal rep speaking:

```python
meeting_audio = Path("customer_call.wav")
known_speakers = [
    ("Internal rep", Path("internal_rep_reference.wav")),
]

raw_transcription = transcribe_with_diarization(
    audio_file=meeting_audio,
    known_speakers=known_speakers,
)
```

Use a clean, consented 2-10 second clip with one speaker and minimal background noise. For recurring internal speakers, a production application can keep an access-controlled reference registry and attach the appropriate clip on each request. For historical recordings, run the same flow per recording; a reference clip may come from an older consented call if it is clean and single-speaker. Treat references as sensitive data, evaluate match quality on representative audio, and keep human review for high-stakes downstream writes.


```python
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from IPython.display import JSON, Markdown, display
except ImportError:  # Makes this cell safe in non-notebook runners.
    JSON = None
    Markdown = None

    def display(value):
        print(value)


def show_markdown(text: str) -> None:
    if Markdown:
        display(Markdown(text))
    else:
        print(text)


def show_json(payload: Any, expanded: bool = False) -> None:
    if JSON:
        display(JSON(payload, expanded=expanded))
    else:
        print(json.dumps(payload, indent=2))


DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_SUMMARY_MODEL = os.getenv("OPENAI_MEETING_INTELLIGENCE_MODEL", "gpt-4.1-mini")
DEFAULT_MODERATION_MODEL = "omni-moderation-latest"
SUPPORTED_REFERENCE_MIME_PREFIXES = ("audio/", "video/")
MAX_AUDIO_UPLOAD_BYTES = 25_000_000
DEFAULT_TRANSCRIPTION_TIMEOUT_SECONDS = 30 * 60

print("Notebook helpers loaded")
```

```python
@dataclass(frozen=True)
class Segment:
    segment_id: str
    speaker: str
    start: float
    end: float
    text: str


DEMO_SEGMENTS = [
    Segment(
        segment_id="seg_001",
        speaker="Solutions Engineer",
        start=0.0,
        end=9.2,
        text="Thanks for joining. I would like to understand where your support handoff breaks down today.",
    ),
    Segment(
        segment_id="seg_002",
        speaker="Customer",
        start=9.3,
        end=22.4,
        text="The biggest issue is that escalation notes are inconsistent. Managers spend Monday morning reconstructing what happened from call recordings.",
    ),
    Segment(
        segment_id="seg_003",
        speaker="Solutions Engineer",
        start=22.5,
        end=38.1,
        text="So the priority is reliable call summaries, who committed to what, and enough evidence that the team trusts the handoff.",
    ),
    Segment(
        segment_id="seg_004",
        speaker="Customer",
        start=38.2,
        end=55.0,
        text="Exactly. We also need risks called out, especially compliance-sensitive promises, and we need to push action items into our CRM.",
    ),
    Segment(
        segment_id="seg_005",
        speaker="Solutions Engineer",
        start=55.1,
        end=70.3,
        text="I will send a prototype that includes speaker-aware transcripts, action items with evidence, and a redaction pass before CRM sync.",
    ),
]


PII_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[email]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"), "[phone]"),
]

print(f"Loaded {len(DEMO_SEGMENTS)} synthetic transcript segments")
```

## Step 1: Define the structured output schema

Meeting intelligence often feeds systems of record. Use strict structured outputs so downstream code gets a stable shape and unsupported fields are rejected rather than silently accepted. This schema also requires structured `evidence_refs`: each extracted item must cite a transcript `segment_id` and a quote from that segment, which lets guardrails verify the grounding mechanically.


```python
EVIDENCE_REF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "segment_id": {"type": "string"},
        "quote": {"type": "string"},
    },
    "required": ["segment_id", "quote"],
}

EVIDENCE_REFS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": EVIDENCE_REF_SCHEMA,
}

NULLABLE_STRING_SCHEMA: dict[str, Any] = {"type": ["string", "null"]}


MEETING_INTELLIGENCE_SCHEMA: dict[str, Any] = {
    "name": "meeting_intelligence",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "participants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "speaker": {"type": "string"},
                        "inferred_role": NULLABLE_STRING_SCHEMA,
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                    },
                    "required": ["speaker", "inferred_role", "evidence_refs"],
                },
            },
            "customer_context": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "fact": {"type": "string"},
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                    },
                    "required": ["fact", "evidence_refs"],
                },
            },
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "decision": {"type": "string"},
                        "speaker_or_group": NULLABLE_STRING_SCHEMA,
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                    },
                    "required": ["decision", "speaker_or_group", "evidence_refs"],
                },
            },
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "owner_speaker": NULLABLE_STRING_SCHEMA,
                        "task": {"type": "string"},
                        "due_date_or_trigger": NULLABLE_STRING_SCHEMA,
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                    },
                    "required": ["owner_speaker", "task", "due_date_or_trigger", "evidence_refs"],
                },
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "risk": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                        "mitigation": {"type": "string"},
                    },
                    "required": ["risk", "severity", "evidence_refs", "mitigation"],
                },
            },
            "explicit_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "question": {"type": "string"},
                        "asked_by_speaker": {"type": "string"},
                        "directed_to_speaker": NULLABLE_STRING_SCHEMA,
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                    },
                    "required": ["question", "asked_by_speaker", "directed_to_speaker", "evidence_refs"],
                },
            },
            "suggested_follow_ups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "question": {"type": "string"},
                        "rationale": {"type": "string"},
                        "evidence_refs": EVIDENCE_REFS_SCHEMA,
                    },
                    "required": ["question", "rationale", "evidence_refs"],
                },
            },
            "notable_quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "speaker": {"type": "string"},
                        "quote": {"type": "string"},
                        "timestamp": {"type": "string"},
                        "segment_id": {"type": "string"},
                    },
                    "required": ["speaker", "quote", "timestamp", "segment_id"],
                },
            },
            "follow_up_email": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["subject", "body"],
            },
        },
        "required": [
            "summary",
            "participants",
            "customer_context",
            "decisions",
            "action_items",
            "risks",
            "explicit_questions",
            "suggested_follow_ups",
            "notable_quotes",
            "follow_up_email",
        ],
    },
}

print("Structured output schema ready")
```

## Step 2: Build audio and transcript helpers

Known-speaker references are optional. Without them, diarization can still separate speakers, but labels may be generic, such as `speaker_0` or `speaker_1`. With references, the API can map segments to the names you provide.

Use short, clean reference clips with one speaker and minimal background noise. Keep reference clips only when you have consent and a clear business need.


```python
def to_data_url(path) -> str:
    path = Path(path)
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "audio/wav"
    elif not mime_type.startswith(SUPPORTED_REFERENCE_MIME_PREFIXES):
        raise ValueError(f"Reference clip must be an audio or video file, got {mime_type}: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def transcribe_with_diarization(
    audio_file: Path,
    known_speakers: list[tuple[str, Path]],
    model: str = DEFAULT_TRANSCRIPTION_MODEL,
    request_timeout_seconds: float = DEFAULT_TRANSCRIPTION_TIMEOUT_SECONDS,
    stream_transcription: bool = True,
) -> Any:
    if not audio_file.is_file():
        raise FileNotFoundError(f"Audio file does not exist or is not a regular file: {audio_file}")

    if request_timeout_seconds <= 0:
        raise ValueError("request_timeout_seconds must be positive.")

    audio_size_bytes = audio_file.stat().st_size
    if audio_size_bytes > MAX_AUDIO_UPLOAD_BYTES:
        raise ValueError(
            f"Audio file is {audio_size_bytes:,} bytes; "
            "the Audio Transcriptions API accepts uploads up to 25 MB. "
            "Compress or split the recording before retrying."
        )

    from openai import OpenAI

    client = OpenAI(timeout=request_timeout_seconds)
    params: dict[str, Any] = {
        "model": model,
        "response_format": "diarized_json",
        "chunking_strategy": "auto",
        "stream": stream_transcription,
    }

    if known_speakers:
        if len(known_speakers) > 4:
            raise ValueError("gpt-4o-transcribe-diarize accepts up to 4 known speaker references.")
        params["extra_body"] = {
            "known_speaker_names": [name for name, _ in known_speakers],
            "known_speaker_references": [to_data_url(path) for _, path in known_speakers],
        }

    with audio_file.open("rb") as audio:
        response = client.audio.transcriptions.create(file=audio, **params)
        if stream_transcription:
            return collect_streamed_transcription(response)
        return response


def to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: to_plain(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    return value


def collect_streamed_transcription(events: Any) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    full_text = ""
    usage: Any = None

    for event in events:
        data = to_plain(event)
        if not isinstance(data, dict):
            continue

        event_type = data.get("type")
        if event_type == "transcript.text.segment":
            segments.append(data)
        elif event_type == "transcript.text.done":
            full_text = str(data.get("text") or "")
            usage = data.get("usage")

    if not segments:
        raise ValueError("No diarized transcript segments were emitted by the transcription stream.")
    return {"segments": segments, "text": full_text, "usage": usage}


def normalize_segments(transcription: Any) -> list[Segment]:
    data = to_plain(transcription)
    raw_segments = data.get("segments", []) if isinstance(data, dict) else []
    segments: list[Segment] = []

    for index, item in enumerate(raw_segments):
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue

        text = str(item.get("text", "")).strip()
        if not text:
            continue

        segment_id = str(item.get("segment_id") or item.get("id") or f"seg_{len(segments) + 1:03d}")
        segments.append(
            Segment(
                segment_id=segment_id,
                speaker=str(item.get("speaker") or f"Speaker {index + 1}"),
                start=float(item.get("start") or 0.0),
                end=float(item.get("end") or 0.0),
                text=text,
            )
        )

    if not segments and isinstance(data, dict) and data.get("text"):
        segments.append(Segment(segment_id="seg_001", speaker="Speaker 1", start=0.0, end=0.0, text=str(data["text"])))

    if not segments:
        raise ValueError("No transcript segments were found in the transcription response.")
    return segments

print("Audio and transcript helpers ready")
```

## Step 3: Normalize the transcript

The normalized transcript is the contract between audio processing and meeting intelligence. It helps you rerun summarization without retranscribing audio, inspect attribution quality, and keep raw audio retention short.

Each segment gets a stable `segment_id` such as `seg_005`. Later, the model must cite those IDs in `evidence_refs`, and the guardrail step verifies that each cited quote appears in the referenced segment.

The regex redaction helper below is intentionally illustrative: it masks basic email and phone patterns only. It is not a complete PII or DLP system; use a policy-approved detector and human review for sensitive or regulated workflows.


```python
def redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_segments(segments: list[Segment]) -> list[Segment]:
    return [
        Segment(
            segment_id=segment.segment_id,
            speaker=segment.speaker,
            start=segment.start,
            end=segment.end,
            text=redact_text(segment.text),
        )
        for segment in segments
    ]


def pii_matches(text: str) -> list[str]:
    matches: list[str] = []
    for pattern, replacement in PII_PATTERNS:
        if pattern.search(text):
            matches.append(replacement.strip("[]"))
    return sorted(set(matches))


def format_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    minutes, remainder_ms = divmod(total_ms, 60_000)
    secs, millis = divmod(remainder_ms, 1000)
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def transcript_as_markdown(segments: list[Segment]) -> str:
    lines = ["# Speaker-Labeled Transcript", ""]
    for segment in segments:
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        lines.append(f"**{segment.segment_id} | {segment.speaker} [{start}-{end}]**: {segment.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def transcript_for_model(segments: list[Segment]) -> str:
    return "\n".join(
        f"{segment.segment_id} | {segment.speaker} | {format_timestamp(segment.start)}-{format_timestamp(segment.end)} | {segment.text}"
        for segment in segments
    )


show_markdown(transcript_as_markdown(DEMO_SEGMENTS))
```

## Step 4: Extract structured meeting intelligence

The model gets a speaker-labeled transcript and must use only that transcript as evidence. The safest default is to produce empty arrays instead of plausible but unsupported CRM notes. The schema also uses required-but-nullable fields, such as `due_date_or_trigger`, `inferred_role`, and `directed_to_speaker`, so unknown values stay `null` instead of being filled with guesses.

For every extracted fact, action item, risk, question, or recommendation, the model returns `evidence_refs` with a `segment_id` and quote. This gives reviewers a readable source trail and gives code something concrete to validate.


```python
def response_output_text_or_raise(response: Any) -> str:
    data = to_plain(response)
    status = data.get("status") if isinstance(data, dict) else getattr(response, "status", None)
    if status and status != "completed":
        details = data.get("incomplete_details") if isinstance(data, dict) else getattr(response, "incomplete_details", None)
        raise RuntimeError(f"Responses API returned status={status!r}; incomplete_details={details!r}")

    refusals: list[str] = []
    if isinstance(data, dict):
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "refusal" or content.get("refusal"):
                    refusals.append(str(content.get("refusal") or content.get("text") or content))
    if refusals:
        raise RuntimeError(f"Responses API returned a refusal: {refusals[0]}")

    content = getattr(response, "output_text", None)
    if content is None and isinstance(data, dict):
        content = data.get("output_text")
    content = str(content or "").strip()
    if not content:
        raise RuntimeError("The model returned an empty response.")
    return content


def parse_meeting_intelligence_json(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Responses API returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Responses API returned JSON, but the top-level value was not an object.")
    return parsed


def generate_meeting_intelligence(segments: list[Segment], model: str = DEFAULT_SUMMARY_MODEL) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    transcript = transcript_for_model(segments)

    completion = client.responses.create(
        model=model,
        temperature=0,
        store=False,
        input=[
            {
                "role": "system",
                "content": (
                    "You create meeting intelligence from speaker-labeled transcripts. "
                    "Use only the transcript as evidence. Do not invent names, dates, decisions, "
                    "commitments, or implementation details. If evidence is missing, leave the relevant array empty. "
                    "Use null for unknown roles, owners, due dates or triggers, directed-to speakers, or decision owners. "
                    "Put single-speaker commitments in action_items, not decisions. "
                    "Only include decisions when the transcript shows an explicit decision or agreement. "
                    "Put only questions actually asked in explicit_questions. "
                    "Put inferred next questions in suggested_follow_ups with rationale and evidence_refs. "
                    "Every extracted item must include evidence_refs with segment_id values copied from the transcript "
                    "and quote text copied from that same segment. Do not fabricate segment IDs or quotes. "
                    "Use empty arrays instead of unsupported items. "
                    "If the follow-up email signer is unknown, end with [Your name]."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract a customer-safe meeting brief from this transcript. "
                    "Transcript rows use: segment_id | speaker | timestamp range | text.\n\n"
                    f"{transcript}"
                ),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": MEETING_INTELLIGENCE_SCHEMA["name"],
                "strict": MEETING_INTELLIGENCE_SCHEMA["strict"],
                "schema": MEETING_INTELLIGENCE_SCHEMA["schema"],
            }
        },
    )

    content = response_output_text_or_raise(completion)
    return parse_meeting_intelligence_json(content)


def demo_meeting_intelligence() -> dict[str, Any]:
    return {
        "summary": (
            "The customer needs a dependable post-call handoff process. Their main pain point is "
            "inconsistent escalation notes, which forces managers to reconstruct calls manually. "
            "The proposed path is a speaker-aware transcript, evidence-backed action items, risk "
            "detection, redaction, and CRM sync."
        ),
        "participants": [
            {
                "speaker": "Solutions Engineer",
                "inferred_role": "OpenAI technical seller or solution owner",
                "evidence_refs": [
                    {
                        "segment_id": "seg_001",
                        "quote": "I would like to understand where your support handoff breaks down today.",
                    },
                    {
                        "segment_id": "seg_005",
                        "quote": "I will send a prototype that includes speaker-aware transcripts, action items with evidence, and a redaction pass before CRM sync.",
                    },
                ],
            },
            {
                "speaker": "Customer",
                "inferred_role": "Customer stakeholder for support operations",
                "evidence_refs": [
                    {
                        "segment_id": "seg_002",
                        "quote": "The biggest issue is that escalation notes are inconsistent.",
                    },
                    {
                        "segment_id": "seg_004",
                        "quote": "we need to push action items into our CRM.",
                    },
                ],
            },
        ],
        "customer_context": [
            {
                "fact": "Escalation notes are inconsistent today.",
                "evidence_refs": [
                    {
                        "segment_id": "seg_002",
                        "quote": "The biggest issue is that escalation notes are inconsistent.",
                    }
                ],
            },
            {
                "fact": "Managers spend time reconstructing calls from recordings.",
                "evidence_refs": [
                    {
                        "segment_id": "seg_002",
                        "quote": "Managers spend Monday morning reconstructing what happened from call recordings.",
                    }
                ],
            },
            {
                "fact": "The customer wants action items pushed into their CRM.",
                "evidence_refs": [{"segment_id": "seg_004", "quote": "we need to push action items into our CRM."}],
            },
        ],
        "decisions": [],
        "action_items": [
            {
                "owner_speaker": "Solutions Engineer",
                "task": "Send a prototype that includes speaker-aware transcripts, action items with evidence, and a redaction pass before CRM sync.",
                "due_date_or_trigger": None,
                "evidence_refs": [
                    {
                        "segment_id": "seg_005",
                        "quote": "I will send a prototype that includes speaker-aware transcripts, action items with evidence, and a redaction pass before CRM sync.",
                    }
                ],
            }
        ],
        "risks": [
            {
                "risk": "Compliance-sensitive promises need to be identified in meeting notes.",
                "severity": "medium",
                "evidence_refs": [
                    {
                        "segment_id": "seg_004",
                        "quote": "We also need risks called out, especially compliance-sensitive promises",
                    }
                ],
                "mitigation": "Route compliance-sensitive risks to human review before CRM sync.",
            }
        ],
        "explicit_questions": [
            {
                "question": "Where does your support handoff break down today?",
                "asked_by_speaker": "Solutions Engineer",
                "directed_to_speaker": "Customer",
                "evidence_refs": [
                    {
                        "segment_id": "seg_001",
                        "quote": "I would like to understand where your support handoff breaks down today.",
                    }
                ],
            }
        ],
        "suggested_follow_ups": [
            {
                "question": "Which CRM object and fields should receive action items?",
                "rationale": "The customer asked to push action items into their CRM but did not specify the target schema or workflow.",
                "evidence_refs": [{"segment_id": "seg_004", "quote": "we need to push action items into our CRM."}],
            }
        ],
        "notable_quotes": [
            {
                "speaker": "Customer",
                "quote": "Managers spend Monday morning reconstructing what happened from call recordings.",
                "timestamp": "00:09.300",
                "segment_id": "seg_002",
            }
        ],
        "follow_up_email": {
            "subject": "Prototype for speaker-aware meeting handoffs",
            "body": (
                "Hi,\n\nThanks for the conversation. I heard that inconsistent escalation notes, "
                "evidence-backed action items, compliance-sensitive risk detection, and CRM sync "
                "are the core requirements. I will send a prototype with speaker-aware transcripts, "
                "action items with evidence, and a redaction pass before CRM sync.\n\nBest,\n[Your name]"
            ),
        },
    }


show_json(demo_meeting_intelligence(), expanded=False)
```

## Step 5: Render a reviewable meeting brief

The review artifact keeps speaker, segment ID, timestamp, and quote evidence next to decisions, risks, and action items so humans can spot-check before anything is written downstream.


```python
def clean_markdown_cell(value: Any) -> str:
    if value is None:
        return "_Not specified._"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_evidence_refs(refs: Any) -> str:
    if not isinstance(refs, list) or not refs:
        return "_No evidence refs._"

    rendered = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        segment_id = clean_markdown_cell(ref.get("segment_id", ""))
        quote = clean_markdown_cell(ref.get("quote", ""))
        rendered.append(f"`{segment_id}`: {quote}")
    return "<br>".join(rendered) if rendered else "_No evidence refs._"


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, Any]]) -> str:
    if not rows:
        return "_None identified._"

    header = "| " + " | ".join(title for title, _ in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        values = []
        for _, key in columns:
            value = key(row) if callable(key) else row.get(key, "")
            values.append(clean_markdown_cell(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body])


def render_meeting_brief(intelligence: dict[str, Any]) -> str:
    follow_up = intelligence.get("follow_up_email", {})
    evidence_column = ("Evidence", lambda row: render_evidence_refs(row.get("evidence_refs", [])))
    lines = [
        "# Meeting Brief",
        "",
        "## Summary",
        "",
        str(intelligence.get("summary", "")).strip() or "_No summary generated._",
        "",
        "## Participants",
        "",
        markdown_table(
            intelligence.get("participants", []),
            [("Speaker", "speaker"), ("Inferred role", "inferred_role"), evidence_column],
        ),
        "",
        "## Customer Context",
        "",
        markdown_table(intelligence.get("customer_context", []), [("Fact", "fact"), evidence_column]),
        "",
        "## Decisions",
        "",
        markdown_table(
            intelligence.get("decisions", []),
            [("Decision", "decision"), ("Owner", "speaker_or_group"), evidence_column],
        ),
        "",
        "## Action Items",
        "",
        markdown_table(
            intelligence.get("action_items", []),
            [
                ("Owner", "owner_speaker"),
                ("Task", "task"),
                ("Due date or trigger", "due_date_or_trigger"),
                evidence_column,
            ],
        ),
        "",
        "## Risks",
        "",
        markdown_table(
            intelligence.get("risks", []),
            [("Risk", "risk"), ("Severity", "severity"), evidence_column, ("Mitigation", "mitigation")],
        ),
        "",
        "## Explicit Questions",
        "",
        markdown_table(
            intelligence.get("explicit_questions", []),
            [
                ("Question", "question"),
                ("Asked by", "asked_by_speaker"),
                ("Directed to", "directed_to_speaker"),
                evidence_column,
            ],
        ),
        "",
        "## Suggested Follow-ups",
        "",
        markdown_table(
            intelligence.get("suggested_follow_ups", []),
            [("Question", "question"), ("Rationale", "rationale"), evidence_column],
        ),
        "",
        "## Notable Quotes",
        "",
        markdown_table(
            intelligence.get("notable_quotes", []),
            [("Speaker", "speaker"), ("Quote", "quote"), ("Timestamp", "timestamp"), ("Segment ID", "segment_id")],
        ),
        "",
        "## Follow-up Email Draft",
        "",
        f"**Subject:** {follow_up.get('subject', '')}",
        "",
        str(follow_up.get("body", "")).strip(),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


demo_brief = render_meeting_brief(demo_meeting_intelligence())
show_markdown(demo_brief)
```

## Step 6: Add guardrails and write artifacts

The sample writes a `guardrail_report.json` with local checks for:

- normalized transcript segments;
- basic email and phone PII patterns;
- evidence references that point to real segment IDs and matching quotes;
- medium/high risk outputs;
- optional moderation flags;
- raw transcription response storage.


```python
def summarize_moderation_response(response: Any) -> dict[str, Any]:
    data = to_plain(response)
    summaries: list[dict[str, Any]] = []

    for result in data.get("results", []) if isinstance(data, dict) else []:
        categories = result.get("categories", {}) if isinstance(result, dict) else {}
        category_scores = result.get("category_scores", {}) if isinstance(result, dict) else {}
        flagged_categories = sorted(key for key, value in categories.items() if bool(value))
        top_scores = dict(sorted(category_scores.items(), key=lambda item: float(item[1] or 0.0), reverse=True)[:5])
        summaries.append(
            {
                "flagged": bool(result.get("flagged")) if isinstance(result, dict) else False,
                "flagged_categories": flagged_categories,
                "top_category_scores": top_scores,
            }
        )

    return {
        "id": data.get("id") if isinstance(data, dict) else None,
        "model": data.get("model") if isinstance(data, dict) else DEFAULT_MODERATION_MODEL,
        "flagged": any(item["flagged"] for item in summaries),
        "results": summaries,
    }


def moderate_text(text: str, model: str = DEFAULT_MODERATION_MODEL) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    response = client.moderations.create(model=model, input=text)
    return summarize_moderation_response(response)


def iter_evidence_refs(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            next_path = f"{path}.{key}"
            if key == "evidence_refs":
                found.append((next_path, inner))
            else:
                found.extend(iter_evidence_refs(inner, next_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(iter_evidence_refs(item, f"{path}[{index}]"))
    return found


def normalize_for_quote_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_evidence_refs(intelligence: dict[str, Any], segments: list[Segment]) -> list[dict[str, Any]]:
    segment_by_id = {segment.segment_id: segment for segment in segments}
    problems: list[dict[str, Any]] = []

    for path, refs in iter_evidence_refs(intelligence):
        if not isinstance(refs, list) or not refs:
            problems.append({"path": path, "issue": "missing_or_empty_evidence_refs"})
            continue

        for index, ref in enumerate(refs):
            ref_path = f"{path}[{index}]"
            if not isinstance(ref, dict):
                problems.append({"path": ref_path, "issue": "evidence_ref_is_not_an_object"})
                continue

            segment_id = str(ref.get("segment_id", "")).strip()
            quote = str(ref.get("quote", "")).strip()
            if not segment_id or not quote:
                problems.append({"path": ref_path, "issue": "missing_segment_id_or_quote", "segment_id": segment_id})
                continue

            segment = segment_by_id.get(segment_id)
            if segment is None:
                problems.append({"path": ref_path, "issue": "unknown_segment_id", "segment_id": segment_id})
                continue

            if normalize_for_quote_match(quote) not in normalize_for_quote_match(segment.text):
                problems.append(
                    {
                        "path": ref_path,
                        "issue": "quote_not_found_in_segment",
                        "segment_id": segment_id,
                        "quote": quote,
                    }
                )

    for index, quote in enumerate(intelligence.get("notable_quotes", [])):
        if not isinstance(quote, dict):
            continue
        segment_id = str(quote.get("segment_id", "")).strip()
        quote_text = str(quote.get("quote", "")).strip()
        segment = segment_by_id.get(segment_id)
        if segment is None:
            problems.append({"path": f"$.notable_quotes[{index}]", "issue": "unknown_segment_id", "segment_id": segment_id})
        elif normalize_for_quote_match(quote_text) not in normalize_for_quote_match(segment.text):
            problems.append(
                {
                    "path": f"$.notable_quotes[{index}]",
                    "issue": "quote_not_found_in_segment",
                    "segment_id": segment_id,
                    "quote": quote_text,
                }
            )

    return problems


def add_guardrail_check(checks: list[dict[str, Any]], name: str, status: str, detail: str, evidence = None) -> None:
    check: dict[str, Any] = {"name": name, "status": status, "detail": detail}
    if evidence is not None:
        check["evidence"] = evidence
    checks.append(check)


def build_guardrail_report(
    segments: list[Segment],
    intelligence: dict[str, Any],
    meeting_brief: str,
    redaction_enabled: bool,
    raw_saved: bool,
    moderation_results: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    transcript_text = transcript_for_model(segments)

    add_guardrail_check(
        checks,
        "transcript_segments_present",
        "pass" if segments else "fail",
        f"Found {len(segments)} normalized transcript segments.",
    )

    pii_found = pii_matches(transcript_text + "\n" + meeting_brief)
    pii_detail = (
        "Basic PII patterns remain after redaction."
        if redaction_enabled
        else "Basic PII patterns were detected; run with redaction or review before storage."
    )
    add_guardrail_check(
        checks,
        "basic_pii_scan",
        "review" if pii_found else "pass",
        pii_detail if pii_found else "No basic email or phone patterns detected.",
        {"matches": pii_found, "redaction_enabled": redaction_enabled},
    )

    evidence_ref_problems = validate_evidence_refs(intelligence, segments)
    add_guardrail_check(
        checks,
        "evidence_refs",
        "review" if evidence_ref_problems else "pass",
        (
            "Some evidence references are missing, cite unknown segments, or quote text that is not present in the cited segment."
            if evidence_ref_problems
            else "All evidence references point to real segments with matching quote text."
        ),
        {"problem_count": len(evidence_ref_problems), "examples": evidence_ref_problems[:5]},
    )

    risks = intelligence.get("risks", [])
    review_risks = [risk for risk in risks if str(risk.get("severity", "")).lower() in {"medium", "high"}]
    severity_counts = {
        "low": sum(1 for risk in risks if str(risk.get("severity", "")).lower() == "low"),
        "medium": sum(1 for risk in risks if str(risk.get("severity", "")).lower() == "medium"),
        "high": sum(1 for risk in risks if str(risk.get("severity", "")).lower() == "high"),
    }
    add_guardrail_check(
        checks,
        "risk_outputs",
        "review" if review_risks else "pass",
        "Medium or high risks should be reviewed before downstream writes." if review_risks else "No medium or high risks identified.",
        {"severity_counts": severity_counts},
    )

    moderation_flagged = [name for name, result in moderation_results.items() if isinstance(result, dict) and result.get("flagged")]
    if moderation_results:
        add_guardrail_check(
            checks,
            "moderation",
            "review" if moderation_flagged else "pass",
            "Moderation flagged content that should be reviewed." if moderation_flagged else "Moderation did not flag transcript or brief content.",
            {"flagged_artifacts": moderation_flagged},
        )
    else:
        add_guardrail_check(checks, "moderation", "not_run", "Moderation was not requested. Use moderation for content safety classification.")

    add_guardrail_check(
        checks,
        "raw_response_storage",
        "review" if raw_saved else "pass",
        "Raw transcription response was saved; confirm retention and access controls." if raw_saved else "Raw transcription response was not saved.",
    )

    status = "review_required" if any(check["status"] in {"review", "fail"} for check in checks) else "pass"
    if any(check["status"] == "fail" for check in checks):
        status = "fail"

    return {
        "status": status,
        "recommended_next_step": "Send artifacts to human review before downstream writes." if status != "pass" else "Artifacts passed local guardrail checks.",
        "checks": checks,
        "moderation": moderation_results,
    }

print("Guardrail helpers ready")
```

```python
def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_artifacts(
    output_dir: Path,
    segments: list[Segment],
    intelligence: dict[str, Any],
    guardrail_report: dict[str, Any],
    raw_payload = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "transcript_segments.json", [asdict(segment) for segment in segments])
    (output_dir / "speaker_labeled_transcript.md").write_text(transcript_as_markdown(segments), encoding="utf-8")
    write_json(output_dir / "meeting_intelligence.json", intelligence)
    (output_dir / "meeting_brief.md").write_text(render_meeting_brief(intelligence), encoding="utf-8")
    write_json(output_dir / "guardrail_report.json", guardrail_report)
    if raw_payload is not None:
        write_json(output_dir / "raw_transcription_response.json", to_plain(raw_payload))


def run_pipeline_from_segments(
    segments: list[Segment],
    output_dir: Path,
    intelligence = None,
    redaction_enabled: bool = False,
    moderation_results = None,
    raw_saved: bool = False,
    raw_payload = None,
) -> dict[str, Any]:
    if redaction_enabled:
        segments = redact_segments(segments)
    if intelligence is None:
        intelligence = generate_meeting_intelligence(segments)
    meeting_brief = render_meeting_brief(intelligence)
    guardrail_report = build_guardrail_report(
        segments=segments,
        intelligence=intelligence,
        meeting_brief=meeting_brief,
        redaction_enabled=redaction_enabled,
        raw_saved=raw_saved,
        moderation_results=moderation_results or {},
    )
    write_artifacts(output_dir, segments, intelligence, guardrail_report, raw_payload=raw_payload if raw_saved else None)
    return {
        "segments": segments,
        "intelligence": intelligence,
        "meeting_brief": meeting_brief,
        "guardrail_report": guardrail_report,
        "output_dir": output_dir,
    }

print("Artifact helpers ready")
```

## Step 7: Run the deterministic demo fixture

This section is a deterministic no-network demo, not a model-quality eval. It uses a fixed synthetic diarized transcript and a fixed expected meeting-intelligence object so reviewers can run the notebook without an API key.

### What this fixture checks

The fixture exercises the same artifact and guardrail path used by real audio: transcript rendering, JSON writing, Markdown brief rendering, PII redaction helpers, evidence-reference validation, nullable fields, and review routing.

### What this fixture does not check

It does not measure transcription quality, diarization accuracy, or model extraction quality on new meetings. The eval sections below add deterministic scoring and an optional LLM-as-judge pattern for that layer.


```python
output_dir = Path(tempfile.mkdtemp(prefix="meeting-intelligence-demo-"))
demo_run = run_pipeline_from_segments(
    segments=DEMO_SEGMENTS,
    output_dir=output_dir,
    intelligence=demo_meeting_intelligence(),
)

print(f"Wrote meeting intelligence artifacts to {output_dir}")
for artifact_name in [
    "transcript_segments.json",
    "speaker_labeled_transcript.md",
    "meeting_intelligence.json",
    "meeting_brief.md",
    "guardrail_report.json",
]:
    artifact_path = output_dir / artifact_name
    print(f"- {artifact_path} ({artifact_path.stat().st_size} bytes)")
```

```python
segments = json.loads((output_dir / "transcript_segments.json").read_text())
segments[:2]
```

```python
show_markdown((output_dir / "speaker_labeled_transcript.md").read_text())
```

```python
meeting_intelligence_json = json.loads((output_dir / "meeting_intelligence.json").read_text())
show_json(meeting_intelligence_json, expanded=False)
```

```python
show_markdown((output_dir / "meeting_brief.md").read_text())
```

```python
guardrail_report = json.loads((output_dir / "guardrail_report.json").read_text())
show_json(guardrail_report, expanded=True)
```

## Step 8: Run with real audio

The next cell is intentionally opt-in. Set `RUN_REAL_AUDIO = True`, provide your local audio paths, and make sure `OPENAI_API_KEY` is set.

The Transcriptions API accepts files up to 25 MB. `chunking_strategy="auto"` segments a valid upload; it does not split an oversized file. For larger meetings, compress to a supported lower-bitrate format or split the recording into bounded files before transcription, then preserve or offset timestamps when combining results.
Long recordings can also outlast the Python SDK default read timeout. The helper streams finalized diarized segments by default and keeps a 30-minute timeout as a backstop. Set `stream_transcription=False` only when you specifically need one non-streamed response; split unusually long recordings when one request is not operationally reliable.

### How readers supply their files

This cookbook is notebook-first; there is no separate `.py` command in the published artifact. Put the meeting recording and any optional reference clips somewhere the notebook kernel can read. In local Jupyter, that can be a folder beside the notebook or an absolute path on disk. In a hosted notebook, upload the files into the notebook session first.

For example, a reader might have:

```text
audio/
  customer_call.mp3
  internal_rep_reference.wav
```

Then point the configuration variables at those files:

```python
AUDIO_FILE = Path("audio/customer_call.mp3")
KNOWN_SPEAKERS = {
    "Internal rep": Path("audio/internal_rep_reference.wav"),
}
```

`AUDIO_FILE` is the original meeting recording. `KNOWN_SPEAKERS` maps the label you want in the output to a separate 2-10 second reference clip; the helper sends the clip with the request rather than appending it to the meeting audio. In a production application, the same helper can receive a temporary file created from an upload or downloaded from object storage.

For the first production-style run, keep the setup simple:

- Use one meeting audio file.
- Use `chunking_strategy="auto"` for longer recordings.
- Add known-speaker references only when you have consent and a clear business need.
- Run redaction before storage.
- Run moderation when harmful-content classification is part of your review policy.


```python
RUN_REAL_AUDIO = False
AUDIO_FILE = Path("/path/to/meeting.wav")
# Keep each reference clip separate from AUDIO_FILE. Use a clean, consented 2-10 second sample of one speaker.
KNOWN_SPEAKERS = {
    # "Internal rep": Path("/path/to/internal_rep_reference.wav"),
    # "Customer": Path("/path/to/customer_reference.wav"),
}
# Demonstration only: masks basic email and phone patterns, not a complete PII/DLP solution.
REDACT_REAL_AUDIO = True
MODERATE_REAL_AUDIO = False
SAVE_RAW_RESPONSE = False
REAL_OUTPUT_DIR = Path(tempfile.mkdtemp(prefix="meeting-intelligence-real-"))

if RUN_REAL_AUDIO:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running on real audio.")
    if not AUDIO_FILE.is_file():
        raise FileNotFoundError(AUDIO_FILE)

    known_speakers = [(speaker_name, reference_path) for speaker_name, reference_path in KNOWN_SPEAKERS.items()]
    raw_transcription = transcribe_with_diarization(AUDIO_FILE, known_speakers)
    real_segments = normalize_segments(raw_transcription)
    if REDACT_REAL_AUDIO:
        real_segments = redact_segments(real_segments)

    moderation_results: dict[str, Any] = {}
    if MODERATE_REAL_AUDIO:
        moderation_results["transcript"] = moderate_text(transcript_for_model(real_segments))

    real_intelligence = generate_meeting_intelligence(real_segments)
    real_brief = render_meeting_brief(real_intelligence)
    if MODERATE_REAL_AUDIO:
        moderation_results["meeting_brief"] = moderate_text(real_brief)

    real_report = build_guardrail_report(
        segments=real_segments,
        intelligence=real_intelligence,
        meeting_brief=real_brief,
        redaction_enabled=REDACT_REAL_AUDIO,
        raw_saved=SAVE_RAW_RESPONSE,
        moderation_results=moderation_results,
    )
    write_artifacts(
        REAL_OUTPUT_DIR,
        real_segments,
        real_intelligence,
        real_report,
        raw_payload=raw_transcription if SAVE_RAW_RESPONSE else None,
    )
    print(f"Wrote real-audio artifacts to {REAL_OUTPUT_DIR}")
else:
    print("Skipped real audio run. Set RUN_REAL_AUDIO = True after configuring AUDIO_FILE and OPENAI_API_KEY.")
```

## Step 9: Run deterministic smoke and regression checks

These checks are deterministic and do not call the API. Treat them as a smoke test and regression suite for the notebook mechanics, not as an eval of model quality.

### Smoke-test checks

The first checks confirm that the notebook writes all expected artifacts and routes medium-risk outputs to review.

### Regression checks

The remaining assertions catch regressions in schema nullability, evidence references, unsupported demo claims, response edge cases, redaction, and timestamp formatting.


```python
expected_files = {
    "transcript_segments.json",
    "speaker_labeled_transcript.md",
    "meeting_intelligence.json",
    "meeting_brief.md",
    "guardrail_report.json",
}
assert expected_files.issubset({path.name for path in output_dir.iterdir()})
assert guardrail_report["status"] == "review_required"
assert any(check["name"] == "risk_outputs" and check["status"] == "review" for check in guardrail_report["checks"])
assert any(check["name"] == "evidence_refs" and check["status"] == "pass" for check in guardrail_report["checks"])

action_schema = MEETING_INTELLIGENCE_SCHEMA["schema"]["properties"]["action_items"]["items"]["properties"]
participant_schema = MEETING_INTELLIGENCE_SCHEMA["schema"]["properties"]["participants"]["items"]["properties"]
question_schema = MEETING_INTELLIGENCE_SCHEMA["schema"]["properties"]["explicit_questions"]["items"]["properties"]
assert "null" in action_schema["due_date_or_trigger"]["type"]
assert "null" in action_schema["owner_speaker"]["type"]
assert "null" in participant_schema["inferred_role"]["type"]
assert "null" in question_schema["directed_to_speaker"]["type"]

assert demo_run["segments"][0].segment_id == "seg_001"
assert demo_run["intelligence"]["decisions"] == []
assert demo_run["intelligence"]["action_items"][0]["due_date_or_trigger"] is None
assert demo_run["intelligence"]["action_items"][0]["evidence_refs"][0]["segment_id"] == "seg_005"
assert demo_run["intelligence"]["explicit_questions"]
assert demo_run["intelligence"]["suggested_follow_ups"]
assert validate_evidence_refs(demo_run["intelligence"], demo_run["segments"]) == []
assert "structured outputs" not in demo_run["intelligence"]["follow_up_email"]["body"].lower()
assert "`seg_005`" in demo_run["meeting_brief"]
assert "_Not specified._" in demo_run["meeting_brief"]

broken_intelligence = json.loads(json.dumps(demo_run["intelligence"]))
broken_intelligence["action_items"][0]["evidence_refs"] = [{"segment_id": "seg_999", "quote": "I will send a prototype"}]
assert validate_evidence_refs(broken_intelligence, demo_run["segments"])

broken_intelligence = json.loads(json.dumps(demo_run["intelligence"]))
broken_intelligence["action_items"][0]["evidence_refs"] = [{"segment_id": "seg_005", "quote": "I will send the contract tomorrow"}]
assert validate_evidence_refs(broken_intelligence, demo_run["segments"])

try:
    response_output_text_or_raise({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}})
    raise AssertionError("Expected incomplete response to raise")
except RuntimeError as exc:
    assert "incomplete" in str(exc)

try:
    response_output_text_or_raise({"status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "Cannot comply."}]}]})
    raise AssertionError("Expected refusal response to raise")
except RuntimeError as exc:
    assert "refusal" in str(exc).lower()

try:
    response_output_text_or_raise({"status": "completed", "output_text": ""})
    raise AssertionError("Expected empty response to raise")
except RuntimeError as exc:
    assert "empty" in str(exc).lower()

try:
    parse_meeting_intelligence_json("not json")
    raise AssertionError("Expected invalid JSON to raise")
except RuntimeError as exc:
    assert "invalid JSON" in str(exc)

redacted = redact_segments([
    Segment("seg_test", "Customer", 0.0, 3.0, "Email me at alex@example.com or call 415-555-0100.")
])
assert redacted[0].segment_id == "seg_test"
assert redacted[0].text == "Email me at [email] or call [phone]."
assert format_timestamp(6000) == "100:00.000"

with tempfile.NamedTemporaryFile(suffix=".wav") as oversized_audio:
    oversized_audio.truncate(MAX_AUDIO_UPLOAD_BYTES + 1)
    oversized_audio.flush()
    try:
        transcribe_with_diarization(Path(oversized_audio.name), [])
        raise AssertionError("Expected oversized audio to raise")
    except ValueError as exc:
        assert "25 MB" in str(exc)

with tempfile.NamedTemporaryFile(suffix=".wav") as tiny_audio:
    try:
        transcribe_with_diarization(Path(tiny_audio.name), [], request_timeout_seconds=0)
        raise AssertionError("Expected invalid timeout to raise")
    except ValueError as exc:
        assert "positive" in str(exc)

streamed_transcription = collect_streamed_transcription([
    {"type": "transcript.text.segment", "id": "seg_stream", "speaker": "A", "start": 0.0, "end": 1.0, "text": "Hello"},
    {"type": "transcript.text.done", "text": "Hello", "usage": {"total_tokens": 1}},
])
streamed_segments = normalize_segments(streamed_transcription)
assert streamed_segments[0].segment_id == "seg_stream"
assert streamed_segments[0].speaker == "A"
assert streamed_transcription["usage"]["total_tokens"] == 1

print("Notebook demo validation passed")
```

## Step 10: Run deterministic evals

This section runs a small deterministic eval against the labeled demo fixture. It is still not a broad production eval, but it shows how to score extraction quality with reproducible rules before adding model-graded judgments.

The scorers below measure action-item precision/recall, explicit-question precision/recall, unsupported decisions, nullable unknown fields, and evidence-reference validity. For production, replace `GOLD_EVAL_LABELS` with a larger labeled dataset and run the same scorers across every example.


```python
GOLD_EVAL_LABELS: dict[str, Any] = {
    "action_items": [
        {
            "owner_speaker": "Solutions Engineer",
            "task_contains": ["send a prototype", "speaker-aware transcripts", "redaction pass", "crm sync"],
            "due_date_or_trigger": None,
            "evidence_segment_ids": ["seg_005"],
        }
    ],
    "explicit_questions": [
        {
            "question_contains": ["support handoff", "break down"],
            "asked_by_speaker": "Solutions Engineer",
            "directed_to_speaker": "Customer",
            "evidence_segment_ids": ["seg_001"],
        }
    ],
    "decisions": [],
}


def normalize_for_eval(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def evidence_ref_segment_ids(item: dict[str, Any]) -> set[str]:
    return {str(ref.get("segment_id", "")) for ref in item.get("evidence_refs", []) if isinstance(ref, dict)}


def contains_all_fragments(text: Any, fragments: list[str]) -> bool:
    normalized = normalize_for_eval(text)
    return all(normalize_for_eval(fragment) in normalized for fragment in fragments)


def action_item_matches_label(item: dict[str, Any], label: dict[str, Any]) -> bool:
    return (
        item.get("owner_speaker") == label.get("owner_speaker")
        and item.get("due_date_or_trigger") == label.get("due_date_or_trigger")
        and contains_all_fragments(item.get("task"), label.get("task_contains", []))
        and set(label.get("evidence_segment_ids", [])).issubset(evidence_ref_segment_ids(item))
    )


def explicit_question_matches_label(item: dict[str, Any], label: dict[str, Any]) -> bool:
    return (
        item.get("asked_by_speaker") == label.get("asked_by_speaker")
        and item.get("directed_to_speaker") == label.get("directed_to_speaker")
        and contains_all_fragments(item.get("question"), label.get("question_contains", []))
        and set(label.get("evidence_segment_ids", [])).issubset(evidence_ref_segment_ids(item))
    )


def precision_recall(predicted: list[dict[str, Any]], labels: list[dict[str, Any]], matcher) -> dict[str, Any]:
    matched_label_indexes: set[int] = set()
    matched_predictions = 0

    for item in predicted:
        for index, label in enumerate(labels):
            if index in matched_label_indexes:
                continue
            if matcher(item, label):
                matched_label_indexes.add(index)
                matched_predictions += 1
                break

    precision = matched_predictions / len(predicted) if predicted else (1.0 if not labels else 0.0)
    recall = len(matched_label_indexes) / len(labels) if labels else 1.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "matched_predictions": matched_predictions,
        "predicted_count": len(predicted),
        "label_count": len(labels),
    }


def evidence_ref_count(intelligence: dict[str, Any]) -> int:
    return sum(len(refs) for _, refs in iter_evidence_refs(intelligence) if isinstance(refs, list)) + len(intelligence.get("notable_quotes", []))


def run_deterministic_evals(
    intelligence: dict[str, Any],
    segments: list[Segment],
    labels: dict[str, Any],
) -> dict[str, Any]:
    action_item_scores = precision_recall(
        intelligence.get("action_items", []),
        labels.get("action_items", []),
        action_item_matches_label,
    )
    explicit_question_scores = precision_recall(
        intelligence.get("explicit_questions", []),
        labels.get("explicit_questions", []),
        explicit_question_matches_label,
    )
    evidence_problems = validate_evidence_refs(intelligence, segments)
    total_evidence_refs = evidence_ref_count(intelligence)
    valid_evidence_ref_rate = (
        round((total_evidence_refs - len(evidence_problems)) / total_evidence_refs, 3)
        if total_evidence_refs
        else 1.0
    )
    action_items = intelligence.get("action_items", [])
    nullable_due_date_rate = (
        round(sum(1 for item in action_items if item.get("due_date_or_trigger") is None) / len(action_items), 3)
        if action_items
        else 1.0
    )
    unsupported_decision_count = len(intelligence.get("decisions", [])) if not labels.get("decisions") else 0

    pass_conditions = [
        action_item_scores["precision"] == 1.0,
        action_item_scores["recall"] == 1.0,
        explicit_question_scores["precision"] == 1.0,
        explicit_question_scores["recall"] == 1.0,
        valid_evidence_ref_rate == 1.0,
        nullable_due_date_rate == 1.0,
        unsupported_decision_count == 0,
    ]

    return {
        "status": "pass" if all(pass_conditions) else "review_required",
        "action_items": action_item_scores,
        "explicit_questions": explicit_question_scores,
        "valid_evidence_ref_rate": valid_evidence_ref_rate,
        "evidence_ref_problem_count": len(evidence_problems),
        "unsupported_decision_count": unsupported_decision_count,
        "nullable_due_date_rate": nullable_due_date_rate,
    }


deterministic_eval_report = run_deterministic_evals(
    demo_run["intelligence"],
    demo_run["segments"],
    GOLD_EVAL_LABELS,
)
show_json(deterministic_eval_report, expanded=True)
assert deterministic_eval_report["status"] == "pass"
```

## Step 11: Add optional LLM-as-judge evals

LLM-as-judge evals are useful for grading qualities that deterministic scorers cannot fully capture, such as summary usefulness, missing follow-ups, and whether the brief would help a reviewer. Keep this optional because it calls the API and can vary by judge model. Use it alongside deterministic scorers, not instead of them.

The judge below receives the transcript, the structured output, and a rubric. It returns scores and review findings. Leave `RUN_LLM_JUDGE_EVAL = False` for the default no-network notebook run.


```python
RUN_LLM_JUDGE_EVAL = False
LLM_JUDGE_MODEL = os.getenv("OPENAI_MEETING_INTELLIGENCE_JUDGE_MODEL", DEFAULT_SUMMARY_MODEL)

LLM_JUDGE_SCHEMA: dict[str, Any] = {
    "name": "meeting_intelligence_judge",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "outcome": {"type": "string", "enum": ["pass", "review", "fail"]},
            "overall_score": {"type": "number"},
            "scores": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "grounding": {"type": "number"},
                    "action_item_correctness": {"type": "number"},
                    "completeness": {"type": "number"},
                    "safety_review_readiness": {"type": "number"},
                },
                "required": ["grounding", "action_item_correctness", "completeness", "safety_review_readiness"],
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "area": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "explanation": {"type": "string"},
                    },
                    "required": ["area", "severity", "explanation"],
                },
            },
        },
        "required": ["outcome", "overall_score", "scores", "findings"],
    },
}


def run_llm_judge_eval(segments: list[Segment], intelligence: dict[str, Any], model: str = LLM_JUDGE_MODEL) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    transcript = transcript_for_model(segments)
    completion = client.responses.create(
        model=model,
        temperature=0,
        store=False,
        input=[
            {
                "role": "system",
                "content": (
                    "You are judging a meeting-intelligence extraction. Grade only against the transcript. "
                    "Penalize unsupported claims, missing major action items, missing customer risks, incorrect speaker attribution, "
                    "and outputs that are not ready for human review. Return calibrated scores from 0 to 1."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Transcript:\n"
                    f"{transcript}\n\n"
                    "Meeting intelligence JSON:\n"
                    f"{json.dumps(intelligence, indent=2)}"
                ),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": LLM_JUDGE_SCHEMA["name"],
                "strict": LLM_JUDGE_SCHEMA["strict"],
                "schema": LLM_JUDGE_SCHEMA["schema"],
            }
        },
    )
    return parse_meeting_intelligence_json(response_output_text_or_raise(completion))


if RUN_LLM_JUDGE_EVAL:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running the LLM judge eval.")
    llm_judge_report = run_llm_judge_eval(demo_run["segments"], demo_run["intelligence"])
    show_json(llm_judge_report, expanded=True)
else:
    print("Skipped LLM judge eval. Set RUN_LLM_JUDGE_EVAL = True after configuring OPENAI_API_KEY.")
```

## Production hardening checklist

Use this checklist before turning the sample into a customer workflow:

| Concern | Recommendation |
| --- | --- |
| Consent | Make sure call recording, diarization, and known-speaker references are permitted in your product, policy, and region. |
| Raw audio retention | Store raw audio only as long as needed. Persist normalized transcript segments when possible. |
| Large recordings | Reject files over 25 MB before upload. Compress or split longer meetings, then preserve timestamp offsets when combining results. |
| PII and DLP | Treat the included email and phone regexes as illustrative only. Use a policy-approved PII/DLP detector and human review for sensitive or regulated workflows. |
| Speaker references | Treat reference clips as sensitive data. Store minimally, encrypt at rest, and rotate/delete when no longer needed. |
| Evidence | Require structured evidence references on decisions, risks, and action items. Validate that each reference points to a real segment ID and quote. |
| Human review | Route high-risk summaries, compliance promises, pricing claims, or contractual terms for review. |
| Moderation | Use the Moderation API for harmful-content classification when notes may contain unsafe content. Keep privacy and compliance checks separate. |
| Retry behavior | Retry transient API errors with backoff. Avoid duplicating downstream CRM writes by using idempotency keys. |
| Observability | Log model names, prompt versions, schema versions, audio duration, latency, redaction status, and reviewer decisions. |
| Evaluation | Sample calls weekly. Track speaker attribution accuracy, action-item precision, and unsupported-claim rate. |


## Evaluation guidance for production

The deterministic eval above is intentionally small: it proves that the scoring pattern works on a labeled fixture. Production teams should expand it into a representative eval set before writing outputs to downstream systems. Start with a small, consented set of recordings or transcript fixtures, create human-reviewed labels, and keep a holdout set for regression testing when prompts, schemas, or models change.

| Area | Example metrics |
| --- | --- |
| Speaker attribution | Speaker-label accuracy, diarization error rate, speaker-turn boundary accuracy, known-speaker match rate. |
| Transcript grounding | Quote exactness, timestamp correctness, evidence-reference validity, unsupported-claim rate. |
| Structured extraction | Precision and recall for action items, decisions, risks, explicit questions, suggested follow-ups, and customer requirements. |
| Safety and privacy | PII redaction recall, moderation flag recall, false-positive review rate, raw-audio retention compliance. |
| Workflow impact | Time-to-CRM-update, reviewer override rate, follow-up completion rate, renewal or escalation risk detection latency. |

A useful first eval is simple: ask reviewers to mark each extracted action item as correct, partially correct, unsupported, or missing from the output. Track precision for generated items and recall against the human-labeled gold set. For quotes and evidence, prefer exact-match or near-exact-match checks against the transcript segment text so that helpful-sounding but unsupported summaries do not pass unnoticed. LLM-as-judge can help grade usefulness and completeness, but keep deterministic grounding checks in the loop because they are easier to reproduce.


## Next steps

You can adapt the same pipeline for:

- Customer success handoffs after quarterly business reviews.
- Support escalations where accountability and exact quotes matter.
- Sales discovery calls that feed CRM next steps.
- Recruiting interview debriefs where each interviewer needs sourced notes.
- Healthcare or financial-services workflows with stronger review and retention controls.

For live scenarios, use Realtime for the in-call experience and still run this post-call diarization pipeline when you need durable, evidence-backed meeting intelligence.

Useful docs:

- [Audio and speech guide](https://developers.openai.com/api/docs/guides/audio)
- [Speech-to-text and speaker diarization](https://developers.openai.com/api/docs/guides/speech-to-text)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Moderation](https://developers.openai.com/api/docs/guides/moderation)
- [Safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices)
- [Realtime guide](https://developers.openai.com/api/docs/guides/realtime)