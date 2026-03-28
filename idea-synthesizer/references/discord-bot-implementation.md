# Discord Bot Implementation Reference

## Environment

- **Conda env:** `idea-synth` (Python 3.11)
- **Dependencies:** discord.py 2.7.1, aiohttp 3.13.3, python-dotenv 1.2.2
- **Bot directory:** `discord-bot/`

## File Structure

```
discord-bot/
├── bot.py              — Main bot: command handlers, message routing, Discord embeds
├── team_store.py       — In-memory store: brain dumps tagged by user, conversation history
├── openclaw_client.py  — OpenClaw API client: sends to /v1/chat/completions, manages context
├── requirements.txt    — Python dependencies
├── .env.example        — Template for secrets (DISCORD_TOKEN, OPENCLAW_URL, etc.)
└── .gitignore          — Excludes node_modules/ and .env
```

## Commands

| Command | What it does |
|---------|-------------|
| `!dump <idea>` | Add a brain dump to the pool, tagged with the author's name |
| `!synthesize` | Batch all dumps, send to OpenClaw, return scored pitch + Evaluation Matrix |
| `!feedback <text>` | Push back on the current pitch — re-synthesizes with constraint in context |
| `!status` | Show dump count, contributors, synthesis state, feedback rounds |
| `!clear` | Wipe all dumps and conversation history for the channel |
| `!help` | Show command reference as a Discord embed |

## Key Design Decisions

### Channel-Scoped Teams
Each Discord channel is treated as a separate "team room." Brain dumps and conversation history are isolated per channel. This means multiple teams can use the same bot in different channels without interference.

### Tagged Ingestion
Every brain dump is stored with the author's `display_name` and `user_id`. When formatting for the agent, dumps are grouped by user so the Synthesizer can see who contributed what and the Critic can score inclusivity.

### Conversation History for Feedback Loop
The `TeamStore` maintains a list of conversation turns (`role: user/assistant`) per channel. On first `!synthesize`, the brain dumps are sent as the initial user message. On `!feedback`, the user's constraint is appended and the full history is replayed to OpenClaw, so the agent adjusts the existing concept rather than starting over.

### Message Splitting
Discord has a 2000-character limit. The bot splits long responses at newline boundaries to keep formatting clean across chunks.

### God Prompt Fallback
The `openclaw_client.py` includes a combined Synthesizer+Critic system prompt. This is the "God Prompt" fallback — if Person A's two-agent pipeline isn't ready, this single prompt handles both roles. Person A can replace the `SYSTEM_PROMPT` constant with their refined version or reconfigure OpenClaw to use separate agents.

## Running the Bot

```bash
conda activate idea-synth
cd discord-bot/
cp .env.example .env
# Fill in DISCORD_TOKEN and OpenClaw credentials
python bot.py
```

## Discord Bot Setup (Developer Portal)

1. Go to https://discord.com/developers/applications
2. Create new Application → name it "Idea Synthesizer"
3. Go to **Bot** tab → Reset Token → copy it → paste into `.env` as `DISCORD_TOKEN`
4. Enable **Message Content Intent** under Privileged Gateway Intents
5. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Read Message History`, `Embed Links`
6. Copy the generated URL → open in browser → invite to your server

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token from Discord Developer Portal |
| `OPENCLAW_URL` | No | `http://localhost:18789` | OpenClaw gateway URL |
| `OPENCLAW_TOKEN` | Yes | — | Bearer token for OpenClaw API |
| `OPENCLAW_AGENT_ID` | No | `synthesizer` | Which OpenClaw agent to route to |
