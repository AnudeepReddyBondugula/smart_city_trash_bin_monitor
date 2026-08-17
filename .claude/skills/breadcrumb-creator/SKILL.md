---
name: breadcrumb-creator
description: "Traces a workflow end-to-end through the data-simulator service and creates a breadcrumb analysis doc in .claude/breadcrumbs/. Use this skill whenever the user wants to document a flow, trace a workflow, understand how a feature works, or create a debugging guide for a specific flow. Also use when the user mentions 'breadcrumb', 'trace this flow', 'how does X work end to end', 'document this workflow', or /breadcrumb-creator."
argument-hint: "<flow name or description, e.g. 'bin status update' or 'kafka retry'>"
allowed-tools: Bash, Read, Edit, Write, Task, Grep, Glob
---

# /breadcrumb-creator — Workflow Breadcrumb Analysis

Traces a workflow through this repo and produces a compact debugging
reference. The output is for devs and agents who need to find where things
break — not for onboarding docs or architecture overviews.

## Repo shape

One implemented service: `services/data-simulator/` — a Python 3.12 AsyncIO
app. Static bin metadata lives in Postgres; telemetry publishes to Kafka.
Logs: console (color) + `services/data-simulator/logs/simulator.log`.

## Context

<flow_context> $ARGUMENTS </flow_context>

If the context above is empty, ask: "Which flow do you want to trace?
Describe it in terms of the event that kicks it off (CLI invocation, signal,
scheduled tick, PR event)."

## Step 0: Check existing breadcrumbs

Before scoping anything, read `.claude/breadcrumbs/_INDEX.md` to see what
already exists.

Compare the user's request against the existing entries and make one of
three decisions:

1. **Already covered** — tell the user which breadcrumb covers it, ask if
   they want to update/extend it instead of creating a new one.
2. **Partially overlapping** — extend the existing breadcrumb's FLOW/DETAILS/
   DEBUG files, or create a new breadcrumb for the non-overlapping portion
   with cross-references in both directions.
3. **New territory** — proceed to Step 1.

Present your decision to the user before proceeding.

## Step 1: Scope the flow

```
FLOW: <name — short, kebab-case, used as folder name>
TRIGGER: <what kicks it off — CLI command, signal, scheduled tick, PR event>
END STATE: <what the system looks like when it completes>
```

Ask the user to confirm the scope before proceeding.

## Step 2: Trace the flow

Read the actual code — don't guess from file names. For each hop record:

1. **Source file and function** — where the action originates.
2. **What it does** — one line, no fluff.
3. **What it passes** — key data (payload shape, IDs, status values).
4. **Where it goes next** — the next file/function in the chain.

## Step 3: Create the breadcrumb docs

Create the folder `.claude/breadcrumbs/<flow-name>/` with three files,
matching the shape of the existing breadcrumbs (e.g.
`.claude/breadcrumbs/startup-and-telemetry/`):

- **`FLOW.md`** — Trigger / End state + a linear
  `file :: function → does X` fenced-code trace, branches labeled if any.
- **`DETAILS.md`** — numbered `## N. <step>` sections: File/Function/Called
  by/Calls, key logic (conditionals, side effects, error handling), data
  in/out. Skip boilerplate.
- **`DEBUG.md`** — `## Log locations`, `## What to search for` (symptom /
  where / grep term table), `## Quick commands` (bash fence, flow-specific
  only), `## Env vars that affect this flow`, `## Common breakpoints`.

## Step 4: Verify completeness

- [ ] Every hop the flow touches is in `FLOW.md`.
- [ ] `DETAILS.md` covers every hop in `FLOW.md` with file/function specifics.
- [ ] `DEBUG.md` has at least 3 "what to search for" entries based on
      realistic failure modes.
- [ ] Every `file:line` citation was verified against the actual current code.
- [ ] `.claude/breadcrumbs/_INDEX.md` is updated (new folder → add row to
      Flows table AND Quick navigation).

## Step 5: Output summary

```
Created breadcrumb analysis for: <flow name>
Location: .claude/breadcrumbs/<flow-name>/
Files:
  FLOW.md    — high-level flow (<N> steps)
  DETAILS.md — detailed trace (<N> sections)
  DEBUG.md   — debug guide (<N> search patterns)

Updated: .claude/breadcrumbs/_INDEX.md
```

## Style rules

Dev-to-dev notes — someone (human or agent) should quickly find where to
look when something breaks.

- No intro paragraphs. Jump straight to content.
- No emoji, no decorative headers.
- Use code formatting for file paths, function names, commands, env vars.
- One line per concept. Prefer tables over prose for structured data.
- If unsure, mark with `[?]` rather than guessing.
