# Idea Synthesizer Bot

A Discord bot that turns chaotic team brainstorming into a scored, cohesive project pitch. Multiple team members dump their raw ideas into a channel, the bot fuses them through an AI agent pipeline (OpenClaw), and returns a structured pitch with a brutally honest evaluation. The team pushes back, the bot adjusts — no restarting from scratch.

## Commands

| Command | What it does |
|---------|-------------|
| `!lobby` | Post the welcome panel with Create/Join project buttons. |
| `!dump <idea>` | Add your idea to the pool. Tagged with your name so the system knows who contributed what. |
| `!synthesize` | Fuse all collected ideas into a unified project pitch + Evaluation Matrix. |
| `!feedback <text>` | Push back on the current pitch. The bot adjusts the existing concept based on your constraint. |
| `!project <name>` | Name this channel's project (e.g., `!project NASA Edu Game`). |
| `!projects` | List all active projects across the server with stats. |
| `!status` | Show dump count, contributors, whether synthesis has happened, and how many feedback rounds. |
| `!health` | Check if the OpenClaw backend is connected and responding. |
| `!clear` | Wipe all ideas and conversation history for the channel. Start fresh. |
| `!help` | Show the command list in Discord. |

## Getting Started (For Users)

### 1. Create or Join a Project

In the lobby channel, type `!lobby`. You'll see two buttons:

- **Create Project** — Click it, type a name, and the bot creates a new channel for your team
- **Join Project** — Click it, pick an existing project from the dropdown, and you're in

### 2. Dump Your Ideas

In your project's channel, post ideas:

```
!dump I want to build something with Web3 and decentralized identity
!dump Let's make an educational tool that teaches coding through games
!dump I found this cool NASA API for real-time satellite data
```

Each team member posts their own ideas. The bot tags everything by author.

### 3. Synthesize

When everyone's ready:

```
!synthesize
```

The bot fuses all ideas into a single project pitch with a scorecard.

### 4. Push Back

Don't like something? Push back:

```
!feedback Technical difficulty is too high. Simplify the backend but keep the NASA data.
```

The bot adjusts the existing concept and rescores — it doesn't start over.

### 5. Repeat Until Happy

Keep giving feedback. Each round builds on the last.

## Evaluation Matrix

Every pitch comes with a scorecard:

| Metric | What it measures |
|--------|-----------------|
| **Novelty** (1-10) | Is there a unique twist, or is it generic? |
| **Technical Difficulty** (1-10) | Can this actually be built in a hackathon? 7+ means probably not. |
| **Inclusivity** (%) | Did every team member's idea make it into the pitch? |
| **Why It Might Fail** | One sentence — the single biggest risk. |

## Architecture

```
Discord Server
    │
    ├── #lobby → !lobby → [Create Project] [Join Project]
    │
    └── PROJECTS category
        ├── #project-1 → !dump, !synthesize, !feedback
        └── #project-2 → !dump, !synthesize, !feedback
              │
              ▼
        bot.py (Discord bot)
            ├── team_store.py (ideas + conversation history per channel)
            └── openclaw_client.py (sends to OpenClaw with project-scoped context)
                    │
                    ▼
              OpenClaw Gateway (localhost:18789)
                    │
                    ▼
              LLM (Claude / OpenAI / DeepSeek)
```

Each project channel is fully isolated — different brain dumps, different conversation history, different synthesis. OpenClaw receives a project ID with every request so it never mixes contexts.

## File Structure

```
discord-bot/
├── bot.py              — Main bot: commands, lobby UI, health check, embeds
├── team_store.py       — Brain dump storage + project names + conversation history
├── openclaw_client.py  — OpenClaw API client + system prompt + health check
├── requirements.txt    — discord.py, aiohttp, python-dotenv
├── .env                — Secrets (DISCORD_TOKEN, OPENCLAW_TOKEN) — not committed
├── .env.example        — Template showing required variables
├── .gitignore          — Excludes .env and __pycache__/
├── BOT.md              — This file (user-facing docs)
└── SETUP.md            — Full deployer setup guide
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token from Discord Developer Portal |
| `OPENCLAW_URL` | No | `http://localhost:18789` | OpenClaw gateway URL |
| `OPENCLAW_TOKEN` | Yes | — | Bearer token for OpenClaw API auth |
| `OPENCLAW_AGENT_ID` | No | `synthesizer` | Which OpenClaw agent to route to |
| `USE_OPENAI_API` | No | `false` | When `true`, `manage.sh` switches the synthesizer agent to OpenAI |
| `OPENAI_API_KEY` | No | — | OpenAI API key used when `USE_OPENAI_API=true` |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` | OpenAI model name used when `USE_OPENAI_API=true` |
| `OPENCLAW_CHAT_MODEL` | No | `openclaw:synthesizer` | Chat completion target sent to OpenClaw |
| `OPENCLAW_AGENT_MODEL_ALIAS` | No | `synthesizer-default` | Alias name used for the agent's backing model |
| `OPENCLAW_AGENT_MODEL` | No | — | Advanced override for the full backing model id |
| `OPENCLAW_OPENAI_PROFILE_ID` | No | `openai:manual` | OpenClaw auth profile used for OpenAI |
| `PROJECT_CATEGORY` | No | `PROJECTS` | Discord category name for project channels |

## Setup

See `SETUP.md` for the full deployer guide (OpenClaw installation, agent creation, Discord bot setup, troubleshooting).

Quick start:

```bash
conda create -n idea-synth python=3.11 -y
conda activate idea-synth
pip install -r requirements.txt
cp .env.example .env
# Fill in DISCORD_TOKEN and OPENCLAW_TOKEN
python bot.py
```

If you want the synthesizer agent to run on OpenAI using only `.env`, set:

```env
USE_OPENAI_API=true
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4.1-mini
```

Then run:

```bash
./manage.sh run-bot
```

`manage.sh` will sync the API key into OpenClaw and apply the model alias before
starting the bot.

If you also start the gateway through `manage.sh run-openclaw`, it will use the
same `.env` values. Plain `openclaw gateway run` does not read this file.

Future model swaps are just:

```bash
# edit USE_OPENAI_API / OPENAI_API_KEY / OPENAI_MODEL in .env
./manage.sh run-openclaw
./manage.sh run-bot
```

## Key Design Decisions

**Channel = Isolated Project.** Each Discord channel is a separate project room. Brain dumps, conversation history, project names, and synthesis state are all scoped per channel. OpenClaw also receives a project ID to prevent context bleed.

**Lobby as entrypoint.** Users create or join projects via interactive buttons — no need to manually create channels or manage permissions.

**Tagged ingestion.** Every dump is stored with the author's display name. The Synthesizer sees who said what, and the Critic can score whether everyone's ideas were included.

**Conversation memory for feedback.** The `TeamStore` keeps a rolling list of user/assistant message turns. On each `!feedback`, the full history is replayed to the LLM so it adjusts rather than restarts.

**Health check.** `!health` pings the OpenClaw gateway and reports status with troubleshooting tips if something's wrong.

**God Prompt fallback.** The system prompt in `openclaw_client.py` makes a single LLM call act as both Synthesizer and Critic. When Person A's two-agent pipeline is ready, this can be swapped out.

**In-memory storage.** Currently all data lives in Python dicts — a bot restart loses everything. SQLite persistence is planned.
