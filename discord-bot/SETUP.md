# Deployer Setup Guide

This guide is for whoever is hosting the bot (Person B). Regular Discord users don't need to do any of this — they just type commands in Discord.

## Architecture

```
Discord Users  ──→  Discord Bot  ──→  OpenClaw Gateway  ──→  LLM (Claude/OpenAI/etc.)
 (everyone)        (you host this)    (you host this)        (API call)
```

You host both the Discord bot and OpenClaw on the same machine. Everyone else just uses Discord.

## Prerequisites

- Python 3.9+ with conda
- Node.js 22.16+ (for OpenClaw)
- A Discord server you have admin access to

## Step 1: Install OpenClaw

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

This installs OpenClaw and registers it as a background service. Default install: `~/.openclaw/`.

## Step 2: Create the Synthesizer Agent

```bash
openclaw agents add synthesizer
```

This creates a new agent called "synthesizer" with its own workspace and config.

## Step 3: Configure the LLM Provider

OpenClaw needs an LLM to do the actual synthesis. Configure it with your API key:

```bash
# For Anthropic Claude:
openclaw agents auth synthesizer --provider anthropic --api-key YOUR_ANTHROPIC_KEY

# For OpenAI:
openclaw agents auth synthesizer --provider openai --api-key YOUR_OPENAI_KEY
```

Alternatively, edit the auth profile directly:
`~/.openclaw/agents/synthesizer/agent/auth-profiles.json`

## Step 4: Start the OpenClaw Gateway

```bash
openclaw gateway --port 18789 --verbose
```

Leave this running in a terminal (or it runs as a daemon if you used `--install-daemon`).

Verify it's up:
```bash
curl http://localhost:18789
```

## Step 5: Set Up the Discord Bot

### Create the Bot on Discord

1. Go to https://discord.com/developers/applications
2. Click **New Application** → name it (e.g., "Idea Synthesizer")
3. Go to **Bot** tab:
   - Click **Reset Token** → copy the token
   - Enable **Message Content Intent** under Privileged Gateway Intents
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions:
     - `Send Messages`
     - `Read Message History`
     - `Embed Links`
     - `Manage Channels` (for creating project channels)
     - `Manage Roles` (for granting channel access)
5. Open the generated URL to invite the bot to your server

### Configure the Bot

```bash
cd discord-bot/
cp .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=paste_your_discord_bot_token_here
OPENCLAW_URL=http://localhost:18789
OPENCLAW_TOKEN=paste_your_openclaw_api_token_here
OPENCLAW_AGENT_ID=synthesizer
PROJECT_CATEGORY=PROJECTS
```

To find your OpenClaw API token:
```bash
openclaw config get api-token
```

### Install Dependencies and Run

```bash
conda create -n idea-synth python=3.11 -y
conda activate idea-synth
pip install -r requirements.txt
python bot.py
```

## Step 6: Verify Everything Works

In any Discord channel on your server, type:

```
!health
```

You should see a green embed saying "All systems operational" with Gateway Reachable: Yes and API Responding: Yes.

If you see red, check the troubleshooting tips in the embed.

## Troubleshooting

### "Cannot connect to OpenClaw"
- Is the gateway running? `openclaw gateway --port 18789 --verbose`
- Is the URL correct in `.env`? Default is `http://localhost:18789`

### "API returned 401"
- Wrong or missing `OPENCLAW_TOKEN` in `.env`
- Get the correct token: `openclaw config get api-token`

### "API returned 404" or agent not found
- Agent doesn't exist. Create it: `openclaw agents add synthesizer`
- Check existing agents: `openclaw agents list`

### "Missing Permissions" when creating projects
- Re-invite the bot with **Manage Channels** and **Manage Roles** permissions
- Or go to Server Settings → Roles → find the bot's role → enable those permissions

### Bot responds twice
- You have multiple instances running. Kill all and restart one:
  ```bash
  # Windows
  taskkill /F /IM python.exe
  # macOS/Linux
  pkill -f bot.py
  ```
  Then start one instance: `python bot.py`

## Hosting for Production

For the hackathon, running locally is fine. For longer-term hosting:

- **Keep it local**: Run on your machine with both OpenClaw and the bot
- **VPS**: Deploy both to a $5/month server (DigitalOcean, Hetzner, etc.)
- **Split**: Bot on a VPS, OpenClaw on your local machine with a tunnel (ngrok, Tailscale)

The key thing: the bot and OpenClaw just need to be able to talk to each other over HTTP.
