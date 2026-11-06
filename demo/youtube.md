# YouTube upload sheet

Title options (pick one, ≤ 100 chars):

1. `MemBridge — one shared memory for every AI coding agent (Kiroween 2026)`
2. `I stopped re-explaining my project to every AI agent | MemBridge, Kiroween 2026`

Description (paste as-is):

```
One memory store, shared by every AI coding agent I use. Switch tools, keep context.

MemBridge is a plain-text memory layer with a single write path. Six agents — Kiro, Finch,
Qoder, OpenCode, Trae and PI-Desktop — read and write the same store through one CLI, so a
new agent starts with the real state of the project instead of from zero.

Chapters
0:00  the problem: six agents, six memories
0:05  the store is plain text on disk
0:11  agent A writes one five-field entry
0:17  agent B starts cold and finds it
0:23  the block that goes into the prompt
0:29  two guards: secret refusal, concurrent writes
0:35  the whole contract, one command
0:47  how Kiro is wired in: steering
0:53  how Kiro is wired in: the spec
0:59  how Kiro is wired in: the hook
1:05  repo and links

Built with: Kiro (IDE — spec-driven development, steering, agent hooks), Python standard
library only. No server, no database, no dependencies.

Code: https://github.com/haolingni-eng/mem-bridge
Demo run: ./demo/demo.sh    Contract check: python3 scripts/selfcheck.py

Made for Kiroween 2026.
```

Pinned comment:

```
The video is a terminal screencast re-rendered from a real run of ./demo/demo.sh against a
throwaway store — every line of output is real. Everything shown lives in the repo:
.kiro/specs, .kiro/steering, .kiro/hooks, and scripts/selfcheck.py.
```

Tags: `kiro`, `kiroween`, `ai agents`, `developer tools`, `memory`, `cli`, `python`

Settings:
- Visibility: **Public** (rules ask for publicly visible; unlisted is also accepted, but public helps the Social Blitz post)
- Not made for kids, no age restriction
- Category: Science & Technology
- Language: English
- Length: 1:10 — inside the 3-minute limit

After upload: paste the URL into Devpost → Project details → Demo video URL, then Submit.
