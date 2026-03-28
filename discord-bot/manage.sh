#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR"
ENV_FILE="$BOT_DIR/.env"

load_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    return
  fi

  while IFS='=' read -r key value; do
    [[ -z "${key// }" ]] && continue
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ -n "${!key:-}" ]] && continue
    export "$key=$value"
  done < "$ENV_FILE"
}

load_env_file

CONDA_ENV="${CONDA_ENV:-idea-synth}"
OPENCLAW_PORT="${OPENCLAW_PORT:-18789}"
OPENCLAW_AGENT_ID="${OPENCLAW_AGENT_ID:-synthesizer}"
OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace-synthesizer}"
OPENCLAW_CHAT_MODEL="${OPENCLAW_CHAT_MODEL:-openclaw:$OPENCLAW_AGENT_ID}"
OPENCLAW_AGENT_MODEL_ALIAS="${OPENCLAW_AGENT_MODEL_ALIAS:-$OPENCLAW_AGENT_ID-default}"
OPENCLAW_AGENT_MODEL="${OPENCLAW_AGENT_MODEL:-}"
OPENCLAW_OPENAI_PROFILE_ID="${OPENCLAW_OPENAI_PROFILE_ID:-openai:manual}"
USE_OPENAI_API="${USE_OPENAI_API:-false}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
OPENAI_MODEL="${OPENAI_MODEL:-gpt-4.1-mini}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  setup-openclaw     Configure OpenClaw for this bot and create the agent
  configure-openai-auth
                     Store an OpenAI API key for the agent from .env or prompt
  apply-model-config [model]
                     Point the agent alias at a model and make the agent use it
  show-model         Show the agent's currently configured model
  run-openclaw       Run OpenClaw gateway on loopback
  run-openclaw-lan   Run OpenClaw gateway with --bind lan (useful on WSL)
  stop-openclaw      Stop the OpenClaw gateway if supervised
  show-token         Print the OpenClaw gateway auth token
  install-bot-deps   Create/update the conda env and install Python deps
  run-bot            Run the Discord bot with conda
  run-all            Install deps, verify .env, then run the bot
                     (expects OpenClaw to already be running)
  help               Show this help text

Examples:
  ./manage.sh setup-openclaw
  ./manage.sh configure-openai-auth
  ./manage.sh apply-model-config openai/gpt-4.1-mini
  ./manage.sh show-model
  ./manage.sh run-openclaw-lan
  ./manage.sh show-token
  ./manage.sh install-bot-deps
  ./manage.sh run-bot
  ./manage.sh run-all
EOF
}

is_truthy() {
  local value="${1:-}"
  value="${value,,}"
  [[ "$value" == "1" || "$value" == "true" || "$value" == "yes" || "$value" == "on" ]]
}

validate_openai_env() {
  if ! is_truthy "$USE_OPENAI_API"; then
    return
  fi

  if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "USE_OPENAI_API is true but OPENAI_API_KEY is empty in $ENV_FILE" >&2
    exit 1
  fi

  if [[ -z "$OPENAI_MODEL" ]]; then
    echo "USE_OPENAI_API is true but OPENAI_MODEL is empty in $ENV_FILE" >&2
    exit 1
  fi
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE" >&2
    echo "Create it from .env.example first." >&2
    exit 1
  fi
}

has_agent() {
  openclaw agents list --json | grep -q "\"id\": \"$OPENCLAW_AGENT_ID\""
}

require_agent() {
  if ! has_agent; then
    echo "OpenClaw agent '$OPENCLAW_AGENT_ID' does not exist yet." >&2
    echo "Run ./manage.sh setup-openclaw first." >&2
    exit 1
  fi
}

