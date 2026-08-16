---
name: writeup
description: Put what the user asked for onto one self-contained HTML page, written in the house voice. It adds nothing of its own — no summary, no score, no severities, no next steps, no sections nobody asked for. The look is a default you can change or throw out. One HTML file is the only thing it makes. Triggers on - 'write this up', 'turn this into a page', 'make an HTML of this', 'I want to show someone this', or /writeup.
---

# Writeup

Shows what you asked to be shown. That is the whole job.

One file in this skill's base directory, plus the house voice doc:

- `docs/ways_of_working/tone_and_taste.md` (at the repo root) — how it is written. Read it before
  writing a word.
- `SHELL.html` — an empty page with the colours, the type and the spacing. Drop the content in
  and change nothing else.

## The rule

**Put on the page what you were asked for. Nothing you were not asked for.**

Anything you add on your own is slop, however good it looks:

- No summary, headline or overview nobody asked for.
- No score, rating, readiness number or confidence level.
- No severity ratings, no colour-coded badges, no Critical / Major / Minor grouping.
- No "next steps", "recommendations", "how to test", "what changed", "risks", "open questions".
- No filler section to make the page look complete. A short page is a finished page.
- Folds (`<details>`) are allowed, with one rule: **the closed summary must already deliver the
  outcome as a complete sentence**, and the body holds only the supporting detail — the trace,
  the code, the numbers behind it. A reader who never opens a fold has still been told
  everything they asked for. Never fold away the answer itself, and never use a fold to smuggle
  in content nobody asked for.

Asked for the three options and what each costs? The page has three options and what each
costs. It does not also have a recommendation, a comparison table, or a verdict.

If you think something is missing, say it in the chat afterwards. Do not put it on the page.

## The only thing it makes is one HTML file

No JSON alongside it, no markdown copy, no notes file, no commit.

## You decide how the page looks

`SHELL.html` is a **default, not a contract.** It is what you get when you say nothing about the
look. Say anything about it and your instruction wins, without discussion: a different layout,
different colours, no theme button, built for printing, or start from a page you like and ignore
this one. Change the CSS, replace it, or throw it out.

Do not argue for the default, do not offer it as a compromise, and do not quietly keep half of
it. If a change costs something worth knowing, say it in one sentence and then build exactly
what was asked.

## How

1. Read `docs/ways_of_working/tone_and_taste.md`.
2. Write what you were asked for. Nothing else.
3. Read `SHELL.html`, replace the `<!-- CONTENT -->` line with the content and
   `<title>Writeup</title>` with the real title. Replace `HOW-THIS-WAS-MADE` in the footer with
   one plain sentence saying where this came from, or delete that line.
4. Write it to `writeup/<slug>.html` at the root of the repo this skill is installed in —
   `$(git rev-parse --show-toplevel)/writeup/`. Create the directory if it is not there, and
   never write to a hardcoded absolute path. Self-contained — no fonts or scripts from anywhere
   else, so it opens from a `file://` URL and survives being emailed.
5. Say where it went, in one line.

If you were not told what goes on the page, ask. Do not guess and do not fill it in.

## What the default shell styles

**Light theme only, always.** The owner decided this; never add a dark mode,
a `prefers-color-scheme` block, or a theme button back.

The look comes from harness-kit's pattern-engineering-audit report: mono
uppercase section labels with a short blue bar, bordered flat cards, chips,
no rounded corners, no shadows. Plain HTML works
(`h1` `h3` `p` `ul` `ol` `a` `strong` `code` `pre` `table`), and these
classes carry the structure — reach for them instead of raw paragraphs when
the content is a sequence, a set of parts, or a status:

| | |
|---|---|
| `<header>` with `<p class="kicker">`, `h1`, `<div class="headmeta">` of `<span class="chip">`s | The top of the page: label, title, a few facts as chips |
| `<section>` + `<h2 class="label">` | A section; the h2 gets the mono small-caps + blue bar treatment |
| `<ol class="walk"><li><div>…</div></li></ol>` | A numbered sequence of steps (01, 02, …) |
| `<div class="card">` with `<span class="file">path</span>`, `h3`, `p` | One component or part, headed by its file path |
| `<span class="tag built">` / `tag planned` / `tag blue` | A small status tag |
| `<div class="cmd"><code>…</code><button class="btn">Copy</button></div>` | A command someone runs |
| `<div class="tablewrap"><table>` | A table that can scroll sideways |
| `<div class="note">` | An aside |
| `<details class="fold"><summary>…</summary><div class="fold-body">…</div></details>` | An accordion. The summary is a complete sentence carrying the outcome; the body is the evidence |
| `<table class="matrix">` with `<button class="cell-btn ok/part/off/na">` cells | A conformance matrix: rows are the things checked, columns are the stages, each cell opens a modal with the specifics (see below) |

### The conformance matrix, when a comparison is asked for

For "X against Y, per stage" comparisons the shell ships a matrix + modal pattern: one row per
thing, one column per stage, and every non-empty cell is a button. The cell shows only the
status word — `ok` (fits), `part` (mismatch), `off` (completely off), `na` (stage doesn't
apply) — and clicking it opens a `<dialog>` whose text explains that one cell **in isolation**:
what was expected, what the code actually does, file and line. The modal text is written so
someone who has read nothing else on the page understands it. Fill the dialog from a
`data-detail` attribute on the cell button; SHELL.html already carries the dialog element and
the click handler.

## Writing it

`docs/ways_of_working/tone_and_taste.md` governs every sentence. Two things from it that get missed most:

- **Every line stands alone.** It gets read by someone with nothing else open. No "see above",
  no bare reference to a label the reader would have to look up — and no positional references
  either: "step 5", "the section above", "D3" mean nothing to someone reading that one line.
  If a line depends on another fact, the line carries that fact with it, in a parenthesis if
  needed.
- **Real numbers, real file names, and where a number came from.** "This broke twice" beats
  "this is a known risk area". A number without its derivation reads as slop because it is slop.
- **The page is agent-to-human communication, and the human is the constraint.** The agent that
  wrote the page held the whole codebase in context; the person reading it holds seven things
  at once and forgets the top of the page by the bottom. So: outcomes visible closed, evidence
  one click deep in a fold or modal, and every fragment — a summary, a table cell, a question —
  understandable on its own. A question a person is asked to answer carries everything needed
  to answer it: what the situation is, what the options are, and what each costs.
