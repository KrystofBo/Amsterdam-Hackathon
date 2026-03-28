# Deployer Setup Guide

This guide is for whoever is hosting the bot (Person B). Regular Discord users don't need to do any of this — they just type commands in Discord.

## Architecture

```
Discord Users  ──→  Discord Bot  ──→  OpenClaw Gateway  ──→  LLM (Claude/OpenAI/etc.)
 (everyone)        (you host this)    (you host this)        (API call)
```

You host both the Discord bot and OpenClaw on the same machine. Everyone else just uses Discord.

## Script Shortcut

If you want the common commands in one place, use:

```bash
cd discord-bot/
./manage.sh help
```

Useful shortcuts:

```bash
./manage.sh setup-openclaw
./manage.sh configure-openai-auth
./manage.sh apply-model-config
./manage.sh show-model
./manage.sh run-openclaw
./manage.sh run-openclaw-lan   # better fallback on WSL
./manage.sh show-token
./manage.sh install-bot-deps
./manage.sh run-bot
```

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
openclaw agents add synthesizer \
  --workspace ~/.openclaw/workspace-synthesizer \
  --non-interactive \
  --json
```

This creates a new agent called "synthesizer" with its own workspace and config.

## Step 3: Configure the LLM Provider

Recent OpenClaw versions handle provider auth during onboarding and store it in
the main OpenClaw config. If you have not already connected a provider, rerun:

```bash
openclaw onboard
```

Confirm the active config file and provider settings if needed:

```bash
openclaw config file
```

For this bot, the recommended pattern is:

1. Keep the bot talking to the agent via `OPENCLAW_CHAT_MODEL=openclaw:synthesizer`
2. Turn `USE_OPENAI_API=true` when you want the synthesizer agent to use OpenAI
3. Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`
4. Run `./manage.sh run-bot`

To store an OpenAI API key for the synthesizer agent:

```bash
cd discord-bot/
./manage.sh configure-openai-auth
```

If `OPENAI_API_KEY` is set in `.env`, that same command will use the env value
instead of prompting.

## Step 4: Start the OpenClaw Gateway

```bash
openclaw config set gateway.http.endpoints.chatCompletions.enabled true --strict-json
openclaw gateway run --port 18789 --verbose
```

Leave this running in a terminal (or it runs as a daemon if you used `--install-daemon`).

Verify it's up:
```bash
curl http://localhost:18789
```

If you're on WSL and `systemd --user` is unavailable, run the gateway in the
foreground instead of relying on the service manager. If `loopback` bind fails
in your environment, use `openclaw gateway run --bind lan --port 18789 --verbose`
and restrict access to your local machine/network.

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
USE_OPENAI_API=true
OPENAI_API_KEY=paste_your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENCLAW_CHAT_MODEL=openclaw:synthesizer
OPENCLAW_AGENT_MODEL_ALIAS=synthesizer-default
OPENCLAW_AGENT_MODEL=
OPENCLAW_OPENAI_PROFILE_ID=openai:manual
PROJECT_CATEGORY=PROJECTS
```

If you use `manage.sh run-bot`, it will automatically:

1. check `USE_OPENAI_API`
2. sync `OPENAI_API_KEY` from `.env` into OpenClaw
3. point the synthesizer alias at `openai/$OPENAI_MODEL`
4. start the bot

If you use `manage.sh run-openclaw` or `manage.sh run-openclaw-lan`, it will do
the same sync/apply steps before starting the gateway. This matters because
plain `openclaw gateway run` does not read the bot's `.env` file.

You can also apply the selected backing model manually:

```bash
./manage.sh apply-model-config
./manage.sh show-model
```

From then on, switching models is just:

```bash
# edit USE_OPENAI_API / OPENAI_API_KEY / OPENAI_MODEL in .env
./manage.sh run-openclaw
./manage.sh run-bot
```

To find your OpenClaw API token:
```bash
openclaw config get gateway.auth.token
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
- Is the gateway running? `openclaw gateway run --port 18789 --verbose`
- Is the URL correct in `.env`? Default is `http://localhost:18789`

### "API returned 401"
- Wrong or missing `OPENCLAW_TOKEN` in `.env`
- Get the correct token: `openclaw config get gateway.auth.token`

### "API returned 404" or agent not found
- Agent doesn't exist. Create it: `openclaw agents add synthesizer --workspace ~/.openclaw/workspace-synthesizer --non-interactive --json`
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