resolve_target_model() {
  local cli_model="${1:-}"
  if [[ -n "$cli_model" ]]; then
    printf '%s\n' "$cli_model"
    return
  fi

  if is_truthy "$USE_OPENAI_API"; then
    if [[ -n "$OPENAI_MODEL" ]]; then
      printf 'openai/%s\n' "$OPENAI_MODEL"
      return
    fi
  fi

  if [[ -n "$OPENCLAW_AGENT_MODEL" ]]; then
    printf '%s\n' "$OPENCLAW_AGENT_MODEL"
    return
  fi

  echo "Missing model id." >&2
  echo "Set OPENAI_MODEL / OPENCLAW_AGENT_MODEL in $ENV_FILE or pass a model id." >&2
  exit 1
}

resolve_agent_dir() {
  openclaw models auth order get \
    --agent "$OPENCLAW_AGENT_ID" \
    --provider openai \
    --json | node -e '
let data = "";
process.stdin.on("data", (chunk) => data += chunk);
process.stdin.on("end", () => {
  const parsed = JSON.parse(data);
  process.stdout.write(String(parsed.agentDir || ""));
});
'
}

sync_openai_auth_from_env() {
  ensure_env_file
  need_cmd openclaw
  need_cmd node
  require_agent

  if [[ -z "$OPENAI_API_KEY" ]]; then
    echo "OPENAI_API_KEY is not set in $ENV_FILE" >&2
    return 1
  fi

  local agent_dir
  agent_dir="$(resolve_agent_dir)"
  if [[ -z "$agent_dir" ]]; then
    echo "Could not resolve OpenClaw agent dir for '$OPENCLAW_AGENT_ID'." >&2
    return 1
  fi

  OPENCLAW_AGENT_DIR="$agent_dir" \
  OPENCLAW_PROFILE_ID="$OPENCLAW_OPENAI_PROFILE_ID" \
  OPENCLAW_API_TOKEN="$OPENAI_API_KEY" \
  node <<'EOF'
const fs = require("fs");
const path = require("path");

const agentDir = process.env.OPENCLAW_AGENT_DIR;
const profileId = process.env.OPENCLAW_PROFILE_ID;
const token = process.env.OPENCLAW_API_TOKEN;

if (!agentDir || !profileId || !token) {
  throw new Error("Missing OPENCLAW_AGENT_DIR, OPENCLAW_PROFILE_ID, or OPENCLAW_API_TOKEN.");
}

const authPath = path.join(agentDir, "auth-profiles.json");
let store = { version: 1, profiles: {} };

if (fs.existsSync(authPath)) {
  store = JSON.parse(fs.readFileSync(authPath, "utf8"));
}

if (!store || typeof store !== "object") {
  store = { version: 1, profiles: {} };
}

if (!store.version) {
  store.version = 1;
}

if (!store.profiles || typeof store.profiles !== "object") {
  store.profiles = {};
}

store.profiles[profileId] = {
  type: "token",
  provider: "openai",
  token,
};

fs.mkdirSync(agentDir, { recursive: true });
const tmpPath = `${authPath}.tmp-${process.pid}`;
fs.writeFileSync(tmpPath, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });
fs.renameSync(tmpPath, authPath);
fs.chmodSync(authPath, 0o600);
EOF

  openclaw models auth order set \
    --agent "$OPENCLAW_AGENT_ID" \
    --provider openai \
    "$OPENCLAW_OPENAI_PROFILE_ID"

  echo "Synced OPENAI_API_KEY from .env into agent '$OPENCLAW_AGENT_ID' profile '$OPENCLAW_OPENAI_PROFILE_ID'."
}

prepare_openclaw_from_env() {
  validate_openai_env

  if is_truthy "$USE_OPENAI_API" && [[ -n "$OPENAI_API_KEY" ]]; then
    sync_openai_auth_from_env
  fi

  if is_truthy "$USE_OPENAI_API"; then
    apply_model_config
  elif [[ -n "$OPENCLAW_AGENT_MODEL" ]]; then
    apply_model_config
  fi
}

setup_openclaw() {
  need_cmd openclaw

  openclaw config set gateway.controlUi.enabled false --strict-json
  openclaw config set gateway.http.endpoints.chatCompletions.enabled true --strict-json

  if has_agent; then
    echo "OpenClaw agent '$OPENCLAW_AGENT_ID' already exists."
  else
    openclaw agents add "$OPENCLAW_AGENT_ID" \
      --workspace "$OPENCLAW_WORKSPACE" \
      --non-interactive \
      --json
  fi
}

