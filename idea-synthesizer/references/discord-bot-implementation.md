# Discord Bot Implementation Reference

## Environment

- **Conda env:** `idea-synth` (Python 3.11)
- **Dependencies:** discord.py 2.7.1, aiohttp 3.13.3, python-dotenv 1.2.2
- **Bot directory:** `discord-bot/`

## File Structure

```
discord-bot/
├── bot.py              — Main bot: commands, lobby UI, health check, Discord embeds
├── team_store.py       — In-memory store: brain dumps, project names, conversation history
├── openclaw_client.py  — OpenClaw API client: synthesis, health check, project-scoped context
├── requirements.txt    — Python dependencies
├── .env.example        — Template for secrets
├── .env                — Actual secrets (not committed)
├── .gitignore          — Excludes .env and __pycache__/
├── BOT.md              — User-facing bot documentation
└── SETUP.md            — Full deployer setup guide (OpenClaw + bot)
```

## Commands

| Command | What it does |
|---------|-------------|
| `!lobby` | Post the welcome panel with interactive Create/Join project buttons |
| `!dump <idea>` | Add a brain dump to the pool, tagged with the author's name |
| `!synthesize` | Batch all dumps, send to OpenClaw with project context, return scored pitch |
| `!feedback <text>` | Push back on the current pitch — re-synthesizes with constraint in context |
| `!project <name>` | Name this channel's project |
| `!projects` | List all active projects across all channels |
| `!status` | Show dump count, contributors, synthesis state, feedback rounds |
| `!health` | Check if OpenClaw gateway is reachable and the agent is responding |
| `!clear` | Wipe all dumps, conversation history, and project name for the channel |
| `!help` | Show command reference as a Discord embed |

## Lobby UI (Interactive Buttons)

The `!lobby` command posts an embed with two persistent buttons:

- **Create Project** (green) → Opens a modal where you type the project name → Bot creates a new text channel under a "PROJECTS" category → Posts a welcome message with instructions
- **Join Project** (blue) → Shows a dropdown of existing project channels (from both the store and the PROJECTS category) → Grants the user read/write access to the selected channel

Buttons use `custom_id` and are re-registered on bot startup via `bot.add_view(LobbyView())`, so they survive restarts.

**Required bot permissions for lobby:**
- `Manage Channels` — to create project channels and the PROJECTS category
- `Manage Roles` — to grant users access when they join a project

## Health Check

`!health` pings the OpenClaw gateway with a 5-second timeout:

1. Checks if the gateway URL is reachable (GET request)
2. Calls authenticated `GET /v1/models` to verify the configured agent is exposed
3. Returns a green embed if all good, or a red embed with specific troubleshooting tips

The `OpenClawClient.health_check()` method returns a dict with `gateway_reachable`, `api_responding`, and `error` fields.

## Key Design Decisions

### Channel = Isolated Project
Each Discord channel is a separate project room. Brain dumps, conversation history, project names, and synthesis state are all scoped per `channel_id`. OpenClaw also receives the project ID and name in every request to prevent context bleed.

### Tagged Ingestion
Every brain dump is stored with the author's `display_name` and `user_id`. When formatting for the agent, dumps are grouped by user so the Synthesizer can see who contributed what and the Critic can score inclusivity.

### Conversation History for Feedback Loop
The `TeamStore` maintains a list of conversation turns (`role: user/assistant`) per channel. On first `!synthesize`, the brain dumps are sent as the initial user message. On `!feedback`, the user's constraint is appended and the full history is replayed to OpenClaw.

### Project Isolation in OpenClaw
Each request to OpenClaw includes a `Project Context` section in the system prompt with the project ID and name. This tells the agent to treat each project as a completely separate session, preventing OpenClaw's memory layer from mixing contexts.

### Graceful Error Handling
The OpenClaw client catches `ClientConnectorError` (gateway down) and `TimeoutError` (gateway slow) and returns human-readable error messages instead of raw tracebacks.

### Message Splitting
Discord has a 2000-character limit. Long responses are split at newline boundaries to keep formatting clean.

### God Prompt Fallback
The system prompt in `openclaw_client.py` makes a single LLM call act as both Synthesizer and Critic. Person A can replace this with separate agent prompts.

## Running the Bot

```bash
conda activate idea-synth
cd discord-bot/
cp .env.example .env
# Fill in credentials
python bot.py
```

See `SETUP.md` for the full deployer guide including OpenClaw setup.

## Discord Bot Setup (Developer Portal)

1. Go to https://discord.com/developers/applications
2. Create new Application
3. **Bot** tab → Reset Token → copy it → paste into `.env`
4. Enable **Message Content Intent** under Privileged Gateway Intents
5. **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Permissions: `Send Messages`, `Read Message History`, `Embed Links`, `Manage Channels`, `Manage Roles`
6. Open generated URL → invite to server

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token from Discord Developer Portal |
| `OPENCLAW_URL` | No | `http://localhost:18789` | OpenClaw gateway URL |
| `OPENCLAW_TOKEN` | Yes | — | Bearer token for OpenClaw API |
| `OPENCLAW_AGENT_ID` | No | `synthesizer` | Which OpenClaw agent to route to |
| `PROJECT_CATEGORY` | No | `PROJECTS` | Discord category name for project channels |
