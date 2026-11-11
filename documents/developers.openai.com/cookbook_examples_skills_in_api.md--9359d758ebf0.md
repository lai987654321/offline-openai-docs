# Skills in OpenAI API

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Package a CSV analysis workflow as a skill, upload it, and run it with GPT-6 Astra in hosted shell. You can also expose the same files to a local shell runtime. For the full reference, see the [Skills documentation](https://developers.openai.com/api/docs/guides/tools-skills).

## What is a skill?

A skill is a reusable bundle of files (instructions + scripts + assets), packaged as a folder and anchored by a required `SKILL.md` manifest. OpenAI copies that bundle into an execution environment so the model can read instructions and run code as needed.

In hosted shell, here's what happens when you attach skills to the shell tool environment (`environment.type="container_auto"`):


- The service uploads and unzips skills into the runtime
- The service reads `SKILL.md` frontmatter (name/description), then adds each skill’s `name`, `description`, and `path` to user prompt context, which lets the model know the skill exists
- If the model decides to invoke a skill, it uses the `path` to read `SKILL.md`, then explores files and executes scripts via the shell tool

Skill instructions have the same priority as other user-provided instructions.

Skills are for procedures: repeatable workflows where the _how_ matters (steps, branching logic, formatting rules, scripts). Skills are useful for when you want your procedure:

- Reused across prompts/agents
- Versioned and independently shipped
- Invoked only when needed (not baked into every system prompt)

### When to use skills


**Skills are particularly appropriate and powerful when…**

1. **You want a reusable, independently versionable set of behaviors.**
Examples: “PowerPoint formatting procedure,” “company-specific report generator,” “standard data-cleaning pipeline.”
2. **Your workflow is highly conditional, or branches like a complex flow chart.**
Example: If X → do this; else if Y → do that; plus validation + retries.
3. **Your workflow needs code execution and local artifacts.**
Anything that benefits from scripts, templates, test fixtures, or reference assets that should live beside the instructions. Skills are designed as a zip of those resources.
4. **You want to keep system prompts slim.**
Put stable procedures in skills; keep system prompts for global behavior.
5. **Multiple agents or teams share the same “house style.”**
Skills are a nice “org standard library” pattern.
6. **You need reproducibility**
Skills are naturally compatible with version pinning via skill versions (see versioning section below).


**Skills are less ideal when…**

- It’s truly a **one-off** task (a quick inline script in the conversation is fine).
- You mostly need **live external data or side effects.** (That’s a tool/API call).
- The procedure changes every day (skills shine when the workflow stabilizes).


## Skills vs. tools vs. system prompts

System prompts and tool schemas become heavy when the boundary isn’t crisp. Use all three to stay organized and help models perform better. Here’s a simple framework:

**System prompt: global behavior and constraints**

Use for:
- Safety boundaries, tone, refusal style
- “Always do X” principles that apply every turn
- Small, stable policies

Avoid:

- Putting long, multi-step procedures here (it bloats every turn and becomes brittle)



**Tools: “do something in the world”**

Use tools when the model must:

- Call external services or databases
- Create side effects (tasks outside of the environment, like canceling an order or sending an email)
- Fetch live state

Tools should:

- Be narrowly scoped
- Have strongly typed inputs
- Be explicit about side effects

**Skills: packaged procedures (+ code + assets)**

Use a skill when you want the model to:

- Follow a repeatable workflow
- Use scripts/templates
- Execute code in a sandbox
- Do it sometimes, not always


## Skill packaging: SKILL.md and folder layout

### Folder structure

A skill is just a folder bundle. Here's an example:
- `SKILL.md` (required)
- Scripts, like `*.py`, `*.js` (optional)
- Helpers and `requirements.txt`
- Assets, templates, sample inputs


### SKILL.md frontmatter

OpenAI models expect names and descriptions to come from frontmatter (important for discovery and routing). Put name and description in the `SKILL.md` frontmatter. Use each API `create` call to upload one skill bundle (one top-level folder) containing exactly one `SKILL.md`/`skill.md`. To upload multiple skills, upload multiple bundles.


## Creating skills via API

After you assemble your skill in a folder, create the skill with an API call.

### Directory upload or zip upload


Use `POST /v1/skills` to upload and validate your skill, extracting name and description from the manifest frontmatter. You can either upload a zip bundle or upload multiple files in your request.

**Option A: Upload files (multipart)**



```bash
curl --fail-with-body 'https://api.openai.com/v1/skills' \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F 'files[]=@./csv_insights_skill/SKILL.md;filename=csv_insights_skill/SKILL.md;type=text/markdown' \
  -F 'files[]=@./csv_insights_skill/run.py;filename=csv_insights_skill/run.py;type=text/plain' \
  -F 'files[]=@./csv_insights_skill/requirements.txt;filename=csv_insights_skill/requirements.txt;type=text/plain' \
  -F 'files[]=@./csv_insights_skill/assets/example.csv;filename=csv_insights_skill/assets/example.csv;type=text/csv'
```

**Option B: Upload zip**

```
curl -X POST 'https://api.openai.com/v1/skills' \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F 'files=@./csv_insights_skill.zip;type=application/zip'
```

Use one upload method per skill. A zip keeps the instructions, script, dependencies, and sample input together.



**Skill object and version pointers**

The response includes the skill `id`, `default_version`, and `latest_version`. Save the `id` and a version to attach the uploaded skill to hosted shell.

## Mounting skills into execution

To use skills in the Responses API, attach them to the shell tool with `tools[].environment.skills`.

### How to reference skills

- **Hosted shell** (`environment.type="container_auto"`): use `skill_reference` with a `skill_id` and optional `version`, or an `inline` base64 zip bundle.
- **Local shell** (`environment.type="local"`): provide `name`, `description`, and `path` for files available in your runtime. Local shell does not accept hosted `skill_reference` attachments. Your application executes the requested commands and returns their outputs.

## Runnable example: `csv_insights_skill` Skill

This walkthrough creates files on disk and then runs Python snippets; it is not a notebook to execute with **Run All**. Save the script below as `csv_insights_skill/run.py`.

Prerequisites: Python 3.10 or later, `curl`, `zip`, and an `OPENAI_API_KEY` environment variable for a project with access to `gpt-6-astra` and hosted shell. Install the current Python SDK with `python -m pip install --upgrade openai`.

The upload commands create a skill in your API project. Responses API calls incur [model and container charges](https://developers.openai.com/api/docs/pricing). The Python API examples are disabled unless you set `RUN_SKILLS_API=1`. Run the local checks first, then opt in when you are ready to make API requests.

**1) Create the skill folder and sample input.**

```bash
mkdir -p csv_insights_skill/assets
```

The finished folder should contain:

```text
csv_insights_skill/
├── SKILL.md
├── requirements.txt
├── run.py
└── assets/
    └── example.csv
```

Save these dependencies as `csv_insights_skill/requirements.txt`. `tabulate` is required by pandas' `to_markdown()` method.

```text
pandas
matplotlib
tabulate
```

Save this synthetic input as `csv_insights_skill/assets/example.csv`:

```csv
quantity,price,category
2,10,books
3,15,games
,20,books
```


**2) Create your `SKILL.md`**

