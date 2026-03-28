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

This skill follows a **hub-and-spoke** pattern. SKILL.md (this file) is the hub — it holds the project vision, architecture, and decision context that you need on every interaction. Detailed implementation knowledge lives in spoke files under `references/` and `prompts/`, loaded only when relevant.

```
idea-synthesizer/
├── SKILL.md                              ← You are here (the hub)
├── references/
│   ├── openclaw-integration.md           ← OpenClaw API, gateway, memory, project isolation
│   └── discord-bot-implementation.md     ← Bot commands, lobby UI, file structure, env setup
└── prompts/
    └── god-prompt.md                     ← Combined Synthesizer+Critic system prompt
```

### When to read which file

| You're working on... | Read this |
|---|---|
| OpenClaw API calls, agent config, gateway setup, project isolation | `references/openclaw-integration.md` |
| Bot commands, lobby UI, Discord setup, environment, running the bot | `references/discord-bot-implementation.md` |
| Modifying the Synthesizer/Critic prompt or output format | `prompts/god-prompt.md` |
| Full deployer setup (OpenClaw + bot from scratch) | `discord-bot/SETUP.md` |
| Understanding the project vision, architecture, or team roles | Stay here (SKILL.md) |

---

## What We're Building

A Discord bot that solves the most painful part of any group project: getting everyone on the same page at the start. Team members dump their raw, unstructured ideas into a Discord channel, and the bot synthesizes them into a single cohesive project pitch with a structured scorecard. The team can then push back ("make it easier to build") and the system iterates without starting over.

## Architecture

```
Discord Server
    │
    ├── #lobby channel
    │   └── !lobby → [Create Project] [Join Project] buttons
    │         │
    │         ├── Create → modal → new #project-name channel under PROJECTS category
    │         └── Join → dropdown → grants access to existing project channel
    │
    ├── PROJECTS category
    │   ├── #nasa-edu-game     ← isolated project room
    │   ├── #web3-identity     ← isolated project room
    │   └── ...
    │
    └── Each project channel:
        !dump → collect ideas → !synthesize → OpenClaw → scored pitch → !feedback → iterate
```

```
Discord Bot (Person B) ──── discord-bot/bot.py
        │
        ▼
OpenClaw Gateway ──── localhost:18789
POST /v1/chat/completions (project-scoped context)
        │
        ▼
LLM (Claude / OpenAI / DeepSeek)
Synthesizer + Critic → Evaluation Matrix
```

## Commands

| Command | What it does |
|---------|-------------|
| `!lobby` | Post the welcome panel with Create/Join project buttons |
| `!dump <idea>` | Add a brain dump to the pool, tagged with your name |
| `!synthesize` | Fuse all ideas into a scored project pitch via OpenClaw |
| `!feedback <text>` | Push back on the pitch — re-synthesizes with your constraint |
| `!project <name>` | Name this channel's project |
| `!projects` | List all active projects across channels |
| `!status` | Show dump count, contributors, synthesis state |
| `!health` | Check if OpenClaw gateway is connected and responding |
| `!clear` | Wipe all ideas and conversation history |
| `!help` | Show command reference |

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

The conversation history is maintained in `team_store.py` so each feedback round builds on the last. Each project channel gets its own isolated context — OpenClaw receives a project ID and name with every request to prevent cross-contamination.

## Team Roles

| Role | Person | Lane |
|---|---|---|
| Prompt Engineer | A | OpenClaw agent config, system prompts, API keys |
| Plumber | B (you) | Discord bot, message capture, formatting, wiring to OpenClaw |
| Pitch Lead | C | QA testing, dummy data, pitch script, demo recording |

## Current State

- **Bot running:** Connected to Discord as `Project Bot#4958`
- **Lobby UI:** `!lobby` posts interactive Create/Join project buttons
- **Project isolation:** Each channel is scoped — OpenClaw gets project ID per request
- **Health check:** `!health` verifies OpenClaw gateway connectivity
- **Conda env:** `idea-synth` (Python 3.11, discord.py 2.7.1, aiohttp, python-dotenv)
- **Pending:** Bot needs Manage Channels + Manage Roles permissions for lobby to create channels
- **Pending:** Connect to live OpenClaw instance for actual synthesis
- **Pending:** Data persistence (currently in-memory only — restarts lose everything)

## Demo Strategy

Show the feedback loop in action:
1. `!lobby` → Create a project → team members join
2. Multiple users posting different ideas with `!dump`
3. `!synthesize` → scored pitch with Evaluation Matrix
4. User types `!feedback make it easier`
5. Bot intelligently strips the hardest feature, preserves novelty, updated scores

## Hackathon Survival Note

If the two-agent pipeline isn't ready, the God Prompt in `openclaw_client.py` handles both Synthesizer and Critic in a single LLM call. See `prompts/god-prompt.md` for the full prompt and migration path.

---

## Creating New Skills for This Project

Follow this hub-and-spoke pattern:

1. **Create a directory** named after the skill under the project root
2. **Write SKILL.md** as the hub — keep it under 200 lines
3. **Put deep knowledge in `references/`** — one file per domain
4. **Put prompts in `prompts/`** — system prompts, templates, output format specs
5. **Put scripts in `scripts/`** — any automation, build steps, or helper scripts
6. **Update the hub** whenever the project state changes
