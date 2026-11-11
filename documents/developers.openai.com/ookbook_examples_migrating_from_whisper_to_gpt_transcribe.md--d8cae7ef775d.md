# Migrate from Whisper to GPT-Transcribe and GPT-Live-Transcribe

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Overview

OpenAI’s new transcription models give existing Whisper users two focused upgrade paths. GPT-Transcribe (`gpt-transcribe`) is designed for accurate transcription of completed audio via uploaded files. GPT-Live-Transcribe (`gpt-live-transcribe`) is designed for low-latency, continuously streaming transcription.

At a high level, the API endpoints are the same. File requests continue to use POST /v1/audio/transcriptions. Realtime integrations continue to configure a transcription session and handle transcription events. What’s different are the supported request fields, the output formats, and contextual/multilingual hints.

### What stays the same

- File transcription uses the existing Audio API transcription endpoint.
- Realtime transcription uses the existing Realtime transcription session, WebSocket or WebRTC transport, and transcription events.
- Applications still provide audio, receive transcription text, and handle API or connection errors.

### What changes

- Use `gpt-transcribe` for completed files, streamed file transcripts, or committed Realtime turns.
- Use `gpt-live-transcribe` for continuously streaming, low-latency live transcription.
- Replace the legacy `language` hint with the new-model `languages` array.
- Use `prompt` for free-form context and `keywords` for literal terms expected in the audio.
- Handle detected-language output for GPT-Transcribe, including an empty languages array.

## 1. Choose your migration path

- Recorded meetings, calls, or uploaded audio: migrate `whisper-1` to `gpt-transcribe` on POST /v1/audio/transcriptions.
- Live captions or continuously arriving microphone audio: migrate `gpt-realtime-whisper` to `gpt-live-transcribe` in a Realtime transcription session.
- Higher-accuracy transcription after a manually committed audio turn: use `gpt-transcribe` in a Realtime transcription session over WebSocket.
Treat live audio and streaming output as separate decisions. A completed file can produce streamed transcript events, and a Realtime session can wait for an audio turn to be committed before producing deltas.

## 2. Migrate recorded audio

The smallest file migration preserves the endpoint, SDK call, and file upload. Replace the model identifier, then consume the JSON transcription response.


### Prerequisites

- Python 3.11 or later.
- The OpenAI Python SDK: `python -m pip install --upgrade openai`.
- An `OPENAI_API_KEY` environment variable.
- A completed recording named `meeting.wav`, or update `audio_path` to point to your own file.
- Access to the transcription models used in the example.

File examples make live API requests. Realtime examples construct the session payloads. Use WebSocket or WebRTC for `gpt-live-transcribe`, and use WebSocket for committed-turn `gpt-transcribe`.


```python
import json
from pathlib import Path

from openai import OpenAI

client = OpenAI()
audio_path = Path("meeting.wav")
```

**Before — Whisper file transcription**


```python
with audio_path.open("rb") as audio:
    before = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio,
    )

print(before.text)
```

**After — GPT-Transcribe**


```python
with audio_path.open("rb") as audio:
    after = client.audio.transcriptions.create(
        model="gpt-transcribe",
        file=audio,
        response_format="json",
    )

print(after.text)
```

**Do’s and don’ts**

- Note that the new model returns JSON. If the existing application requests `text`, `verbose_json`, `srt`, or `vtt`, do not assume the same response_format remains valid. Keep Whisper for those formats or explicitly build and test the downstream conversion your application requires.

## 3. Update language hints and domain context

Legacy Whisper integrations commonly send a single `language` value and place domain vocabulary in a free-form prompt. The new models accept multiple expected input languages and separate structured keyword hints from the general prompt.


**Before — single-language Whisper request**


```python
from openai import OpenAI

client = OpenAI()

with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio,
        language="en",
        prompt="A support call about AC-42.",
    )

print(result.text)
```

**After — multilingual GPT-Transcribe request**