```
---
name: csv-insights
description: Summarize a CSV, compute basic stats, and produce a markdown report + a plot image.
---

# CSV Insights Skill

## When to use this
Use this skill when the user provides a CSV file and wants:
- a quick summary (row/col counts, missing values)
- basic numeric statistics
- a simple visualization
- results packaged into an output folder (or zip)

## Inputs
- A CSV file path (local) or a file mounted in the container.

## Outputs
- `output/report.md`
- `output/plot.png` (when the CSV has a numeric column)

## How to run

Run from the directory containing this SKILL.md. The environment must have
pandas, matplotlib, and tabulate installed. If a dependency is unavailable,
report it rather than attempting an unapproved network install.

python run.py --input assets/example.csv --outdir output

Use the output directory requested by the user when one is provided.
Check that report.md exists and that plot.png exists for numeric input.

```

**3) Create your `run.py`**

```python
import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def write_report(df: pd.DataFrame, outpath: Path) -> None:
    lines = []
    lines.append(f"# CSV Insights Report\n")
    lines.append(f"**Rows:** {len(df)}  \n**Columns:** {len(df.columns)}\n")
    lines.append("\n## Columns\n")
    lines.append("\n".join([f"- `{c}` ({df[c].dtype})" for c in df.columns]))

    missing = df.isna().sum()
    if missing.any():
        lines.append("\n## Missing values\n")
        for col, count in missing[missing > 0].items():
            lines.append(f"- `{col}`: {int(count)}")
    else:
        lines.append("\n## Missing values\nNo missing values detected.\n")

    numeric = df.select_dtypes(include="number")
    if not numeric.empty:
        lines.append("\n## Numeric summary (describe)\n")
        lines.append(numeric.describe().to_markdown())

    outpath.write_text("\n".join(lines), encoding="utf-8")


def make_plot(df: pd.DataFrame, outpath: Path) -> None:
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        # No numeric columns → skip plotting
        return

    # Plot the first numeric column as a simple histogram
    col = numeric.columns[0]
    plt.figure()
    df[col].dropna().hist(bins=30)
    plt.title(f"Histogram: {col}")
    plt.xlabel(col)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--outdir", required=True, help="Directory for outputs")
    args = parser.parse_args()

    inpath = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inpath)

    write_report(df, outdir / "report.md")
    make_plot(df, outdir / "plot.png")


if __name__ == "__main__":
    main()
```

