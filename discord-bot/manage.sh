#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR"
ENV_FILE="$BOT_DIR/.env"
CONDA_ENV="${CONDA_ENV:-idea-synth}"
OPENCLAW_PORT="${OPENCLAW_PORT:-18789}"
OPENCLAW_AGENT_ID="${OPENCLAW_AGENT_ID:-synthesizer}"
OPENCLAW_WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace-synthesizer}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  setup-openclaw     Configure OpenClaw for this bot and create the agent
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
  ./manage.sh run-openclaw-lan
  ./manage.sh show-token
  ./manage.sh install-bot-deps
  ./manage.sh run-bot
  ./manage.sh run-all
EOF
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

run_openclaw() {
  need_cmd openclaw
  openclaw gateway run --port "$OPENCLAW_PORT" --verbose
}

run_openclaw_lan() {
  need_cmd openclaw
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
