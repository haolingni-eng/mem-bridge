# Implementation plan: shared memory layer

- [x] 1. Store layout and path resolution
  - [x] 1.1 Resolve the store root from `MEMORY_HOME`, default `~/finchnest`
  - [x] 1.2 Create `memory/`, `memory/notes/`, `memory/spaces/` on demand
  - [x] 1.3 Keep the derived search index outside the tracked tree

- [x] 2. Retrieval
  - [x] 2.1 Weighted lexical scoring over index, notes and dated logs
  - [x] 2.2 Optional embedding backend with reciprocal-rank fusion
  - [x] 2.3 Degrade to lexical search when the backend is unavailable, with a stderr note
  - [x] 2.4 Return `path:line` with every hit

- [x] 3. Write path
  - [x] 3.1 Five-field template with `无` defaults
  - [x] 3.2 Secret pattern rejection, before disk and before unlocking
  - [x] 3.3 `flock` serialization with a bounded wait

- [x] 4. Prompt-side helpers
  - [x] 4.1 `inject` emits a bounded `<memory>` block
  - [x] 4.2 `dispatch` emits memory block + task + five-field handoff instruction
  - [x] 4.3 `protocol` prints the paste-ready adapter text

- [x] 5. Transcript tooling
  - [x] 5.1 `harvest` appends idempotent gist summaries per agent
  - [x] 5.2 `sessions` searches raw transcripts without promoting them
  - [x] 5.3 `recall` queries activity history with keystroke/clipboard excluded

- [ ] 6. Verification hardening
  - [x] 6.1 `protocol` and `search` smoke checks
  - [x] 6.2 Concurrent-append test script checked into the repo (`scripts/selfcheck.py`)
  - [x] 6.3 Secret-rejection test against the real write path, before disk

- [ ] 7. Portability
  - [ ] 7.1 Replace `fcntl` with a portable lock so Windows works
  - [ ] 7.2 Adapter templates for agents that only load workspace rules