**4) Test locally, then zip the skill.**

From the directory containing `csv_insights_skill`, install dependencies and run the script:

```bash
python -m pip install -r csv_insights_skill/requirements.txt
python csv_insights_skill/run.py --input csv_insights_skill/assets/example.csv --outdir local-output
```

`local-output/report.md` should report three rows, three columns, and one missing `quantity` value. `local-output/plot.png` should contain a histogram of `quantity`.

Package only the skill files, not the generated output:

```bash
zip -r csv_insights_skill.zip csv_insights_skill/SKILL.md csv_insights_skill/requirements.txt csv_insights_skill/run.py csv_insights_skill/assets
```

**5) Upload the skill (live API request).**

Run this command only when you are ready to create the skill. It saves the response to `skill.json` for the next step.

```bash
curl --fail-with-body 'https://api.openai.com/v1/skills' \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F 'files=@./csv_insights_skill.zip;type=application/zip' \
  -o skill.json
```

**6) Run the skill via hosted shell (live API request).**

Set `RUN_SKILLS_API=1`, then run this snippet from the same directory as `skill.json`. It pins the uploaded skill's default version and analyzes the CSV bundled inside the skill. No separate CSV upload is needed.

Hosted shell uses its installed dependencies; outbound network access is disabled by default. The skill reports missing dependencies rather than enabling network access automatically. Save downloadable artifacts under `/mnt/data`, as described in the [Shell guide](https://developers.openai.com/api/docs/guides/tools-shell#hosted-runtime-details).

```python
import json
import os
from pathlib import Path

from openai import OpenAI

if os.environ.get("RUN_SKILLS_API") == "1":
    client = OpenAI()
    skill = json.loads(Path("skill.json").read_text())
    response = client.responses.create(
        model="gpt-6-astra",
        tools=[
            {
                "type": "shell",
                "environment": {
                    "type": "container_auto",
                    "skills": [
                        {
                            "type": "skill_reference",
                            "skill_id": skill["id"],
                            "version": str(skill["default_version"]),
                        }
                    ],
                },
            }
        ],
        input=(
            "Use the csv-insights skill to analyze its bundled assets/example.csv. "
            "Run the skill's run.py and write outputs to /mnt/data/csv-insights-output. "
            "Verify the row count and missing values, and link to report.md and plot.png."
        ),
    )
    print(response.output_text)
else:
    print("Skipped live API request. Set RUN_SKILLS_API=1 to run.")
```

**7) Request a local shell call (optional, live API request).**

Local shell uses the files you created above, without uploading or referencing a hosted skill. Run this snippet from the directory containing `csv_insights_skill` in your execution environment.

This snippet only requests and displays commands. It does not execute them or complete the analysis. To complete the workflow, your application must review and execute `shell_call` commands in a sandbox, capture stdout, stderr, and the exit outcome, and return `shell_call_output` with the matching `call_id`. Continue until the model returns its final answer. See [Local shell mode](https://developers.openai.com/api/docs/guides/tools-shell#local-shell-mode) for the execution loop and output format.

```python
import os
from pathlib import Path

from openai import OpenAI

if os.environ.get("RUN_SKILLS_API") == "1":
    client = OpenAI()
    skill_path = Path("csv_insights_skill").resolve()
    response = client.responses.create(
        model="gpt-6-astra",
        tools=[
            {
                "type": "shell",
                "environment": {
                    "type": "local",
                    "skills": [
                        {
                            "name": "csv-insights",
                            "description": (
                                "Summarize a CSV, compute basic stats, and produce "
                                "a markdown report + a plot image."
                            ),
                            "path": str(skill_path),
                        }
                    ],
                },
            }
        ],
        input=(
            "Use the csv-insights skill to analyze its bundled assets/example.csv "
            "and write outputs to local-output."
        ),
    )
    for item in response.output:
        if item.type == "shell_call":
            print(item.action.commands)
    print(response.output_text)
else:
    print("Skipped live API request. Set RUN_SKILLS_API=1 to run.")
```

## Operational best practices

**1) Keep skills “discoverable”**