```python
from openai import OpenAI

client = OpenAI()

with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="gpt-transcribe",
        file=audio,
        prompt="A customer support call about billing.",
        extra_body={
            "keywords": ["AC-42", "Premium Plus"],
            "languages": ["en", "fr"],
        },
    )

print(result.text)
```

**Do’s and don’ts**

- Use `prompt` to describe the recording’s topic or setting.
- Use `keywords` for literal product names, medication names, account identifiers, or other domain-specific terms that may actually be spoken.
- Use `languages` to indicate expected spoken languages.
- Do not send both `language` and `languages`.
- Validate keyword input before making the request: each keyword must be a single-line literal and must not include `<`, `>`, a carriage return, or a line feed. Invalid keyword input rejects the whole request or session update.

## 4. Stream the transcription of a completed file

Streaming applies to the transcription output, not the audio input. The application first supplies a completed recording; the API then streams text as it transcribes that recording.


**Before — blocking Whisper file request**


```python
with audio_path.open("rb") as audio:
    before = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio,
    )

print(before.text)

# whisper-1 does not provide transcript.text.delta events.
```

**After — streamed GPT-Transcribe file request**


```python
with audio_path.open("rb") as audio:
    stream = client.audio.transcriptions.create(
        model="gpt-transcribe",
        file=audio,
        stream=True,
    )

    for event in stream:
        if event.type == "transcript.text.delta":
            print(event.delta, end="", flush=True)
        elif event.type == "transcript.text.done":
            print("\nFinal:", event.text)
```

**Do’s and don’ts**

- Use transcription events to distinguish in-progress from completed transcripts. Update your transcript or progress UI with `transcript.text.delta` events, then use `transcript.text.done` to mark the transcript as final.
- Do not label file streaming as live audio capture: the file must already exist.

## 5. Migrate continuous live transcription

For a live captioning workflow, preserve the Realtime connection and transcription-session architecture. Change the transcription model and update the model-specific configuration.


**Before — GPT-Realtime-Whisper**


```python
legacy_realtime_session = json.loads(
    r'''
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "transcription": {
          "model": "gpt-realtime-whisper",
          "language": "en"
        },
        "turn_detection": null
      }
    }
  }
}
'''
)

print(json.dumps(legacy_realtime_session, indent=2))
```

**After — GPT-Live-Transcribe**


```python
live_transcription_session = json.loads(
    r'''
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "transcription": {
          "model": "gpt-live-transcribe",
          "prompt": "A support call about a plan.",
          "keywords": ["AC-42", "Premium Plus"],
          "languages": ["en", "fr"],
          "delay": "low"
        },
        "turn_detection": null
      }
    }
  }
}
'''
)

print(json.dumps(live_transcription_session, indent=2))
```

**Do’s and don’ts**

- Continue handling `conversation.item.input_audio_transcription.delta` and `conversation.item.input_audio_transcription.completed`.
- Preserve the existing item_id-based reconciliation logic.
- Use the model’s `delay` setting to trade off faster partial transcripts against a more accurate final transcript.
- Preserve the existing WebSocket or WebRTC transport; Realtime transcription supports both.

## 6. Use GPT-Transcribe in a committed-turn Realtime session

GPT-Transcribe is not limited to uploaded files. Use it as the input transcription model in a Realtime session over WebSocket when your application needs higher-accuracy transcription after a manually committed audio turn.


**Before — legacy live-transcription session**


```python
legacy_live_session = json.loads(
    r'''
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "transcription": {
          "model": "gpt-realtime-whisper",
          "language": "en"
        }
      }
    }
  }
}
'''
)

print(json.dumps(legacy_live_session, indent=2))
```

**After — committed-turn GPT-Transcribe session**


```python
committed_turn_session = json.loads(
    r'''
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "transcription": {
          "model": "gpt-transcribe",
          "prompt": "A customer support call.",
          "keywords": ["AC-42"],
          "languages": ["en", "fr"]
        },
        "turn_detection": null
      }
    }
  }
}
'''
)

print(json.dumps(committed_turn_session, indent=2))
```

**Do’s and don’ts**

