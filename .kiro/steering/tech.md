# Project steering: tech

## Constraints

- **Python 3.8+ standard library only.** No pip install, no virtualenv requirement. The CLI
  must run on a bare macOS/Linux box with the system Python.
- **Plain text storage.** Markdown files on local disk. Nothing that needs a daemon.
- **POSIX only today.** `fcntl` locking is used for the write path; Windows is out of scope
  until a portable lock replaces it.

## Conventions

- One module: `mem.py`. Subcommands are argparse subparsers, one function each.
- The store root comes from `MEMORY_HOME` (default `~/finchnest`). Never hardcode paths to a
  specific user's home.
- All writes go through `append`; `MEMORY.md` and `memory/notes/` are curator-only.
- Errors go to stderr as `[mem] 错误：...` and exit non-zero. A silent failure is a bug.
- Retrieval failures degrade, they do not crash: if an optional embedding backend is
  unavailable, fall back to lexical search and say so on stderr.

## Testing

- `python3 mem.py protocol` must print the shared protocol and exit 0.
- `python3 mem.py search <term>` must return ranked hits from the store and exit 0.
- `python3 mem.py append --tool test --task smoke --text "..."` must add exactly one entry
  to today's daily log, and must reject text containing a secret pattern.
- Concurrency: two `append` processes started at the same time must both land, with no
  interleaved or truncated lines.