* Put a **clear** `name` and `description` in frontmatter.
* In `SKILL.md`, include: when to use, how to run, expected outputs, gotchas.

- Add explicit routing guidance: “Use when…” vs. “Don’t use when…”, and a few key edge cases, all in `SKILL.md`.

- Include negative examples (when the skill should *not* be triggered) alongside positive examples to improve routing accuracy.

- If routing feels inconsistent, iterate on name, description, and examples before changing code.

This came up in “bulk upload” discussions: name and description should come from frontmatter, and you should test with a small number first.

**2) Prefer zip uploads for reliability and reproducibility**

* Zips are portable, easy to version, and a useful workaround when uploads misbehave.

**3) Version pin in production**

You want to be able to say, “Run this procedure version,” not, “Run whatever the latest is.” Uploaded skills have **default_version** and **latest_version** pointers. Create new versions with `POST /v1/skills/{skill_id}/versions`; see [versioning and management](https://developers.openai.com/api/docs/guides/tools-skills#versioning-and-management).

* How to pin: `version: "2"`
* How to float: `version: "latest"`
* What happens when omitted: defaults to `default_version`

Consider pinning the model and skill version together for reproducible behavior across deployments.

**4) Design skills like tiny CLIs**

A good skill script:

* Runs from the command line
* Prints deterministic stdout
* Fails loudly with usage/errors
* Writes outputs to known file paths when needed

Add concrete templates and worked examples inside the skill (inputs → commands → expected outputs); the model reads these details when it invokes the skill, while discovery metadata remains part of the input context. When examples are workflow-specific, prefer examples and templates in skills over system-level, few-shot prompting.

**5) Avoid duplicating skills in system prompts**

If the system prompt repeats the entire procedure, people will:

* Bypass skills
* Stuff logic into tool schemas

And you lose the whole point (reusability + versioning + conditional invocation) of skills. Keep the system prompt content separate.

**6) Network access**

Combining skills and open network access is high-risk. If you must use network access, use strict allowlists and treat tool output as untrusted. Avoid this configuration for consumer-facing apps where users expect confirmation controls.
**If network access is required, pair allowlists with explicit “what data is allowed to leave” guidance.**

**7) Use a model that reliably executes multi-step workflows**

Skills work best when the model is strong at long-context reasoning and multi-step tool execution (filesystem navigation, CLI runs, verification).
If you see partial completion or brittle execution, upgrade the model or simplify the workflow, and add explicit verification steps and output checks in `SKILL.md`.

**Limits and validation**

- `SKILL.md` matching is case-insensitive
- Exactly one manifest file allowed (`skill.md`/`SKILL.md`)
- Frontmatter validation follows Agent Skills spec (name field)
- Max zip upload size: 50 MB
- Max file count per skill version: 500
- Max uncompressed file size: 25 MB

## Conclusion

Skills are the missing “middle layer” between prompts and tools: **prompts** define always-on behavior, **tools** provide atomic capabilities and side effects, and **skills** package repeatable procedures (instructions + scripts + assets) that the model can **mount and execute only when needed.**

**Use skills to keep your system prompts lean and your workflows durable.** Start small—bundle one stable procedure with a clear `SKILL.md`, make it runnable as a tiny CLI, and ship it. After it’s in production, pin versions for reproducibility, iterate safely by publishing new versions, and treat your skills library like an internal standard library: audited, discoverable, and shared across agents.

As users scale from single-turn assistants to long-running agents, skills help turn “prompt spaghetti” into **maintainable, testable, versioned workflows**—for building agentic behavior you can trust, reuse, and evolve over time.

To get started with Skills, check out our [documentation](https://developers.openai.com/api/docs/guides/tools-skills).