# MemBridge

**One shared memory layer for every AI coding agent you use.**

Kiro, Claude Code-style agents, OpenCode, Qoder, Trae, PI-Desktop, Command Code, Antigravity — every one of them keeps its own memory. Switch tools and the project conventions, the design decisions and the "we already tried that and it broke" notes are gone. You re-explain everything, and the same mistakes get repeated in a different window.

MemBridge is a small, dependency-free memory layer that makes all of them read and write the **same** project memory:

- **One writer.** A single CLI (`mem.py`) is the only thing that touches the store: `search`, `read`, `notes`, `append`, `inject`, `protocol`, `dispatch`, `harvest`, `sessions`, `recall`.
- **File-locked writes.** Agents run in parallel; every write goes through a POSIX file lock and a single entry point, so concurrent agents cannot corrupt the store or drift the format.
- **Fixed note template.** Every entry is five fields — *done / where it stopped / next step / reusable conclusion / pitfall*. Memory stays structured instead of becoming a chat-log dump.
- **Secret filter.** API keys, tokens, passwords and credentials are rejected before anything reaches disk. `--force` does not bypass it.
- **Layer discipline.** Hard rules, one-line index, dated work log, per-project state, and reusable lessons live in separate layers. Facts only get promoted upward when they prove reusable.
- **Zero infrastructure.** Plain text and Markdown on your own disk. No server, no database, no vendor account, no lock-in.

## Why this exists

Layered memory is not about storing more. It is about knowing **when to recall**. Without a template, "memory" degrades into noise — and noisy memory is worse than none, because the agent confidently reads the wrong thing.

MemBridge enforces three habits:

1. **Search before you start.** Look up the project, the site, the reagent, the error string first. Never probe from zero, never repeat a known failure.
2. **Write at the end, in a fixed shape.** One entry per task, five fields, with the reusable conclusion marked as a candidate.
3. **Promote slowly.** A candidate conclusion only moves into the index when it is used a second time. Everything else stays a diary.

## Install

```bash
git clone https://github.com/<your-account>/mem-bridge.git
cd mem-bridge
export MEMORY_HOME="$HOME/finchnest"   # where the memory store lives
python3 mem.py protocol
```

There are no third-party dependencies — Python 3.8+ standard library only.

Create the store once:

```bash
mkdir -p "$MEMORY_HOME/memory/notes"
printf '## Notes\n' > "$MEMORY_HOME/MEMORY.md"
```

## Usage

```bash
# search the whole store (index first, then notes and daily logs)
python3 mem.py search "primer design"

# read a specific layer
python3 mem.py read MEMORY
python3 mem.py read 2026-11-06

# append one five-field entry (the only write path)
python3 mem.py append --tool kiro --task "cloning" --text "完成：..."

# build a memory block you can paste into any prompt
python3 mem.py inject "cloning primer"

# three-part dispatch prompt: memory block + task + handoff instruction
python3 mem.py dispatch --task "review the adapter docs" adapter

# print the shared protocol
python3 mem.py protocol
```

## Architecture

```
memory store (plain text, your disk)
├── AGENTS.md                 L0  hard rules and red lines
├── MEMORY.md                 L1  one-line index — enough to judge relevance
├── memory/notes/<slug>.md    L1  detail notes: trigger → conclusion → when to reuse
├── memory/<date>.md          L2  daily work log
└── memory/spaces/<id>.md     L2  per-project state and decisions

mem.py  ── single read/write entry point, file-locked, secret-filtered
   ▲
   ├── adapter: global AGENTS.md        (agents that auto-load it)
   ├── adapter: global CLAUDE.md        (CLAUDE-style agents)
   ├── adapter: prompt include file     (prompt-composition agents)
   └── adapter: project rules directory (per-workspace agents)
```

Each agent is connected through its **own native surface** — a rules file, a project rule, or a prompt include. No plugin, no proxy, no per-vendor API. See [docs/adapters.md](docs/adapters.md).

## Safety model

| Rule | Why |
|---|---|
| External tools may only `append` to the daily log | Prevents two agents rewriting the index at the same time |
| Only the curator process promotes notes into `MEMORY.md` | Keeps the index short, deduplicated and trustworthy |
| Secrets are rejected at write time | Memory is long-lived; a leaked key in a daily log is forever |
| Raw data stays read-only; outputs go to new files | An agent must never silently overwrite source data |

## Verifying

```bash
python3 scripts/selfcheck.py
```

Runs against a throwaway store and checks the contract end to end: protocol output,
retrieval, the five-field write path, secret rejection (nothing reaches disk), and five
concurrent appends all landing intact.

## Working in Kiro

The Kiro configuration lives at the repository root, not hidden by `.gitignore`:

| Path | What it holds |
|---|---|
| `.kiro/steering/` | product, tech and structure notes, loaded into every spec session |
| `.kiro/specs/shared-memory-layer/` | the feature spec: requirements in EARS form, design, task plan |
| `.kiro/hooks/verify-after-edit.kiro.hook` | runs `scripts/selfcheck.py` whenever `mem.py` or a test changes |
| `.kiro/hooks/verify-adapter.kiro.hook` | on demand: probes whether an agent actually loaded the protocol |

The steering files stop a session from re-litigating settled decisions (no pip installs, no
daemon, writes only through `append`). The spec is written before the code and the task file
is checked off as work lands, so a fresh session can resume mid-feature instead of guessing.

## Status

Working, used daily across six agents. Retrieval is a weighted lexical search (BM25-style scoring with an index-first bias); an optional embedding backend can be configured for hybrid retrieval.

## License

MIT — see [LICENSE](LICENSE).
