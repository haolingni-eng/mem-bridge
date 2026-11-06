# Project steering: product

## What this is

MemBridge is a shared memory layer for people who use more than one AI coding agent.
Each agent keeps its own memory; MemBridge gives all of them one store on disk and one
write path.

## Goals

1. An agent that has never seen a project can start work with the project's real state
   already in context — no re-explaining.
2. Memory never degrades into a chat-log dump: every entry has the same five fields.
3. Two agents writing at the same time never corrupt the store or drift its format.
4. No infrastructure: plain text on local disk, no server, no account, no lock-in.

## Non-goals

- Not a vector database or a hosted memory service.
- Not an agent framework. It does not drive any agent; it only feeds and records.
- Not a note-taking app. There is no UI and there will not be one.

## Audience

Developers who run two or more coding agents in parallel and lose context every time
they switch tools.
