# Enabling Long-Term Agent Memory with Oracle AI Agent Memory

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/openai/openai-cookbook/blob/main/examples/vector_databases/oracle_db/deep_research_openai_agents.ipynb) [![Documentation](https://img.shields.io/badge/Documentation-Oracle%20AI%20Agent%20Memory-red?style=flat-square)](https://www.oracle.com/database/ai-agent-memory/)

**Framework:** OpenAI Agents SDK | **Web search:** Tavily | **Memory:** Oracle AI Agent Memory on Oracle AI Database

Long-running agent workflows often need more than short-term conversation replay. They need a way to remember durable findings, decisions, and reusable context across sessions, so the agent can continue from prior work instead of starting from scratch each time.

This notebook demonstrates an **Oracle-backed Session pattern for the OpenAI Agents SDK**. It is not a general-purpose OpenAI memory implementation. The Agents SDK `Session` interface stores short-term conversation history for the current agent loop; durable research findings are saved separately through explicit memory tools backed by Oracle AI Agent Memory.

The example uses a **deep research agent** for human genome exploration, but the core pattern is broader: combine OpenAI Agents SDK session persistence with a durable memory layer for reusable findings. The agent uses Tavily for live web research, stores OpenAI Agents SDK session items in Oracle AI Database, and saves durable findings through a dedicated `save_research_finding` tool.

## Why Long-Term Memory Matters

Short-term session memory helps an agent keep the current conversation coherent. Long-term memory solves a different problem: it lets an agent preserve selected findings across sessions, resume prior work, and avoid rediscovering facts that were already researched.

For this example, session items and durable findings have different lifecycles. Session items are raw conversation state used for replay inside the agent loop. Durable findings are curated, searchable conclusions that the agent deliberately saves through a tool.

Oracle AI Agent Memory fits this pattern when an application already operates on Oracle AI Database and needs governed durable memories, semantic search over saved findings, and scoped access to both short-term session replay and long-term memory on one database-backed substrate.

---

## Operational Modes in Agent Applications

AI agent applications generally fall into three operational modes:

| Mode | Shape | Typical use |
|---|---|---|
| **Assistant** | Turn-by-turn conversational | Customer support, coding copilot, chat UIs |
| **Deep Research** | Multi-step autonomous investigation | Literature review, market research, technical scoping |
| **Workflow** | Predetermined sequence of steps, often with conditional branches | Approval pipelines, compliance checks, structured triage |

> **Note:** This notebook focuses on the Deep Research mode.
>
> A deep-research agent plans, retrieves, synthesises, and accumulates findings over long-horizon investigations. Memory is central, but not all memory has the same lifecycle: session items support short-term continuity, while durable findings are curated facts the agent can reuse across sessions.


## What You'll Learn

- How to implement the **OpenAI Agents SDK `Session` protocol** against a custom backend (Oracle AI Agent Memory)
- How to wrap **Tavily** as a `function_tool` the agent can call
- How to store long-lived research findings as durable **memories** (separate from short-term conversation history)
- How to verify memory continuity across sessions — the agent can pick up where it left off

> **💡 Key insight:** Short-term memory (conversation history for the current run) and long-term memory (durable findings across runs) are different access patterns over the same store. We use `Session` for the former and `add_memory()` for the latter.

## Prerequisites

- **Python 3.10 or 3.11** recommended for this notebook
- **Oracle AI Database** running locally (Docker container) or reachable over the network
- **`OPENAI_API_KEY`** for the agent's LLM and embeddings
- **`TAVILY_API_KEY`** for web search (free tier available at [tavily.com](https://tavily.com))
- The `oracleagentmemory`, `litellm`, `openai-agents`, `tavily-python`, `python-dotenv`, and `nest_asyncio` packages installed in the active kernel's environment

If you run this notebook in Colab, the Oracle database must be reachable from the Colab runtime. Colab cannot reach a Docker database on your laptop via `localhost`; expose the database through a reachable host/network path, or run the notebook locally next to the Docker container.

For a local Oracle Database Free Docker container with port `1521` exposed, the DSN usually looks like `localhost:1521/FREEPDB1`. If your container maps Oracle's listener to a different host port, use that host port in `ORACLE_DSN`. Wait until the container reports `DATABASE IS READY TO USE!` before running the connection cell.

Create a `.env` file next to the notebook or set these variables in your shell:

```env
OPENAI_API_KEY=
TAVILY_API_KEY=
ORACLE_USER=
ORACLE_PASSWORD=
ORACLE_DSN=
# Optional: set OPENAI_MODEL to use a different OpenAI model
# OPENAI_MODEL=
```

The notebook also accepts the legacy aliases `DB_USER`, `DB_PASSWORD`, and `DB_CONNECT_STRING`, but the Oracle-style names above are preferred.


## 1. Install dependencies

We install the notebook dependencies: `oracleagentmemory` for Oracle-backed memory, `litellm` for the embedding path used by Oracle AI Agent Memory, `openai-agents` for the Agents SDK runtime, `tavily-python` for web search, `python-dotenv` for environment variables, and `nest_asyncio` so `Runner.run` works cleanly inside a Jupyter event loop.

Dependency boundary: `openai-agents` provides the Agents SDK runtime and session protocol, while `litellm` is used by Oracle AI Agent Memory for embeddings and semantic search over durable findings. A plain Agents SDK session implementation does not require Oracle's long-term memory path.


```python
%%capture
%pip install -q oracleagentmemory litellm openai-agents tavily-python nest_asyncio python-dotenv
```

## 2. Configure API keys and Oracle connection

Load configuration from `.env` or environment variables. This notebook intentionally does **not** provide default credentials. If a required value is missing, it prompts you for it rather than embedding secrets in the notebook.

Required values:

- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `ORACLE_USER` or `DB_USER`
- `ORACLE_PASSWORD` or `DB_PASSWORD`
- `ORACLE_DSN` or `DB_CONNECT_STRING`

```python
import os
import getpass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the current working directory or notebook directory.
load_dotenv()
load_dotenv(Path.cwd() / ".env")


def _read_setting(primary: str, *aliases: str, secret: bool = False) -> str:
    """Read a required setting from env vars, falling back to a notebook prompt."""
    for key in (primary, *aliases):
        value = os.getenv(key)
        if value:
            os.environ[primary] = value
            return value

    prompt = f"Enter {primary}: "
    value = getpass.getpass(prompt) if secret else input(prompt)
    if not value:
        raise RuntimeError(f"Missing required setting: {primary}")
    os.environ[primary] = value
    return value


OPENAI_API_KEY = _read_setting("OPENAI_API_KEY", secret=True)
TAVILY_API_KEY = _read_setting("TAVILY_API_KEY", secret=True)
DB_USER = _read_setting("DB_USER", "ORACLE_USER")
DB_PASSWORD = _read_setting("DB_PASSWORD", "ORACLE_PASSWORD", secret=True)
DB_CONNECT_STRING = _read_setting("DB_CONNECT_STRING", "ORACLE_DSN")
MODEL = os.getenv("OPENAI_MODEL") or "gpt-5.4"

# Keep later cells consistent if a notebook user updates these Python variables directly.
os.environ.update({
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "TAVILY_API_KEY": TAVILY_API_KEY,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_CONNECT_STRING": DB_CONNECT_STRING,
})

# Jupyter runs an async event loop already; this lets us call async SDK methods cleanly.
import nest_asyncio
nest_asyncio.apply()

print("Configuration loaded from environment variables or prompts.")
print("OpenAI model configured.")
```

```text
Configuration loaded from environment variables or prompts.
OpenAI model configured.
```

## 3. Connect to Oracle AI Database and initialise the memory client

`OracleAgentMemory` is the governed memory client. In this notebook, automatic extraction is disabled so the separation is explicit:

- **Session items** are short-term OpenAI Agents SDK conversation state used for replay.
- **Research findings** are durable memories written only through the `save_research_finding` tool.

We use `text-embedding-3-small` for semantic search over durable findings.

> **💡 Key insight:** `schema_policy` controls how the library interacts with the DB on startup. `REQUIRE_EXISTING` never issues DDL. `CREATE_IF_NECESSARY` fills in missing objects and is safer for demos and development. `RECREATE` drops and rebuilds objects and should not be the default in a shared schema.

```python
import oracledb
from oracleagentmemory.core import OracleAgentMemory
from oracleagentmemory.core.dbschemapolicy import SchemaPolicy

connection = oracledb.connect(
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    dsn=os.environ["DB_CONNECT_STRING"],
)
print("Connected to Oracle AI Database.")

memory_client = OracleAgentMemory(
    connection=connection,
    embedder="text-embedding-3-small",   # OpenAI-compatible; 1536 dims
    extract_memories=False,               # durable findings are saved explicitly via tool calls
    schema_policy=SchemaPolicy.CREATE_IF_NECESSARY,
    table_name_prefix="genome_",         # isolates this example's tables from others
)
print("Memory client ready with safe schema policy:", SchemaPolicy.CREATE_IF_NECESSARY.value)
```

```text
Connected to Oracle AI Database.
Memory client ready with safe schema policy: create_if_necessary
```

## 4. Register the research user and agent

Use a unique run scope so rerunning the notebook does not mix old demo memories with the current run. This keeps `CREATE_IF_NECESSARY` safe while avoiding stale long-term findings from previous executions.

```python
from datetime import datetime, timezone

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
USER_ID = f"genome-researcher-{RUN_ID}"
AGENT_ID = f"deep-research-agent-{RUN_ID}"

for create_fn, eid, info in [
    (memory_client.add_user, USER_ID, "Genomics researcher exploring human disease associations."),
    (memory_client.add_agent, AGENT_ID, "Deep-research agent with web search and long-term memory."),
]:
    try:
        create_fn(eid, info)
        print(f"Registered: {eid}")
    except ValueError:
        print(f"Already exists: {eid}")

print(f"Run scope: {RUN_ID}")
```

```text
Registered: genome-researcher-20260715083601
Registered: deep-research-agent-20260715083601
Run scope: 20260715083601
```

## 5. Implement the `Session` protocol on top of Oracle AI Agent Memory

The OpenAI Agents SDK `Session` protocol handles **short-term session persistence**: the runner asks for previous items and appends new items during the agent loop.

In this implementation, session items are stored as Oracle Agent Memory `message` records with `metadata={"session_item": true}`. They are scoped by `session_id`, `user_id`, and `agent_id`, and they are used only for replaying the conversation. Durable long-term findings are stored separately as `memory` records through the `save_research_finding` tool.

> **Important:** Raw model/tool messages can be large and noisy. They should not appear as long-term research findings unless a tool deliberately promotes a concise conclusion.

```python
import json
from typing import Optional
from agents.memory.session import SessionABC


class OracleAgentMemorySession(SessionABC):
    """Session backend that persists OpenAI Agents SDK items in Oracle AI Database.

    Session items are short-term replay state stored as message records. Durable
    research findings are saved separately via the save_research_finding tool.
    """

    def __init__(self, session_id: str, client: OracleAgentMemory, user_id: str, agent_id: str):
        self.session_id = session_id
        self._client = client
        self._store = client._store
        self._user_id = user_id
        self._agent_id = agent_id
        try:
            self._client.create_thread(
                thread_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                extract_memories=False,
            )
        except ValueError:
            pass  # thread already exists
        self._next_session_seq = self._load_next_session_seq()

    async def get_items(self, limit: Optional[int] = None) -> list:
        records = self._session_records()
        ordered = sorted(records, key=self._session_sort_key)
        if limit:
            ordered = ordered[-limit:]
        return [json.loads(r.content) for r in ordered]

    async def add_items(self, items: list) -> None:
        if not items:
            return
        start_seq = self._next_session_seq
        metadata = [
            {
                "session_item": True,
                "session_id": self.session_id,
                "session_seq": start_seq + offset,
            }
            for offset, _ in enumerate(items)
        ]
        self._store.add(
            contents=[json.dumps(item) for item in items],
            record_type="message",
            thread_ids=self.session_id,
            user_ids=self._user_id,
            agent_ids=self._agent_id,
            roles=[self._message_role(item) for item in items],
            metadata=metadata,
        )
        self._next_session_seq = start_seq + len(items)

    async def pop_item(self) -> Optional[dict]:
        records = self._session_records()
        if not records:
            return None
        last = max(records, key=self._session_sort_key)
        self._store.delete("message", last.id)
        return json.loads(last.content)

    async def clear_session(self) -> None:
        records = self._session_records()
        for r in records:
            self._store.delete("message", r.id)
        self._next_session_seq = 0

    def _session_records(self) -> list:
        return self._store.list(
            "message",
            thread_id=self.session_id,
            user_id=self._user_id,
            agent_id=self._agent_id,
            limit=10_000,
            metadata_filter={"session_item": True},
        )

    def _load_next_session_seq(self) -> int:
        seqs = [self._session_seq(r) for r in self._session_records()]
        seqs = [seq for seq in seqs if seq is not None]
        return max(seqs) + 1 if seqs else 0

    @staticmethod
    def _record_metadata(record) -> dict:
        metadata = getattr(record, "metadata", None) or {}
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except json.JSONDecodeError:
                return {}
        return metadata if isinstance(metadata, dict) else {}

    @classmethod
    def _session_seq(cls, record) -> Optional[int]:
        seq = cls._record_metadata(record).get("session_seq")
        try:
            return int(seq)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _session_sort_key(cls, record) -> tuple:
        seq = cls._session_seq(record)
        if seq is not None:
            return (1, seq)
        # Fallback only covers records created before this notebook stored session_seq.
        created_at = getattr(record, "created_at", "") or ""
        return (0, str(created_at), str(getattr(record, "id", "")))

    @staticmethod
    def _message_role(item: dict) -> str:
        role = item.get("role") if isinstance(item, dict) else None
        if role in {"user", "assistant", "system", "tool"}:
            return role
        return "user"
```

## 6. Define the agent's tools

The agent needs three tools:

1. **`tavily_search`** — live web search for up-to-date genomics sources
2. **`save_research_finding`** — persist a durable research note the agent can recall in future sessions
3. **`recall_research_findings`** — search the long-term memory for prior findings on a topic

Tools 2 and 3 are how the agent manages its **long-term** memory. They're distinct from the `Session` machinery, which handles short-term conversation history automatically.

> **📌 The `@function_tool` decorator** auto-generates the tool's JSON schema from Python type hints and parses the docstring for the description the LLM sees. Write informative docstrings — the LLM reads them.

```python
from agents import function_tool
from tavily import TavilyClient

_tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

@function_tool
def tavily_search(query: str, max_results: int = 5) -> str:
    """Search the live web for recent, authoritative genomics sources.

    Use this to pull current information from NCBI, OMIM, peer-reviewed journals,
    and other scientific sources. Prefer this over relying on model-internal knowledge
    for facts about specific genes, mutations, or recent studies.

    Args:
        query: Natural-language search query.
        max_results: How many results to return (1-10).
    """
    resp = _tavily.search(
        query=query, max_results=max_results,
        search_depth="advanced", include_answer=True,
    )
    lines = [f"Answer: {resp.get('answer', '')}"]
    for r in resp.get("results", []):
        lines.append(f"- {r['title']} ({r['url']})\n  {r['content'][:300]}")
    return "\n".join(lines)


@function_tool
def save_research_finding(topic: str, finding: str) -> str:
    """Persist a durable research finding the agent should recall in future sessions.

    Use this for claims worth remembering across sessions, for example: "BRCA1
    pathogenic variants are associated with substantially elevated lifetime breast
    cancer risk." Do not use this for conversational acknowledgements, raw tool
    output, or speculation.

    Args:
        topic: Short topic tag (e.g. 'BRCA1', 'TP53 mutations').
        finding: The finding to remember, ideally one sentence.
    """
    memory_id = memory_client.add_memory(
        f"[{topic}] {finding}",
        user_id=USER_ID,
        agent_id=AGENT_ID,
        metadata={"topic": topic, "kind": "research_finding", "durable": True},
    )
    return f"Saved durable research finding (id={memory_id})."


@function_tool
def recall_research_findings(query: str, max_results: int = 5) -> str:
    """Search prior durable research findings for information relevant to a query.

    Use this at the start of a research task to check what is already known.
    Results are ranked by semantic similarity.

    Args:
        query: Natural-language query describing what you want to recall.
        max_results: How many findings to return.
    """
    results = memory_client.search(
        query,
        user_id=USER_ID,
        agent_id=AGENT_ID,
        exact_user_match=True,
        exact_agent_match=True,
        max_results=max_results,
        record_types=["memory"],
    )
    if not results:
        return "(no prior durable findings)"
    return "\n".join(
        f"- {r.content}  [distance={r.distance:.3f}]" for r in results
    )


print("Tools defined: tavily_search, save_research_finding, recall_research_findings")
```

```text
Tools defined: tavily_search, save_research_finding, recall_research_findings
```

## 7. Construct the research agent

The agent's `instructions` are its system prompt — the place to encode the behaviour you want. For a deep-research agent, the instructions should emphasise:

1. **Recall before research** — check long-term memory before hitting the web
2. **Cite sources** — so findings are traceable
3. **Save what's worth remembering** — commit durable conclusions explicitly

> **💡 Key insight:** A deep-research agent's output quality is largely determined by how well its instructions distinguish *research* (retrieve + synthesise) from *conversation* (respond + acknowledge). Encode that distinction in the system prompt.

```python
from agents import Agent, Runner

INSTRUCTIONS = """You are a deep-research agent specialising in human genome exploration.

For every research question:
1. FIRST call `recall_research_findings` to check what is already known from prior sessions.
2. If the prior findings are insufficient or outdated, call `tavily_search` for current sources.
3. Synthesise a clear, cited answer. Prefer authoritative sources (NCBI, OMIM, PubMed).
4. Call `save_research_finding` for each durable conclusion worth remembering across sessions.
   Save one finding per call; keep findings atomic and one sentence long.
5. Present the final answer to the user with inline citations (URLs).

Do not save conversational acknowledgements as findings. Only save factual conclusions.
"""

research_agent = Agent(
    name="GenomeDeepResearcher",
    instructions=INSTRUCTIONS,
    tools=[tavily_search, save_research_finding, recall_research_findings],
    model=MODEL,
)
print(f"Agent created: {research_agent.name}")
```

```text
Agent created: GenomeDeepResearcher
```

## 8. Run a research session

We create a session (tied to a `thread_id` in the memory store) and run the agent over a sequence of research questions. Because we pass `session=session`, the SDK will automatically inject prior conversation items at the start of each turn and persist new items at the end.

> **📌 Separation of concerns.**
> - The `Session` persists the **raw conversation** (working memory).
> - The agent's `save_research_finding` tool persists **durable findings** (long-term memory).
> Both live in the same Oracle database but are accessed through different interfaces.

Because this example uses live web search and model generation, exact wording, citations, and ranking may vary between runs. The important behavior to verify is that the agent recalls durable findings before researching, cites sources, and saves new findings explicitly through the memory tool.


```python
from IPython.display import Markdown, display


def _notebook_text(text: str) -> str:
    """Normalize model text so GitHub, VS Code, and terminals render it consistently."""
    return (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


SESSION_ID = f"genome-session-{RUN_ID}-001"
session = OracleAgentMemorySession(
    session_id=SESSION_ID,
    client=memory_client,
    user_id=USER_ID,
    agent_id=AGENT_ID,
)

research_questions = [
    "What is BRCA1 and what is its primary function in DNA repair?",
    "What is the typical lifetime breast cancer risk associated with pathogenic BRCA1 variants?",
    "How does BRCA1 interact with BRCA2 in homologous recombination?",
]

session_sections = []
for i, q in enumerate(research_questions, 1):
    result = await Runner.run(research_agent, q, session=session)
    session_sections.append(f"### Q{i}: {q}\n\n{_notebook_text(result.final_output.strip())}")

display(Markdown("\n\n---\n\n".join(session_sections)))
```

### Q1: What is BRCA1 and what is its primary function in DNA repair?

BRCA1 is a human tumor suppressor gene that encodes a nuclear protein important for maintaining genomic stability [(NCBI Gene)](https://www.ncbi.nlm.nih.gov/datasets/gene/672).

Its primary DNA-repair function is to help repair DNA double-strand breaks through homologous recombination, a high-fidelity repair pathway. BRCA1 helps coordinate this process by acting at sites of DNA damage and supporting RAD51-mediated repair together with BRCA2 [(NCBI GeneReviews)](https://www.ncbi.nlm.nih.gov/books/NBK1247) [(NCBI Gene)](https://www.ncbi.nlm.nih.gov/datasets/gene/672).

---

### Q2: What is the typical lifetime breast cancer risk associated with pathogenic BRCA1 variants?

The typical estimate is about 55%-72% lifetime breast cancer risk for women with a pathogenic germline BRCA1 variant by age 70 [(NCBI GeneReviews)](https://www.ncbi.nlm.nih.gov/books/NBK1247).

For context, this is much higher than the roughly 12% general-population lifetime risk cited in the same source [(NCBI GeneReviews)](https://www.ncbi.nlm.nih.gov/books/NBK1247).

---

### Q3: How does BRCA1 interact with BRCA2 in homologous recombination?

BRCA1 and BRCA2 act in the same homologous recombination pathway, but they do different jobs.

BRCA1 acts earlier, helping organize the DNA-damage response and promote repair at double-strand breaks. BRCA2 acts later, mainly by controlling RAD51 loading onto single-stranded DNA so RAD51 can form the repair filament needed for strand invasion [(NCBI GeneReviews)](https://www.ncbi.nlm.nih.gov/books/NBK1247).

A key connection between them is PALB2, which physically links BRCA1 and BRCA2. Through PALB2, BRCA1 helps recruit or stabilize the BRCA2-RAD51 machinery at DNA damage sites, allowing efficient homologous recombination [(Nature/PMC review)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4972490) [(PNAS)](https://www.pnas.org/doi/10.1073/pnas.0811159106).

So, in short: BRCA1 helps set up homologous recombination, and BRCA2 helps execute RAD51-dependent repair, with PALB2 bridging the two [(NCBI GeneReviews)](https://www.ncbi.nlm.nih.gov/books/NBK1247) [(PMC review)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4972490).

## 9. Inspect what the agent remembered

At this point the agent has accumulated two different kinds of records:

- **Short-term session items**: raw OpenAI Agents SDK items that replay the conversation for the current session.
- **Durable research findings**: concise conclusions the agent deliberately saved through `save_research_finding`.

The two lists should look different. Session items may include user messages, tool calls, and tool outputs. Durable findings should be short, factual, reusable research notes — not raw `call_id` JSON or full tool output.

```python
# Short-term: conversation items replayed each turn.
session_items = await session.get_items()

# Long-term: durable findings the agent deliberately chose to save.
findings = await memory_client.search_async(
    "BRCA1 function and risk",
    user_id=USER_ID,
    agent_id=AGENT_ID,
    exact_user_match=True,
    exact_agent_match=True,
    max_results=10,
    record_types=["memory"],
)


def _split_finding(content: str) -> tuple[str, str]:
    content = _notebook_text(str(content)).strip()
    if content.startswith("[") and "]" in content:
        topic, finding = content[1:].split("]", 1)
        return topic.strip(), finding.strip()
    return "Research finding", content


raw_json_leaks = [r for r in findings if str(r.content).lstrip().startswith("{")]
quality_note = (
    "Clean saved memories only; raw tool or session JSON was not saved."
    if not raw_json_leaks
    else "Review needed: raw tool or session JSON was saved."
)

summary = (
    "### Memory inspection\n\n"
    f"- Short-term session items stored: `{len(session_items)}`\n"
    f"- Durable research findings saved: `{len(findings)}`\n"
    f"- Stored content quality: {quality_note}\n"
)

rows = ["| Topic | Saved finding |", "|---|---|"]
for record in findings:
    topic, finding = _split_finding(record.content)
    rows.append(f"| {topic} | {finding} |")

display(Markdown(summary + "\n" + "\n".join(rows)))
```

### Memory inspection

- Short-term session items stored: `32`
- Durable research findings saved: `5`
- Stored content quality: Clean saved memories only; raw tool or session JSON was not saved.

| Topic | Saved finding |
|---|---|
| BRCA1 | BRCA1 encodes a tumor suppressor protein that helps maintain genomic stability and is essential for homologous recombination repair of DNA double-strand breaks. |
| BRCA1 | Women with a germline pathogenic BRCA1 variant have an estimated 55% to 72% lifetime risk of breast cancer by age 70. |
| BRCA1 | BRCA1 promotes DNA repair in part by localizing with BRCA2 and RAD51 at DNA damage sites to support RAD51-mediated repair. |
| BRCA1_BRCA2 | In homologous recombination, BRCA1 helps recruit the PALB2-BRCA2 complex to DNA damage sites, linking DNA end processing to RAD51 loading. |
| PALB2 | PALB2 physically links BRCA1 and BRCA2 during homologous recombination by binding both proteins and facilitating BRCA2-RAD51 repair complex assembly. |

## 10. Verify continuity — resume a fresh session with the same memory store

The real test of a memory-aware agent is whether it can pick up where a prior session left off. Let's create a *new* session (simulating a separate process or later day) and ask a question that builds on prior durable findings.

If the agent recalls BRCA1 findings from the previous run without depending on the previous session transcript, we've demonstrated end-to-end durable memory continuity.

This is an educational genomics example, not medical advice. The follow-up asks the agent to summarize guideline-backed discussion topics with citations, not to provide patient-specific clinical recommendations.


```python
# Simulate a fresh session (new session_id, but same run-scoped user/agent).
FRESH_SESSION_ID = f"genome-session-{RUN_ID}-002"
fresh_session = OracleAgentMemorySession(
    session_id=FRESH_SESSION_ID,
    client=memory_client,
    user_id=USER_ID,
    agent_id=AGENT_ID,
)

followup = (
    "Based on the saved BRCA1 findings, list exactly three concise, "
    "guideline-backed topics a clinician might discuss when explaining "
    "screening considerations for pathogenic BRCA1 variants. Keep this "
    "educational, not patient-specific medical advice. Use plain ASCII "
    "punctuation. Include concise inline URL citations for any sources you mention."
)

result = await Runner.run(research_agent, followup, session=fresh_session)
answer = _notebook_text(result.final_output.strip())
display(
    Markdown(
        "### Fresh session follow-up\n\n"
        f"**Question:** {_notebook_text(followup)}\n\n"
        f"{answer}"
    )
)
```

### Fresh session follow-up

**Question:** Based on the saved BRCA1 findings, list exactly three concise, guideline-backed topics a clinician might discuss when explaining screening considerations for pathogenic BRCA1 variants. Keep this educational, not patient-specific medical advice. Use plain ASCII punctuation. Include concise inline URL citations for any sources you mention.

1. Breast imaging timing and modality: discuss that guidelines generally recommend earlier, intensified breast screening, typically annual MRI starting by age 25 and annual mammography added around age 30 for BRCA1 carriers (https://www.cancer.gov/types/breast/hp/breast-ovarian-genetics-pdq, https://www.sgo.org/wp-content/uploads/2012/09/PB-182.pdf).

2. Limits of ovarian screening: explain that routine ovarian surveillance with transvaginal ultrasound or CA-125 has not shown clear benefit and is generally not recommended as an effective screening strategy (https://www.cancer.gov/types/breast/hp/breast-ovarian-genetics-pdq, https://www.ncbi.nlm.nih.gov/books/NBK589498).

3. Role of risk-reducing surgery in "screening considerations": note that counseling often includes the option of risk-reducing salpingo-oophorectomy, commonly discussed around ages 35 to 40 after childbearing, because screening alone does not adequately address ovarian cancer risk (https://www.sgo.org/wp-content/uploads/2012/09/PB-182.pdf, https://www.cancer.gov/types/breast/hp/breast-ovarian-genetics-pdq).

## 11. Cleanup (optional)

Cleanup is intentionally commented out. Uncomment it only when you want to remove the current run's session items and durable findings from your demo schema.

The setup above uses `CREATE_IF_NECESSARY`, so rerunning the notebook should not drop and recreate the schema by default. Each run uses a unique `RUN_ID` to avoid mixing current results with stale demo memories.

```python
# await session.clear_session()
# await fresh_session.clear_session()
# for r in await memory_client.search_async("BRCA", user_id=USER_ID, agent_id=AGENT_ID, exact_user_match=True, exact_agent_match=True, max_results=100, record_types=["memory"]):
#     memory_client.delete_memory(r.record.id)
# print("Cleaned up current run.")

connection.close()
print("Connection closed.")
```

```text
Connection closed.
```

## Key Takeaways

> **🎯 1. The `Session` protocol is the clean integration point.** Four async methods (`get_items`, `add_items`, `pop_item`, `clear_session`) is all the OpenAI Agents SDK needs to plug in a custom session backend. You don't have to modify the runner — you implement the protocol and pass an instance via `session=`.

> **🎯 2. Session persistence is not the same as long-term memory.** The session handles short-term conversation replay for the current agent loop. Durable findings should be concise conclusions written through explicit tools, not raw conversation or tool output dumped into long-term memory.

> **🎯 3. Instructions steer memory usage.** A deep-research agent must be explicitly told to *recall before researching* and *save durable conclusions*. Otherwise the LLM will treat memory as optional decoration and the store will fill up with low-value content.

> **🎯 4. Use safe schema defaults.** `CREATE_IF_NECESSARY` is safer for demos and development than a destructive recreate policy. Reserve destructive schema reset paths for isolated demo schemas.

> **🎯 5. Oracle AI Database gives you one governed substrate for both tiers.** Short-term session items and durable findings can live in one backend while remaining separate record types with different lifecycles.

> **🎯 6. Continuity is testable.** A new `session_id` with the same `user_id` / `agent_id` should produce an agent that reasons over prior durable findings. That's the simplest end-to-end test of a memory-aware agent.