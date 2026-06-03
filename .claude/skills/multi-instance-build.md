Create the file .claude/skills/multi-instance-build.md 
(create the .claude/skills/ directory if it doesn't exist) 
with exactly this content:

---
name: multi-instance-build
description: >
  Use this skill whenever the user wants to build a software project using
  multiple parallel Claude Code instances coordinated from a single chat.
  Triggers include: "generate prompts for Claude Code", "break this into
  parallel tasks", "give me the next round of prompts", "multi-instance build",
  or any request to coordinate a build across multiple terminal instances.
---

# Multi-Instance Claude Code Build Skill

## What This Skill Does

Coordinates a software build across multiple parallel Claude Code instances.
The chat acts as the Architect — it plans, breaks down tasks, generates
prompts, and processes summaries. Claude Code instances act as Builders —
they execute one focused task each and report back.

---

## Core Concepts

**Round** — one batch of prompts. All instances in a round run in parallel.
A round ends when all instances finish and report their summaries.

**Instance** — one Claude Code terminal running one prompt. Each instance
handles exactly one module, one file, or one clearly scoped task.

**Summary** — structured text each instance outputs at the end. The Architect
reads these to understand what was done and plan the next round.

**Test Prompt** — one prompt per round (last to run) that verifies the
round's work. Results logged to test.md.

---

## Workflow

Round N:
  Architect generates N task prompts + 1 test prompt
  User runs all task prompts in parallel Claude Code instances
  User collects all summaries and returns to Architect
  Architect reads summaries → generates Round N+1
  User runs test prompt → appends result to test.md

---

## Rules for Parallel Tasks

Can run in parallel:
- Different files with no imports between them
- Different database tables or models
- Different API routes
- Different modules that don't call each other

Cannot run in parallel:
- Task B imports from Task A
- Task B writes to a table Task A creates
- Scaffold must always be Round 1 alone

---

## Prompt Format

## SLATE Build — Round [N] — Instance [X] of [Total]

### Context
[2-3 sentences: what exists, what this instance's task fits into]

### Your Task
[One clearly scoped task. One module or one file. Never more.]

### Exact Files to Create or Edit
- [file path] — [what to do]

### Inputs Available
- [what already exists that this task depends on]

### Output Requirements
- [exactly what the file/function must do]
- [specific function signatures if needed]
- [MOCK_MODE = True/False instruction]

### Do Not
- [explicit things to avoid]

### When Done — Output This Summary

---SUMMARY---
Instance: [X]
Task: [one line]
Files created: [list]
Files edited: [list]
Functions defined: [key public functions]
Tables created: [if applicable]
MOCK_MODE: [True/False]
Blockers: [any issues or None]
Notes: [anything the Architect needs to know]
---END SUMMARY---

---

## Test Prompt Format

## SLATE Build — Round [N] — Test

### What Was Built This Round
[List of modules/files]

### Test Instructions
1. [command or function call]
   Expected: [what success looks like]

2. [command or function call]
   Expected: [what success looks like]

### On Completion

---TEST RESULT---
Round: [N]
Date: [today]
Tests run: [number]
Passed: [number]
Failed: [number]
Details:
  - [test 1]: PASS / FAIL — [one line]
  - [test 2]: PASS / FAIL — [one line]
Blockers for next round: [failures that block Round N+1 or None]
---END TEST RESULT---

---

## Architect Rules

1. Never more than 4 instances per round
2. Round 1 is always scaffold only — one instance
3. Read every summary before generating next round
4. Never generate Round N+1 if Round N has unresolved failures
5. Test prompt always runs last, no exceptions
6. All modules start MOCK_MODE = True
7. State lives in summaries — they must be complete and honest

---

## SLATE Round Structure

### Round 1 — Scaffold (1 instance)
- Instance 1: main.py + config.py + database.py + models + 
  stub pipeline modules + stub webhooks router
- Test: FastAPI starts, Supabase connects, models import cleanly

### Round 2 — Database + Brand Analyser (2 instances)
- Instance 1: Create Supabase tables (carousel_jobs, 
  brand_profiles, pipeline_runs)
- Instance 2: brand_analyser.py — Haiku vision (MOCK_MODE = True)
- Test: Tables exist, brand_analyser returns mock BrandAnalysis

### Round 3 — Style Analyser + Question Generator (2 instances)
- Instance 1: style_analyser.py — Haiku vision (MOCK_MODE = True)
- Instance 2: question_generator.py — Haiku text (MOCK_MODE = True)
- Test: Both return correct mock output types

### Round 4 — Brief Builder (1 instance)
- Instance 1: brief_builder.py — Sonnet (MOCK_MODE = True then REAL)
- Test: Sonnet returns valid slide-by-slide JSON brief

### Round 5 — Canva Builder (1 instance)
- Instance 1: canva_builder.py — Canva MCP (MOCK_MODE = True)
- Test: Returns mock Canva URL without errors

### Round 6 — Orchestrator + Slack Webhooks (2 instances)
- Instance 1: orchestrator.py — full pipeline wired (MOCK_MODE)
- Instance 2: routers/webhooks.py — Slack slash command + 
  thread reply poller
- Test: /slate command triggers full mock pipeline end to end

### Round 7 — Real Mode (sequential, 1 module at a time)
- Turn off MOCK_MODE one module at a time
- Test after each one
- Canva builder last

### Round 8 — Railway Deployment (1 instance)
- Procfile + railway.json + env vars
- Test: Live Railway URL returns /health 200