# Demo video storyboard (≤ 3:00)

Rules judges optimize for: the project actually running, and visible proof of how Kiro was
used. Everything below is scripted so the recording takes one pass.

## Before you record

```bash
cd ~/finchnest/membridge
PAUSE=0 ./demo/demo.sh      # dry run once, so nothing surprises you
```

- Terminal: 1440×900, font ≥ 18 pt, dark theme, no personal paths on screen (`export PS1='$ '`).
- Do a clean run: `clear` before you start, and don't show `~/.zshrc`, browser tabs, or notifications.
- Have a second window open on the repo in Kiro so you can cut to it without loading time.
- Record with QuickTime (File → New Screen Recording), 1080p, microphone on.

## Shot list

### 0:00–0:20 — The problem
Terminal, nothing running.

> "I use six different AI coding agents. Every one keeps its own memory. So every time I
> switch tools, I re-explain the project — and the same mistake gets made again in a
> different window."

### 0:20–0:35 — What it is
```bash
cd ~/finchnest/membridge && ls -R .kiro
```
> "MemBridge is one memory store, one write path, shared by all of them. Plain text, no
> server, standard library only. The store is a directory you can `cat`."

### 0:35–1:05 — Agent A writes
```bash
PAUSE=0 ./demo/demo.sh
```
Run up to step 2, then pause the recording.

> "Agent A finishes a task and writes one entry through the only write path it has: `append`.
> Five fields — done, where it stopped, next step, the reusable conclusion, the pitfall.
> No free-form diary."

Point at the five `- 完成 / 停在哪 / 下一步 / 复用结论 / 踩坑` lines on screen.

### 1:05–1:30 — Agent B starts cold
Step 3 in the same run.

> "Now a different agent, a different tool, zero context. It searches the store first — that
> is the one rule in the protocol — and it gets agent A's exact conclusion, with the file and
> line it came from."

Highlight `[memory/2026-11-06.md:3]`. Say explicitly: **this is the whole point — context
survived the tool switch.**

### 1:30–1:50 — What the prompt actually receives
Step 4.

> "`inject` turns that into a memory block you prepend to any prompt, so recall does not
> depend on the agent reading rules by itself. Same block works for a tool that ignores
> config files entirely."

### 1:50–2:15 — The two guards
Step 5.

> "Two guards. Secret-shaped text is refused before it reaches disk — not logged, not
> truncated, refused. And five agents appending at the same instant all land: the write path
> is serialized by a file lock, so nothing interleaves."

Let the error line and the `5` land on screen for a beat each.

### 2:15–2:40 — How Kiro was used (required footage)
Cut to Kiro with the repo open. Show, in this order:

1. `.kiro/specs/shared-memory-layer/requirements.md` → "the spec is written before the code; these are EARS acceptance criteria, and each guard in the demo traces to one."
2. `.kiro/steering/tech.md` → "steering holds the constraints a new session would otherwise re-litigate: standard library only, no daemon, `MEMORY_HOME` instead of hardcoded paths."
3. `.kiro/specs/shared-memory-layer/tasks.md` → "tasks are checked off as work lands, so a fresh session resumes mid-feature."
4. Edit one line in `mem.py`, save, and let `verify-after-edit.kiro.hook` fire `scripts/selfcheck.py` → "the hook runs the contract on every edit. Green means the write path still holds; red means stop."

### 2:40–2:58 — Whole contract, one command
Step 6 of the demo run.

> "Four checks in one command: protocol, retrieval, five-field write, secret rejection, five
> concurrent appends. All green."

### 2:58–3:00 — Close
> "Same memory, every agent. That's MemBridge."

## Checklist before upload

- [ ] Under 3:00 (hard cut, don't let it run to 3:05)
- [ ] YouTube visibility: public or unlisted, no password
- [ ] Shows the project running on the machine it was built for
- [ ] Shows Kiro: specs, steering, and a hook firing
- [ ] No third-party trademarks or music
- [ ] Paste the YouTube URL into Project details → Demo video URL, then Submit

## Narration notes

- Say "file lock", "five fields", "refused before disk" — those are the three claims the demo
  proves, and judges score on claims that match footage.
- Don't explain the internals of scoring or embeddings. The video is about the switch: same
  memory, different agent.
