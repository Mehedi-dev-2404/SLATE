Create the file CLAUDE.md in the project root with exactly this content:

# SLATE — Claude Code Instructions

## Project
SLATE is an AI-powered Instagram carousel agent. It analyses brand 
materials, understands style preferences via Slack, and generates 
carousel briefs + Canva designs. Stack: Python, FastAPI, Supabase, 
Railway, Claude API (Haiku + Sonnet), Slack, Canva MCP.

## The WAT Architecture
This project follows the WAT framework (Workflows, Agents, Tools).

- Workflows: instructions and SOPs — stored in .claude/skills/
- Agents: you (Claude Code) — read the workflow, execute the task,
  report back
- Tools: Python modules in pipeline/, routers/ — deterministic 
  execution only

Your job is orchestration and decision-making. Offload all 
execution to the modules. Never try to do in a prompt what 
should be done in a Python function.

## How You're Being Used
This project is built using the multi-instance build workflow.
Read .claude/skills/multi-instance-build.md to understand the 
full process.

You will receive one focused prompt per instance. Do exactly 
what the prompt says. Nothing more. When done, output the 
summary block exactly as specified in the skill.

## Standing Rules
- MOCK_MODE = True on every new module unless told otherwise
- Use service role key for Supabase, never anon key
- Never commit .env or any credentials file
- Store all secrets as Railway env vars, never as files
- Use print(flush=True) for all logging
- Strip ```json fences before parsing any Claude API response
- Use .execute() not .single() for Supabase queries
- Never touch files outside your assigned task for this round
- If something is unclear, make a decision and note it in 
  your summary — do not stop and ask

## File Structure
pipeline/          ← AI agent modules (brand_analyser, style_analyser,
                      question_generator, brief_builder, canva_builder,
                      orchestrator)
routers/           ← FastAPI endpoints and Slack webhooks
models/            ← Pydantic data models (carousel.py, job.py)
.claude/skills/    ← Claude Code workflow skills
test.md            ← test log, append only, never delete
rounds.md          ← round summaries, append only, never delete

## Environment Variables
See config.py for the full list. All loaded via pydantic-settings.
ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY,
SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_WEBHOOK_URL,
CANVA_API_KEY

## Model Strategy
- Brand/style analysis (vision): claude-haiku-4-5-20251001
- Question generation: claude-haiku-4-5-20251001
- Carousel brief generation: claude-sonnet-4-6
- Canva MCP calls: no model — direct API

## After Every Round
- Append test result to test.md
- Append all instance summaries to rounds.md