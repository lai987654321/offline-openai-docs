# Docs MCP

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

OpenAI hosts a public Model Context Protocol (MCP) server for documentation on `developers.openai.com`, `platform.openai.com`, and `learn.chatgpt.com`.

**Server URL (streamable HTTP):** `https://developers.openai.com/mcp`

## What it provides

- Read-only access to OpenAI developer documentation (search + page content).
- A way to pull documentation into your agent's context while you work.

This MCP server is documentation-only. It does not call the OpenAI API on your
  behalf.

## Quickstart



  

    You can connect Codex to [MCP servers](https://developers.openai.com/codex/extend/mcp) in the [CLI](https://developers.openai.com/codex/cli) or [IDE extension](https://developers.openai.com/codex/ide). The configuration is shared between both so you only have to set it up once.

    Add the server using the Codex CLI:

```bash
codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp
```

    Verify it's configured:

```bash
codex mcp list
```

    Alternatively, you can add it in `~/.codex/config.toml` directly:

```toml
[mcp_servers.openaiDeveloperDocs]
url = "https://developers.openai.com/mcp"
```

    To have Codex reliably use the MCP server, add this snippet to your `AGENTS.md`:

```text
Always use the OpenAI developer documentation MCP server if you need to work with the OpenAI API, plugins, ChatGPT, Codex,… without me having to explicitly ask.
```

  


  

    VS Code supports MCP servers when using GitHub Copilot in Agent mode.

    Click the following link to add the Docs MCP to VS Code:

    Alternatively, you can manually add a `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "openaiDeveloperDocs": {
      "type": "http",
      "url": "https://developers.openai.com/mcp"
    }
  }
}
```

    To have VS Code reliably use the MCP server, add this snippet to your `AGENTS.md`:

```text
Always use the OpenAI developer documentation MCP server if you need to work with the OpenAI API, plugins, ChatGPT, Codex,… without me having to explicitly ask.
```

    Open Copilot Chat, switch to **Agent** mode, enable the server in the tools picker, and ask an OpenAI-related question like:

> Look up the request schema for Responses API tools in the OpenAI developer docs and summarize the required fields.

  


  

    Cursor has native MCP support and reads configuration from `mcp.json`.

    Install with Cursor:

    Alternatively, create a `~/.cursor/mcp.json` (macOS/Linux) and add:

```json
{
  "mcpServers": {
    "openaiDeveloperDocs": {
      "url": "https://developers.openai.com/mcp"
    }
  }
}
```

    To have Cursor reliably use the MCP server, add this snippet to your `AGENTS.md`:

```text
Always use the OpenAI developer documentation MCP server if you need to work with the OpenAI API, plugins, ChatGPT, Codex,… without me having to explicitly ask.
```

    Restart Cursor and ask Cursor's agent an OpenAI-related question like:

> Look up the request schema for Responses API tools in the OpenAI developer docs and summarize the required fields.

  


  

    Claude Code supports remote HTTP MCP servers through the `claude mcp` CLI.

    Add the Docs MCP server from the project where you use Claude Code:

```bash
claude mcp add --transport http openaiDeveloperDocs https://developers.openai.com/mcp
```

    Verify it's configured:

```bash
claude mcp list
```

    To make the server available across all Claude Code projects on your machine, add it with user scope:

```bash
claude mcp add --transport http --scope user openaiDeveloperDocs https://developers.openai.com/mcp
```

    In Claude Code, run `/mcp` to confirm the server is connected. Then ask an OpenAI-related question like:

> Look up the request schema for Responses API tools in the OpenAI developer docs and summarize the required fields.

  




## Tips

- If you don't have the snippet in the AGENTS.md file, you need to explicitly tell your agent to consult the Docs MCP server for the answer.
- If you have more than one MCP server, keep server names short and descriptive to aid the agent in selecting the server.

## OpenAI Docs Skill

If you use skills in your AI tooling, pair this MCP server with the
[OpenAI Docs Skill](https://github.com/openai/skills/blob/main/skills/.curated/openai-docs/SKILL.md).
It tells the agent to use Docs MCP tools first for OpenAI questions, then fall back to official OpenAI domains.

1. Install the skill from the [OpenAI skills repository](https://github.com/openai/skills).
2. Confirm you configured this Docs MCP server at `https://developers.openai.com/mcp`.
3. Enable the skill for your project or session in your agent tooling.
4. Ask OpenAI product/API questions and request citations so answers stay traceable to docs sources.