- Append audio to the input buffer, then send `input_audio_buffer.commit`. Transcription happens per committed chunk of audio, not continuous live captioning. GPT-Transcribe may emit transcript delta events before the completed event for that chunk.

## 7. Update response and event handling

GPT-Transcribe can include detected input languages in completed file and Realtime results. These are predictions returned by the model, not a restatement of the caller’s language hints.


**Before — transcript without language predictions**


```python
legacy_transcription_response = json.loads(
    r'''
{
  "text": "Bonjour, pouvez-vous m'entendre ?"
}
'''
)

print(json.dumps(legacy_transcription_response, indent=2))
```

**After — GPT-Transcribe detected-language response**


```python
detected_language_response = json.loads(
    r'''
{
  "text": "Bonjour, pouvez-vous m'entendre ?",
  "languages": [
    { "code": "fr" }
  ]
}
'''
)

print(json.dumps(detected_language_response, indent=2))

language_codes = [
    item["code"]
    for item in detected_language_response.get("languages", [])
]
print("Detected languages:", language_codes)
```

**Do’s and don’ts**

- Handle `languages: []` as a valid result when the model cannot make a reliable prediction.
- Do not infer that no one spoke, that the request failed, or that a synthetic `unknown` language was returned. GPT-Live-Transcribe does not return detected-language predictions in its initial contract.
- For Realtime, inspect `conversation.item.input_audio_transcription.completed`; GPT-Transcribe may attach the same language metadata to that event.

## 8. Check compatibility before switching

Some existing transcription features do not have a drop-in replacement in `gpt-transcribe` or `gpt-live-transcribe`.

- Subtitles: retain `whisper-1` if the integration depends on native SRT or VTT output.
- Timestamps: retain a model and response format that explicitly support word or segment timestamps.
- Translation: retain `/v1/audio/translations` with a supported translation model if the application translates audio into English.
- Speaker diarization: use `gpt-4o-transcribe-diarize` on `/v1/audio/transcriptions` with `response_format: "diarized_json"` when your application requires speaker labels. Set `chunking_strategy: "auto"` for recordings longer than 30 seconds. This model is not supported in the Realtime API.

## 9. Evaluate before and after

Use the same representative audio clips across both models. Compare the baseline, a direct model-only replacement, and a version that adds the new context fields. This isolates improvements from the model itself versus improvements caused by prompt, keywords, or language hints.

### Evaluate transcription quality

- Overall word error rate on representative recordings.
- Exact-match accuracy for names, product names, medication names, account identifiers, numbers, and email addresses.
- Performance with accents, background noise, telephony audio, and short utterances.
- Accuracy during language switching and mixed-language speech.
- Keyword hallucination: confirm the transcript does not insert hinted words that were not actually spoken.
- Completeness of the final transcript and any expected language metadata.

### Evaluate streaming and operational behavior

- Time to first transcript delta, reported separately for file streaming and live audio.
- Time from an explicit committed turn to the final transcript.
- Median and tail latency, including p95 or the team’s existing service-level threshold.
- How frequently partial transcript text changes before completion.
- Event ordering and item_id reconciliation across overlapping turns.
- Reconnect, retry, empty-audio, and interrupted-session behavior.
- Actual request pricing and production rate limits from the released source of truth.

## Common migration errors

- Treating `gpt-transcribe` as incompatible with Realtime solely because it is optimized for completed audio.
- Describing GPT-Transcribe as unable to stream because processing begins after a commit.
- Assuming streamed file output means the endpoint accepts an ongoing microphone stream.
- Sending both legacy `language` and new-model `languages`.
- Expecting subtitle formats, timestamps, speaker labels, or detected-language output from a model that does not support them.
- Treating an empty detected-language array as an API error.
- Forcing keywords into the transcript instead of treating them as hints.
- Assuming every Realtime model supports the same voice activity detection and latency controls.


## Related resources

- [Speech to text](https://developers.openai.com/api/docs/guides/speech-to-text)
- [Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription)
- [GPT-4o Transcribe Diarize](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize)