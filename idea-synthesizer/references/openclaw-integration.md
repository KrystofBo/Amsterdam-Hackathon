# OpenClaw Integration Reference

## What is OpenClaw?

OpenClaw (formerly Clawdbot/Moltbot) is an open-source, self-hosted AI personal assistant framework. It acts as a gateway connecting 12+ messaging platforms (Discord, Slack, Telegram, etc.) to AI agents. It's model-agnostic (Claude, OpenAI, DeepSeek, etc.) and supports multi-agent systems with isolated workspaces and memory.

- **GitHub:** openclaw/openclaw (MIT License, TypeScript)
- **Docs:** docs.openclaw.ai
- **Requirements:** Node 22.16+ (Node 24 recommended)

## Installation

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

The `--install-daemon` flag registers OpenClaw as a background service. Default install location: `~/.openclaw/`.

## Agent Configuration

Agents are created via CLI and configured in `openclaw.json`:

```bash
openclaw agents add synthesizer
```

Each agent has:
- **Workspace** (`~/.openclaw/workspace-<agentId>/`): files, persona rules
- **Agent Directory** (`~/.openclaw/agents/<agentId>/`): auth credentials, per-agent settings
- **Auth Profiles** (`~/.openclaw/agents/<agentId>/agent/auth-profiles.json`): API keys per agent

### Routing (openclaw.json)

Bindings route inbound messages to specific agents by channel/account:

```json5
{
  agents: {
    list: [
      { id: "synthesizer", workspace: "~/.openclaw/workspace-synthesizer" }
    ]
  },
  bindings: [
    {
      agentId: "synthesizer",
      match: { channel: "discord", accountId: "your-server-id" }
    }
  ]
}
```

## Gateway REST API

OpenClaw exposes an HTTP server on **localhost:18789** by default.

### OpenAI-Compatible Chat Endpoint

This is the primary integration point for our Discord bot:

```
POST /v1/chat/completions
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json
```

**Request body:**
```json
{
  "model": "openclaw:synthesizer",
  "messages": [
    {"role": "system", "content": "...system prompt..."},
    {"role": "user", "content": "...brain dumps..."}
  ],
  "stream": false
}
```

**Response:**
```json
{
  "choices": [
    {
      "message": {
        "content": "...synthesized pitch + evaluation matrix..."
      }
    }
  ]
}
```

### Other Endpoints

- `POST /tools/invoke` — Direct tool/script execution without LLM
- `POST /api/channels/*` — Channel-specific APIs
- Webhook endpoint: `http://localhost:18789/hooks`

## Memory System

OpenClaw uses local Markdown-based long-term memory + SQLite for session history:

- **Session memory:** Last 20-50 exchanges, injected as context each turn (stored in `~/.openclaw/openclaw.db`)
- **Long-term memory:** Structured Markdown files in the workspace the agent reads/writes
- **Pruning:** Trims old tool results in-memory per-request only; never modifies user/assistant messages on disk
- **Search:** Hybrid vector + BM25 keyword search for retrieval

This is why the feedback loop works — OpenClaw maintains conversational context across turns, so the Synthesizer can adjust an existing concept rather than starting from scratch.

## Discord-Native Integration (Alternative)

OpenClaw also has built-in Discord support (no custom bot needed):

```json5
{
  channels: {
    discord: {
      token: "YOUR_DISCORD_BOT_TOKEN",
      dmPolicy: "allow"
    }
  }
}
```

We chose a **custom bot** instead because we need:
- Multi-user message collection and tagging
- Explicit trigger commands (!dump, !synthesize, !feedback)
- Custom Evaluation Matrix formatting as Discord embeds
- Channel-scoped team brain dump storage

The native integration treats each message as a direct conversation turn, which doesn't fit our multi-user batch-and-synthesize workflow.

## Project Isolation

Each Discord channel is a separate project. To prevent OpenClaw's memory layer from mixing context between projects, every API request includes a project-scoped system prompt addition:

```
## Project Context
Project ID: 1234567890
Project Name: NASA Edu Game
This is an isolated project session. Only consider ideas and
feedback from this specific project. Do not reference or mix in
context from any other project.
```

The project ID is the Discord channel ID (unique per channel). The project name is set via `!project <name>` or defaults to `project-<channel_id>`.

User messages also include a `[Project: name]` prefix for additional clarity.

## Health Check

The `OpenClawClient.health_check()` method verifies connectivity:

1. **Gateway reachable** — GET request to the base URL (5s timeout)
2. **API responding** — Sends an authenticated `GET /v1/models` and confirms the target agent is listed

Returns a dict with `gateway_reachable`, `api_responding`, and `error` fields. Used by the `!health` Discord command.
