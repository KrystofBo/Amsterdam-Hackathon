---
name: idea-synthesizer
description: >
  Reference skill for the "Idea Synthesizer" hackathon project — a Discord bot that takes chaotic brain dumps
  from team members and fuses them into a scored, cohesive project pitch using dual AI agents (Synthesizer + Critic)
  powered by OpenClaw. Use this skill whenever working on the Discord bot, the agent prompts, the evaluation matrix,
  or any part of this hackathon project. Also trigger when the user mentions "idea synthesizer", "brain dump",
  "synthesizer bot", "critic agent", "evaluation matrix", "openclaw", or asks about the hackathon project architecture.
---

# Idea Synthesizer — Project Hub

## How This Skill Is Organized

This skill follows a **hub-and-spoke** pattern. SKILL.md (this file) is the hub — it holds the project vision, architecture, and decision context that you need on every interaction. Detailed implementation knowledge lives in spoke files under `references/` and `prompts/`, loaded only when relevant. This keeps the main context lean while preserving deep knowledge for when it's needed.

```
idea-synthesizer/
├── SKILL.md                              ← You are here (the hub)
├── references/
│   ├── openclaw-integration.md           ← OpenClaw API, gateway, memory, config
│   └── discord-bot-implementation.md     ← Bot commands, file structure, env setup
└── prompts/
    └── god-prompt.md                     ← Combined Synthesizer+Critic system prompt
```

### When to read which file

| You're working on... | Read this |
|---|---|
| OpenClaw API calls, agent config, gateway setup | `references/openclaw-integration.md` |
| Bot commands, Discord setup, environment, running the bot | `references/discord-bot-implementation.md` |
| Modifying the Synthesizer/Critic prompt or output format | `prompts/god-prompt.md` |
| Understanding the project vision, architecture, or team roles | Stay here (SKILL.md) |

---

## What We're Building

A Discord bot that solves the most painful part of any group project: getting everyone on the same page at the start. Team members dump their raw, unstructured ideas into a Discord channel, and the bot synthesizes them into a single cohesive project pitch with a structured scorecard. The team can then push back ("make it easier to build") and the system iterates without starting over.

## Architecture

```
Discord Channel (multiple users post ideas)
        │
        ▼
   Discord Bot (Person B) ──── discord-bot/bot.py
   Collects !dump messages, tags by user
   Triggers synthesis on !synthesize
        │
        ▼
   OpenClaw Gateway ──── localhost:18789
   POST /v1/chat/completions
        │
        ▼
   Synthesizer + Critic Agent(s)
   Fuses ideas → Scores with Evaluation Matrix
        │
        ▼
   Discord Channel (formatted embed with scores)
```

## The Evaluation Matrix

Every synthesized pitch is scored on:

| Metric | Scoring |
|---|---|
| **Novelty** | 1-10: Unique twist from combined inputs? |
| **Technical Difficulty** | 1-10: Buildable in a hackathon? (7+ = probably won't finish) |
| **Inclusivity** | Percentage: Did every team member's idea make it in? |
| **Why It Fails** | One-sentence biggest risk |

## The Feedback Loop (Core Differentiator)

1. **Dump** — Users post ideas freely with `!dump`
2. **Synthesize** — `!synthesize` batches ideas → OpenClaw → scored pitch
3. **Pushback** — `!feedback make it easier` sends constraints into existing context
4. **Pivot** — Agent adjusts the concept (doesn't restart), Critic rescores

The conversation history is maintained in `team_store.py` so each feedback round builds on the last.

## Team Roles

| Role | Person | Lane |
|---|---|---|
| Prompt Engineer | A | OpenClaw agent config, system prompts, API keys |
| Plumber | B (you) | Discord bot, message capture, formatting, wiring to OpenClaw |
| Pitch Lead | C | QA testing, dummy data, pitch script, demo recording |

## Current State

- **Bot scaffolded:** `discord-bot/` has all files (bot.py, team_store.py, openclaw_client.py)
- **Conda env ready:** `idea-synth` with discord.py 2.7.1, aiohttp, python-dotenv
- **Next step:** Discord Developer Portal — create app, get bot token, enable Message Content Intent, invite to server
- **After that:** Test bot locally, then connect to OpenClaw gateway

## Demo Strategy

Show the feedback loop in action:
1. Multiple users posting different ideas
2. Bot synthesizes into a scored pitch
3. User types "make it easier"
4. Bot intelligently strips the hardest feature, preserves novelty
5. Updated scores reflect the change

## Hackathon Survival Note

If the two-agent pipeline isn't ready, the God Prompt in `openclaw_client.py` handles both Synthesizer and Critic in a single LLM call. See `prompts/god-prompt.md` for the full prompt and migration path.

---

## Creating New Skills for This Project

If you need to add more skills (e.g., a skill for Person A's prompt engineering, or a skill for demo scripting), follow this hub-and-spoke pattern:

1. **Create a directory** named after the skill under the project root
2. **Write SKILL.md** as the hub — keep it under 200 lines with:
   - YAML frontmatter (`name`, `description` — make the description trigger-happy)
   - Project context that's needed on every interaction
   - A file map table showing when to read each spoke file
3. **Put deep knowledge in `references/`** — one file per domain (API docs, implementation details, third-party tool guides)
4. **Put prompts in `prompts/`** — system prompts, templates, output format specs
5. **Put scripts in `scripts/`** — any automation, build steps, or helper scripts
6. **Update the hub** whenever the project state changes (new files, new decisions, completed milestones)

The goal: anyone (human or AI) reading SKILL.md gets oriented in 30 seconds, then drills into spokes only for the specific thing they're working on.
