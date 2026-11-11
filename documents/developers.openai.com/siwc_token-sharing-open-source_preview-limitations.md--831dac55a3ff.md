# Preview limitations

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Preview behavior and limitations

These limits apply to ChatGPT plan usage through Sign in with ChatGPT and `https://api.openai.com/v1`, both directly and through Codex app-server.

### Responses API requirements

- **HTTP requests:** Set `store: false` and `stream: true`. Send `input` as an array containing the context needed for each request. Use `instructions` or developer messages; explicit `{type: "message", role: "system"}` items are rejected.
- **Unsupported fields:** Omit `background`, `conversation`, `max_output_tokens`, `max_tool_calls`, `metadata`, `moderation`, `multi_agent`, `prompt`, `prompt_cache_retention`, `safety_identifier`, `temperature`, `top_logprobs`, `top_p`, `truncation`, and `user`.
- **Conversation state:** Omit `previous_response_id` over HTTP and send the required history in `input`. WebSocket continuation can reference only responses from the same authenticated connection; it does not provide persistent conversation storage.
- **Supported tools:** Group function/custom tools in namespaces or supply them through `additional_tools` input items. Web search remains subject to model and account/workspace policy.
- **Unsupported tools:** Image generation, file search, Code Interpreter, native computer use, hosted MCP/connectors, and Responses `tool_search`. Client-side execution does not make `tool_search` supported. `programmatic_tool_calling` is not accepted in top-level `tools` on this route.
- **Inputs:** Text, images, and files are supported when the selected model accepts them. Audio/video input, the Files upload API, and the transcription API are not supported by this flow.

### Codex app-server behavior

- **Transport:** The [Codex app-server configuration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server) uses stdio between your app and app-server, then HTTP/SSE to Responses. App-server sets `store: false` and `stream: true`; `supports_websockets=false` selects HTTP for this configuration.
- **Local tools and agents:** Codex can run shell and MCP tools and coordinate child agents through supported function/custom tool calls. These are separate from hosted Responses tools. Configurations that emit Responses `tool_search` will fail.
- **Inputs and history:** Use app-server's RPC inputs; it does not accept arbitrary Responses parameters. Local thread history and `thread/resume` still work with `store: false`.
- **Token renewal:** Your app must refresh the OAuth token. With the [`env_key` setup](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server#using-codex-app-server), restart app-server with the renewed `ACCESS_TOKEN`, then resume the saved thread.