configure_openai_auth() {
  if [[ -n "$OPENAI_API_KEY" ]]; then
    sync_openai_auth_from_env
    return
  fi

  need_cmd openclaw
  require_agent

  openclaw models auth paste-token \
    --provider openai \
    --profile-id "$OPENCLAW_OPENAI_PROFILE_ID"

  openclaw models auth order set \
    --agent "$OPENCLAW_AGENT_ID" \
    --provider openai \
    "$OPENCLAW_OPENAI_PROFILE_ID"
}

apply_model_config() {
  need_cmd openclaw
  require_agent

  local target_model
  target_model="$(resolve_target_model "${1:-}")"

  openclaw models aliases add "$OPENCLAW_AGENT_MODEL_ALIAS" "$target_model"
  openclaw models --agent "$OPENCLAW_AGENT_ID" set "$OPENCLAW_AGENT_MODEL_ALIAS"

  echo "Agent '$OPENCLAW_AGENT_ID' now uses alias '$OPENCLAW_AGENT_MODEL_ALIAS' -> '$target_model'"
  show_model
}

show_model() {
  need_cmd openclaw
  require_agent

  echo "Chat target: $OPENCLAW_CHAT_MODEL"
  echo "USE_OPENAI_API: $USE_OPENAI_API"
  echo "Model alias: $OPENCLAW_AGENT_MODEL_ALIAS"
  if is_truthy "$USE_OPENAI_API"; then
    echo "Desired OpenAI model from .env: openai/$OPENAI_MODEL"
  fi
  if [[ -n "$OPENCLAW_AGENT_MODEL" ]]; then
    echo "Desired model from .env: $OPENCLAW_AGENT_MODEL"
  fi
  echo "Current agent model:"
  openclaw models --agent "$OPENCLAW_AGENT_ID" status --plain
}

run_openclaw() {
  need_cmd openclaw
  prepare_openclaw_from_env
  openclaw gateway run --port "$OPENCLAW_PORT" --verbose
}

run_openclaw_lan() {
  need_cmd openclaw
  prepare_openclaw_from_env
  openclaw gateway run --bind lan --port "$OPENCLAW_PORT" --verbose
}

stop_openclaw() {
  need_cmd openclaw
  openclaw gateway stop
}

show_token() {
  need_cmd openclaw
  openclaw config get gateway.auth.token
}

ensure_conda_env() {
  need_cmd conda

  if conda run -n "$CONDA_ENV" python --version >/dev/null 2>&1; then
    echo "Conda env '$CONDA_ENV' already exists."
  else
    conda create -n "$CONDA_ENV" python=3.11 -y
  fi
}

install_bot_deps() {
  ensure_conda_env
  conda run -n "$CONDA_ENV" pip install -r "$BOT_DIR/requirements.txt"
}

run_bot() {
  ensure_env_file
  ensure_conda_env
  prepare_openclaw_from_env
  cd "$BOT_DIR"
  conda run -n "$CONDA_ENV" python bot.py
}

run_all() {
  install_bot_deps
  run_bot
}

COMMAND="${1:-help}"

case "$COMMAND" in
  setup-openclaw)
    setup_openclaw
    ;;
  configure-openai-auth)
    configure_openai_auth
    ;;
  apply-model-config)
    apply_model_config "${2:-}"
    ;;
  show-model)
    show_model
    ;;
  run-openclaw)
    run_openclaw
    ;;
  run-openclaw-lan)
    run_openclaw_lan
    ;;
  stop-openclaw)
    stop_openclaw
    ;;
  show-token)
    show_token
    ;;
  install-bot-deps)
    install_bot_deps
    ;;
  run-bot)
    run_bot
    ;;
  run-all)
    run_all
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    echo >&2
    usage >&2
    exit 1
    ;;
esac
