# Project steering: structure

```
mem.py                     the only executable: search / read / notes / append /
                           inject / protocol / dispatch / harvest / sessions / recall
AGENTS.memory.md           the protocol text pasted into every agent's rules surface
docs/adapters.md           how to wire an agent to the store, and how to verify it
.kiro/steering/            product, tech and structure notes loaded in every spec session
.kiro/specs/               specs for features, in requirements → design → tasks order
.kiro/hooks/               agent hooks that run the verification steps

store (MEMORY_HOME, not in this repo)
├── MEMORY.md              one-line index
├── memory/notes/*.md      detail notes
├── memory/<date>.md       daily log, append-only
└── memory/spaces/*.md     per-project state
```

## Rules of placement

- Anything that changes how an agent behaves belongs in `AGENTS.memory.md`, because that
  file is what gets pasted verbatim into each tool.
- Anything that changes how this repo is built belongs in `.kiro/steering/`.
- Anything that describes a feature belongs in `.kiro/specs/<feature>/`, never in the README.
- The README stays short enough that a person reads it before cloning.
