# Submit desktop-only plugins

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Desktop-only plugins require local execution on the user's computer. This includes
most plugins with a local (stdio) MCP server and plugins that call local programs.
They display a **Desktop only** badge in the OpenAI Plugin Directory and can only
be installed from the ChatGPT desktop app. Users can mention them only in threads
that run locally.

> **Approval required:** Local MCP submissions are limited to approved partners.
> Contact your OpenAI representative to confirm eligibility and have your
> submitting organization allowlisted before following these steps.

Before submitting, [package your plugin](https://developers.openai.com/plugins/build/plugins) and test a clean
desktop installation and its main workflows. Complete the standard
[submission prerequisites](https://developers.openai.com/plugins/deploy/submission#confirm-access-and-publishing-identity), including
submission access and developer or business identity verification.

## Configure a local MCP server

Use the same [plugin structure](https://developers.openai.com/plugins/build/plugins#plugin-structure) as any
other plugin. In root `mcp.json`, replace the HTTP server entry under `mcpServers`
with a stdio entry that defines the local launch command.

The server can use any language or runtime that supports MCP over stdio. For
example, a Node.js server entry could look like this:

```json
{
  "type": "stdio",
  "command": "node",
  "args": ["${PLUGIN_ROOT}/server/dist/index.js"],
  "cwd": "${PLUGIN_ROOT}"
}
```

Include the server and its dependencies in the package. `${PLUGIN_ROOT}` is a
built-in placeholder.

## Submit a plugin with a local MCP server

1. Find the submitting organization's ID in your [OpenAI Platform organization settings](https://platform.openai.com/settings/organization/general).
2. Send the ID to your OpenAI representative and ask them to have your
   organization allowlisted for local MCP submissions. Wait for confirmation
   before submitting.
3. Open the [plugin submission portal](https://platform.openai.com/plugins),
   select **Create plugin**, and choose **Skills only**. Use **Upload ZIP** to
   upload your plugin package, including its local MCP configuration.
4. Complete the [submission requirements](https://developers.openai.com/plugins/deploy/submission) and submit
   for review. After approval, publish from the portal.

## Plugins without an MCP server

If your skills-only plugin requires desktop execution, set
`requires_local_executor` to `true` in `extensions.com.openai` in your root
`plugin.json`:

```json
{
  "extensions": {
    "com.openai": {
      "requires_local_executor": true
    }
  }
}
```

For a legacy package using `.codex-plugin/plugin.json`, add
`"requires_local_executor": true` at the top level of that manifest instead.

This flag marks your plugin as **Desktop only**. Follow the
[standard submission flow](https://developers.openai.com/plugins/deploy/submission).
If the portal reports that the field isn't allowed, send your submitting
organization's ID to your OpenAI representative to confirm submission access.