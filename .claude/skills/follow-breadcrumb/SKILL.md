---
name: follow-breadcrumb
description: "Consults existing breadcrumb analysis docs before exploring the codebase. Use this skill whenever the user asks how a flow works, where something happens in the code, how to debug or test a specific area, what files are involved in a feature, or needs to understand the path telemetry/data takes through the simulator. Also trigger on 'where does X happen', 'how does Y work', 'trace this', 'what files handle Z', 'how to test this flow', 'debug this area', or before spawning exploration subagents for a cross-cutting flow. This is cheaper and more accurate than re-discovering the same information through code search."
argument-hint: "<what you're trying to understand, e.g. 'how does shutdown work' or 'where does telemetry get published'>"
allowed-tools: Read, Grep, Glob, Task, Bash
---

# /follow-breadcrumb — Breadcrumb-First Exploration

This skill is about reading before searching. `.claude/breadcrumbs/` contains
end-to-end workflow traces that have already been carefully researched and
verified against the code (`file:line` citations). Loading a relevant
breadcrumb takes seconds and costs a fraction of what spawning exploration
subagents costs.

## Context

<exploration_context> $ARGUMENTS </exploration_context>

If the context above is empty, look at what the user is asking about in the
conversation and infer the exploration target.

## Step 1: Load the index

Read `.claude/breadcrumbs/_INDEX.md`. This is the single source of truth for
what's been documented.

Two sections matter:

1. **Flows table** — lists every breadcrumb folder and what it traces. Scan
   to find which breadcrumb(s) cover the user's question.
2. **Quick navigation** — maps common symptoms directly to the right
   `DEBUG.md`. If the user describes a symptom, check here first.

### Debugging gate (mandatory)

If this is a debugging task — any error or symptom — you must, BEFORE your
first debugging action, find the symptom in the Quick navigation table and
**QUOTE the matching row verbatim in your output** (or state "no row
matches", which means a breadcrumb is missing). Work that starts debugging
without that quote is wrong regardless of outcome.

## Step 2: Match the question to breadcrumbs

### A. Direct hit — a breadcrumb covers exactly this flow

Load docs in order of increasing detail:

1. **FLOW.md** — Read first. High-level map (30-second read). Often answers
   "where does X happen?".
2. **DETAILS.md** — Read for function-level specifics. Answers "how does X
   work?".
3. **DEBUG.md** — Read when debugging/testing. Log locations, grep patterns,
   commands, env vars, breakpoints.

Don't load all three by default. Start with `FLOW.md` and go deeper only if
needed.

### B. Partial coverage — a breadcrumb covers part of the flow

Load the relevant breadcrumb, then tell the user which parts it covers and
which parts you'll need to explore directly.

### C. No coverage — nothing in the index matches

Tell the user no existing breadcrumb covers this flow, explore the code
directly, and suggest running `/breadcrumb-creator` afterward to document it.

## Step 3: Present findings

Synthesize an answer to the user's actual question. Don't dump breadcrumb
content — extract the specific info they need, citing `file:line` from the
breadcrumb.

If the breadcrumb is stale (references files/functions that no longer
exist), verify those points against current code and flag it so the
breadcrumb can be updated.

## Step 4: Suggest breadcrumb creation for gaps

If exploration uncovered an undocumented flow or a significant gap, suggest
running `/breadcrumb-creator` to document it for future reference.

## When NOT to use this skill

- **Single-file questions** — "What does `functionName` in `file.py` do?" →
  Just read the file.
- **Creating new breadcrumbs** — Use `breadcrumb-creator` instead. This skill
  reads; that one writes.
- **General codebase search** — "Find all TODO comments" → Just grep.
  Breadcrumbs trace flows, not patterns.
