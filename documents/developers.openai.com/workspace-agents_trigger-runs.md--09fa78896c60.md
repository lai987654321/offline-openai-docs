# Trigger workspace agent runs

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use the Workspace Agents API to programmatically trigger a published ChatGPT
workspace agent through API.

This endpoint is designed to integrate with workflows where an external system
needs to trigger an agent outside of the ChatGPT UI and third party
triggers offered.

## Endpoint

```text
POST https://api.chatgpt.com/v1/workspace_agents/{id}/trigger
GET  https://api.chatgpt.com/v1/workspace_agents/{id}/runs/{run_id}
```

`id` is the stable public API trigger identifier for the published API channel,
in a `agtch_XXX` format.

`run_id` is the trigger run identifier returned by a beta trigger request, in an
`apirun_XXX` format.

## Authentication

Authenticate with a Workspace Agent access token:

```bash
Authorization: Bearer $AGENT_ACCESS_TOKEN
```

See [Authenticate with Workspace Agent access tokens](https://developers.openai.com/workspace-agents/authentication)
for how to provision a token.

## Request body

```json
{
  "conversation_key": "email_thread_abc",
  "input": "Summarize the customer escalation and recommend a response."
}
```

### Fields

| Field              | Type   | Required | Description                                                                                                 |
| ------------------ | ------ | -------- | ----------------------------------------------------------------------------------------------------------- |
| `input`            | string | Yes      | Message text passed to the agent as trigger input.                                                          |
| `conversation_key` | string | No       | Caller-defined stable identifier for continuing the same agent conversation across multiple trigger events. |

To safely retry the same trigger event, send an optional `Idempotency-Key`
header. Reuse the same key only when retrying the same event. Requests to the
same API trigger with the same key return the original accepted outcome instead
of adding a second trigger event to the queue.

## Response

The API durably queues the trigger event and returns `202 Accepted` with a link
to the ChatGPT conversation:

```json
{
  "conversation_url": "https://chatgpt.com/c/123"
}
```

The agent's response cannot currently be retrieved through the API.

## Track run status

Run status polling is in beta. To receive a trigger run ID, include
  `OpenAI-Beta: workspace_agent_runs=v1` when you trigger the agent.

With the beta header, the trigger response includes `agent_trigger_run_id`:

```json
{
  "conversation_url": "https://chatgpt.com/c/123",
  "agent_trigger_run_id": "apirun_123"
}
```

Poll the run ID until it reaches a terminal status:

```bash
curl https://api.chatgpt.com/v1/workspace_agents/$API_TRIGGER_ID/runs/$RUN_ID \
  -H "Authorization: Bearer $AGENT_ACCESS_TOKEN"
```

The response describes the latest run state:

```json
{
  "object": "workspace_agent.trigger_run",
  "id": "apirun_123",
  "status": "in_progress",
  "created_at": 1784763880,
  "agent_id": "agt_123",
  "api_trigger_id": "agtch_123",
  "conversation_url": "https://chatgpt.com/c/123",
  "error": null
}
```

| Status        | Description                                                      |
| ------------- | ---------------------------------------------------------------- |
| `queued`      | The trigger was accepted and is waiting to start.                |
| `in_progress` | The agent is running.                                            |
| `suspended`   | The agent is waiting for an external action or tool.             |
| `completed`   | The agent run completed successfully.                            |
| `failed`      | The agent run failed. See `error.code` for the failure category. |

`completed` and `failed` are terminal statuses. For failed runs, `error.code`
can be `dispatch_failed` or `run_failed`.

## Example

```bash
curl -i https://api.chatgpt.com/v1/workspace_agents/agtch_complaints_123/trigger \
  -X POST \
  -H "Authorization: Bearer $AGENT_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "OpenAI-Beta: workspace_agent_runs=v1" \
  -d '{
    "conversation_key": "email_thread_abc",
    "input": "Summarize the newest escalation and recommend next steps."
  }'
```

Expected response:

```text
HTTP/1.1 202 Accepted

{
  "conversation_url": "https://chatgpt.com/c/123",
  "agent_trigger_run_id": "apirun_123"
}
```

## Errors

| Status             | When returned                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `401 Unauthorized` | The bearer credential is missing, expired, revoked, or invalid.                            |
| `403 Forbidden`    | The token is valid but does not have permission to trigger the requested workspace agent.  |
| `404 Not Found`    | The trigger or run does not exist or is not visible to the caller's workspace.             |
| `409 Conflict`     | The trigger could not be accepted because the channel or agent is not in a runnable state. |