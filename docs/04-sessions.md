# 04 — Sessions

Sessions preserve conversations and agent state across runs.

## Design

Tau uses an append-only session tree. Instead of mutating old state, Tau appends entries and reconstructs state by replaying them.

The low-level implementation lives in:

```text
src/tau_agent/session/
```

## Entry types

- `message`
- `model_change`
- `thinking_level_change`
- `compaction`
- `branch_summary`
- `label`
- `leaf`
- `session_info`
- `custom`

## Current capabilities

Tau can now:

- serialize and deserialize session entries as JSONL
- append entries to local session files
- read session files in order
- reconstruct linear session state
- reconstruct a root-to-leaf branch path
- load a `tau_coding.CodingSession` that restores messages and persists new runs

## Boundary

Low-level session primitives belong in `tau_agent`. File locations, slash commands, and coding-agent workflows belong in `tau_coding`.

`CodingSession` is the first `tau_coding` layer on top of the low-level primitives. It wires storage, `AgentHarness`, cwd, and coding tools together while leaving richer commands and resource loading for later phases.
