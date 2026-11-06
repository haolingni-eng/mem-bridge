# Adapters

MemBridge does not patch other agents. Each agent gets a thin adapter that points at the
same memory store, using whatever configuration surface that agent already reads on
startup. There are four shapes, and most agents fall into one of them.

| Shape | Where the adapter lives | Agents observed to use it |
|---|---|---|
| Global rules file | a single agent-wide rules file, auto-loaded in every session | OpenCode-style agents |
| Global instruction file | a global `CLAUDE.md`-equivalent | CLAUDE-style agents |
| Prompt include | a file the agent's prompt template includes | prompt-composition agents |
| Project rules | `<workspace>/AGENTS.md`, inherited up the directory tree | per-workspace agents |

## Writing an adapter

An adapter is a short text file that tells the agent four things:

1. **Where memory lives** — the store root and its layers.
2. **What to do first** — run `mem.py search <keywords>` before starting a task; read the
   detail note when a hit matters.
3. **What to do last** — run `mem.py append --tool <name> --task <task>` with the five fields.
4. **What is forbidden** — never edit the index or the notes directly, never write secrets,
   never rename identifiers away from the source document, never invent data.

The protocol text is kept in one place — [`AGENTS.memory.md`](../AGENTS.memory.md) — and
pasted verbatim into each agent's surface. Keeping a single source means the behaviour does
not drift between tools.

## Verifying an adapter

Config files are not proof. Start a **fresh** session in the target agent and ask it
something that can only be answered from memory:

```
Run `python3 mem.py protocol`, then search "acceptance rules" and tell me what you hit.
```

If it returns the stored entry, the adapter works. If it returns a plausible-sounding
answer with no hit, the rules file is being ignored — check the agent's load order, because
most of them load the workspace rules and their own global settings, not the home-directory
chain.

## Known asymmetry

Rule auto-loading is uneven: some agents load a global rules file in every session, others
only load the current workspace. Two stable workarounds, neither requiring the agent to
cooperate:

- paste `AGENTS.memory.md` into each agent's global rules box once;
- generate a memory block with `mem.py inject <keywords>` and prepend it to whatever prompt
  you are about to send.

The second one always works, because it does not depend on the agent reading anything on
its own.
