# Design: shared memory layer

## Overview

One CLI process (`mem.py`) and one directory of Markdown files. Agents call the CLI; the CLI
owns every read and write. There is no daemon, so the store is inspectable with `cat`.

## Store layout

```
MEMORY.md                  L1 index, one line per fact
memory/notes/<slug>.md     L1 detail: trigger → conclusion → when to reuse
memory/<YYYY-MM-DD>.md     L2 daily log, append-only
memory/spaces/<id>.md      L2 per-project state
memory/.mem.lock           lock file for the write path
memory/.search-index/      derived cache, safe to delete
```

## Retrieval

1. Score `MEMORY.md` lines and note bodies lexically (term overlap, idf-weighted).
2. Add dated logs at lower weight so recency does not outrank a curated index line.
3. Optionally fuse an embedding backend's ranking with reciprocal-rank fusion; if the
   backend is missing or errors, fall back to lexical only and print the fallback reason to
   stderr. A retrieval failure must never abort a read.
4. Return `path:line` with each hit so the caller can open the source.

## Write path

```
append → acquire flock(.mem.lock) → format five fields → secret check → append line → release
```

The secret check runs **before** the lock is released and before anything touches disk, so a
rejected write leaves no partial line. `--force` bypasses capacity checks, never the secret
check.

## Extension points

- `harvest` reads each agent's transcript store and appends gist summaries, idempotently.
- `sessions` greps those transcripts, so raw process can be drilled into without promoting
  it into the shared layer.
- `recall` reads an activity database for "what was on screen at the time"; keystroke and
  clipboard tables are explicitly excluded from the query surface.

## Failure modes considered

| Failure | Handling |
|---|---|
| Two agents append at once | flock serializes; the loser waits, then writes |
| Embedding backend down | lexical fallback plus a stderr note |
| Store missing | commands that need it create the directory tree; `read` reports the missing layer |
| Oversized entry | truncated at the template boundary, never mid-line |
| Secret in text | rejected, non-zero exit, nothing written |
