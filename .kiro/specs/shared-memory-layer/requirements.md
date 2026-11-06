# Requirements: shared memory layer

## Introduction

A single local memory store that several AI coding agents read and write through one CLI,
so switching tools no longer means losing project context.

## Requirements

### Requirement 1 — One store, many agents

**User story:** As a developer who switches between agents, I want every agent to see the
same project memory, so that a new agent starts with the real state of the work.

#### Acceptance criteria

1. WHEN any supported agent runs `mem.py search <keywords>`, THE SYSTEM SHALL return ranked
   hits drawn from the index, the detail notes and the dated logs of one store.
2. WHEN an agent runs `mem.py protocol`, THE SYSTEM SHALL print the shared protocol text so
   the agent can follow it without reading another file.
3. WHEN `MEMORY_HOME` is set, THE SYSTEM SHALL use it as the store root instead of the
   default `~/finchnest`.

### Requirement 2 — One write path

**User story:** As the store's owner, I want external agents to only append to the daily
log, so that the index and the notes stay curated and deduplicated.

#### Acceptance criteria

1. WHEN an agent runs `mem.py append --tool <name> --task <task> --text <text>`, THE SYSTEM
   SHALL append exactly one entry to today's daily log under the five-field template.
2. WHEN a field is omitted, THE SYSTEM SHALL fill it with `无` rather than dropping it.
3. THE SYSTEM SHALL NOT expose a command that modifies `MEMORY.md` or `memory/notes/`.

### Requirement 3 — Concurrency safety

**User story:** As a developer running agents in parallel, I want simultaneous writes to
serialize, so that no entry is lost or interleaved.

#### Acceptance criteria

1. WHEN two `append` processes write at the same time, THE SYSTEM SHALL serialize them with
   a file lock and both entries SHALL appear intact.
2. WHEN the lock cannot be acquired within the timeout, THE SYSTEM SHALL fail loudly with a
   non-zero exit code.

### Requirement 4 — Secret rejection

**User story:** As the store's owner, I want credentials rejected at write time, so that a
long-lived log never carries a leaked key.

#### Acceptance criteria

1. WHEN the text to be written matches a secret pattern (API key, token, password,
   private-key header, AWS access key), THE SYSTEM SHALL refuse the write and exit non-zero.
2. WHEN `--force` is passed with secret-shaped text, THE SYSTEM SHALL still refuse.

### Requirement 5 — Prompt injection block

**User story:** As a developer dispatching a task to another agent, I want a ready-made
memory block, so that recall does not depend on the agent reading rules by itself.

#### Acceptance criteria

1. WHEN `mem.py inject <keywords>` runs, THE SYSTEM SHALL emit a `<memory>` block containing
   the highest-scoring entries, bounded in size.
2. WHEN `mem.py dispatch --task <task> <keywords>` runs, THE SYSTEM SHALL emit three parts:
   the memory block, the task, and a handoff instruction telling the agent to write its
   five-field summary at the end.
