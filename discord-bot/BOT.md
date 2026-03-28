# Idea Synthesizer Bot

A Discord bot that turns chaotic team brainstorming into a scored, cohesive project pitch. Multiple team members dump their raw ideas into a channel, the bot fuses them through an AI agent pipeline (OpenClaw), and returns a structured pitch with a brutally honest evaluation. The team pushes back, the bot adjusts — no restarting from scratch.

## Commands

| Command | What it does |
|---------|-------------|
| `!dump <idea>` | Add your idea to the pool. Tagged with your name so the system knows who contributed what. |
| `!synthesize` | Fuse all collected ideas into a unified project pitch + Evaluation Matrix. |
| `!feedback <text>` | Push back on the current pitch. The bot adjusts the existing concept based on your constraint. |
| `!status` | Show dump count, contributors, whether synthesis has happened, and how many feedback rounds. |
| `!clear` | Wipe all ideas and conversation history for the channel. Start fresh. |
| `!help` | Show the command list in Discord. |

## How It Works

### 1. Brain Dump Collection

Team members post ideas using `!dump`. Each message is stored in memory, tagged with the author's Discord display name. Ideas accumulate per channel — each channel acts as a separate team room, so multiple teams can use the same bot without interference.

```
User A: !dump I want to build something with Web3 and decentralized identity
User B: !dump Let's make an educational tool that teaches coding through games
User C: !dump I found this cool NASA API for real-time satellite data
```

### 2. Synthesis

When someone runs `!synthesize`, the bot:

1. Collects all brain dumps for the channel
2. Groups them by contributor
3. Sends them to OpenClaw's gateway (`POST /v1/chat/completions`)
4. The AI agent acts as both **Synthesizer** (fuses the ideas into one pitch) and **Critic** (scores it)
5. Returns the result to the channel

### 3. Evaluation Matrix

Every pitch comes with a scorecard:

| Metric | What it measures |
|--------|-----------------|
| **Novelty** (1-10) | Is there a unique twist, or is it generic? |
| **Technical Difficulty** (1-10) | Can this actually be built in a hackathon? 7+ means probably not. |
| **Inclusivity** (%) | Did every team member's idea make it into the pitch? |
| **Why It Might Fail** | One sentence — the single biggest risk. |

### 4. Feedback Loop

This is the core feature. After seeing the pitch, team members push back:

```
User A: !feedback Technical difficulty is too high. Simplify the backend but keep the NASA data.
```

The bot feeds this constraint into the **existing conversation context** — it doesn't start over. The agent adjusts the concept and the Critic rescores. This loop repeats until the team agrees.

The conversation history is maintained in memory, so each round builds on the last.

## Architecture

```
Discord Channel
    │
    │  !dump messages accumulate
    │  !synthesize triggers pipeline
    │
    ▼
bot.py (Discord bot)
    │  Captures messages, tags by user
    │  Manages conversation history
    │
    ├── team_store.py
    │     In-memory store
    │     Brain dumps per channel, tagged by user
    │     Conversation history for feedback loop
    │
    ├── openclaw_client.py
    │     Sends to OpenClaw REST API
    │     POST /v1/chat/completions
    │     Includes system prompt + conversation context
    │
    ▼
OpenClaw Gateway (localhost:18789)
    │  Routes to configured agent
    │  Maintains its own memory layer
    │
    ▼
LLM (Claude / OpenAI / DeepSeek)
    │  Synthesizes ideas
    │  Scores with Evaluation Matrix
    │
    ▼
Discord Channel (formatted response)
```

## File Structure

```
discord-bot/
├── bot.py              — Main bot: command handlers, message splitting, Discord embeds
├── team_store.py       — Brain dump storage + conversation history per channel
├── openclaw_client.py  — OpenClaw API client + system prompt (God Prompt fallback)
├── requirements.txt    — discord.py, aiohttp, python-dotenv
├── .env                — Secrets (DISCORD_TOKEN, OPENCLAW_TOKEN) — not committed
├── .env.example        — Template showing required variables
└── .gitignore          — Excludes .env and node_modules/
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token from Discord Developer Portal |
| `OPENCLAW_URL` | No | `http://localhost:18789` | OpenClaw gateway URL |
| `OPENCLAW_TOKEN` | Yes | — | Bearer token for OpenClaw API auth |
| `OPENCLAW_AGENT_ID` | No | `synthesizer` | Which OpenClaw agent to route to |

## Setup

### Prerequisites
- Conda (miniconda or anaconda)
- A Discord server you can add bots to
- OpenClaw running locally (or planned)

### Steps

1. **Create the conda environment:**
   ```bash
   conda create -n idea-synth python=3.11 -y
   conda activate idea-synth
   pip install -r requirements.txt
   ```

2. **Set up the Discord bot:**
   - Go to https://discord.com/developers/applications
   - Create a new Application
   - Bot tab → Reset Token → copy it
   - Enable **Message Content Intent** under Privileged Gateway Intents
   - OAuth2 → URL Generator → scope: `bot` → permissions: `Send Messages`, `Read Message History`, `Embed Links`
   - Open the generated URL to invite the bot to your server

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Paste your DISCORD_TOKEN into .env
   # Add OPENCLAW_TOKEN when OpenClaw is configured
   ```

4. **Run:**
   ```bash
   conda activate idea-synth
   python bot.py
   ```

## Key Design Decisions

**Channel = Team.** Each Discord channel is an isolated team room. Brain dumps, conversation history, and synthesis state are all scoped per channel.

**Tagged ingestion.** Every dump is stored with the author's display name. The Synthesizer sees who said what, and the Critic can score whether everyone's ideas were included.

**Conversation memory for feedback.** The `TeamStore` keeps a rolling list of user/assistant message turns. On each `!feedback`, the full history is replayed to the LLM so it adjusts rather than restarts.

**God Prompt fallback.** The system prompt in `openclaw_client.py` makes a single LLM call act as both Synthesizer and Critic. When Person A's two-agent pipeline is ready, this can be swapped out.

**Message splitting.** Discord caps messages at 2000 characters. Long responses are split at newline boundaries to keep formatting intact.

## Hackathon Context

This bot is part of a 3-person hackathon project:

| Person | Role | Focus |
|--------|------|-------|
| A | Prompt Engineer | OpenClaw agent config, Synthesizer & Critic prompts |
| B | Plumber | This Discord bot — capture, format, wire to agents |
| C | Pitch Lead | QA testing, dummy data, demo recording |

The demo should highlight the feedback loop: show the bot propose a complex idea, a user type "make it easier," and the bot intelligently simplify while preserving novelty.
