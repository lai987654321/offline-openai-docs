# OpenAI Developers plugin

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

The OpenAI Developers plugin helps you build AI applications and agents in
ChatGPT and Codex with OpenAI Platform access and OpenAI API setup guidance.
ChatGPT and Codex share its listing in the universal plugin directory.
Adaptations for Claude Code and Cursor bundle the portable developer skills and
public OpenAI Docs MCP server without the Codex-specific Platform connector. In
Codex, the plugin works with the OpenAI Docs skill bundled with your install.

It includes:

- **OpenAI API Platform:** connect ChatGPT or Codex to the
  [OpenAI API Platform](https://platform.openai.com/).
- **OpenAI Docs MCP:** use current OpenAI documentation from Claude Code or
  Cursor.
- **API key setup:** create, save, and connect a project API key from Codex, or
  get guided local `OPENAI_API_KEY` setup in Claude Code and Cursor.
- **Agents SDK:** build and deploy OpenAI Agents SDK apps from an idea, a repo,
  or a prior Codex task.
- **API migration:** when your installation includes the migration skill, migrate
  existing LLM apps and agents to OpenAI or improve their Responses API
  integration through changes designed to preserve behavior and improve
  performance and efficiency. Apply agreed changes incrementally without
  requiring a full rewrite.
- **Troubleshooting:** identify common OpenAI API failures and route
  you to the right next step.

## Get started with Codex

If you are new to Codex, start here before installing the plugin:

1. [Download the ChatGPT desktop app](https://developers.openai.com/codex/app#getting-started) for macOS or Windows.
2. Follow the [Codex quickstart](https://developers.openai.com/codex/quickstart) to sign in, choose a
   project, and send your first message.

## Install the plugin



  

    [Install the OpenAI Developers plugin](codex://plugins/install/openai-developers?marketplace=openai-curated)
  


  

    

    1. Open Codex

       Start Codex from your terminal:

       ```bash
       codex
       ```


    2. Open the plugin browser

       Run:

       ```text
       /plugins
       ```


    3. Install the plugin

       Search for **OpenAI Developers**, open it, and select `Install plugin`.

    4. Complete any setup prompts

       If Codex asks you to connect the bundled OpenAI Platform app, complete
       that setup so the plugin can create project API keys when needed.

    5. Start a new chat

       Start a new chat before using the plugin for the first time.
    


  


  

    

    1. Open the plugin settings

       In the Claude app, open **Settings**, then select **Plugins**.

    2. Add the marketplace

       Select **Add** in the top-right corner, then choose **Add Marketplace**.
       In the modal, select **Add from a repository**.

    3. Add the repository

       Enter `https://github.com/openai/openai-developers-for-claude` and select
       **Sync**. Do not append a `.git` suffix.

    4. Install the plugin

       When **OpenAI Developers** appears, open it and select **Install**.
    


  


  

    

    1. Add the plugin marketplace

       In Claude Code, run:

       ```text
       /plugin marketplace add openai/openai-developers-for-claude
       ```


    2. Install the plugin

       Run:

       ```text
       /plugin install openai-developers@openai-developers
       ```


    3. Start a new session

       Start a new Claude Code session before using the plugin for the first
       time.
    


  


  

    

    1. Open the plugin settings

       In Cursor, open **Settings**, then select **Plugins**.

    2. Add the repository

       Paste `https://github.com/openai/openai-developers-for-cursor` into the
       plugin search box.

    3. Install the plugin

       When **OpenAI Developers** appears, open it and select **Install**.
    


  




## Use the plugin

After installation, start building with your agent. ChatGPT or Codex can use
the plugin automatically when the task calls for OpenAI Platform interactions,
such as creating API keys or troubleshooting API issues. Claude Code and Cursor
can use the plugin's skills and bundled Docs MCP server for OpenAI API, model,
Agents SDK, and plugin guidance.

The plugin is useful when you want your coding agent to:

- build an app or agent that uses the OpenAI API
- set up OpenAI API access for the app you are building
- diagnose common OpenAI API errors and explain the next step.

### Migrate an existing app

When the migration skill is installed, try:

```text
Migrate this app to use OpenAI Responses API best practices.
```


## Sample prompts

<h3 className="not-prose mt-6 mb-3 text-base leading-6 font-medium text-default">
  Build a new app
</h3>



  <h3 className="not-prose mt-8 mb-3 text-base leading-6 font-medium text-default">
  Improve an existing app
</h3>