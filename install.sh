#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INSTALL_BIN=true
SERVICE_MODE=""
INSTALL_GREET=false
INSTALL_UDEV=false
INSTALL_AGY_HOOKS=false

usage() {
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Install ThinkDot (thinkdot.py & light_control.py) and optional system integrations.

Options:
  --service <alert|clock>  Install and enable the systemd daemon service (alert or clock)
  --greet                  Install and enable the boot Morse greeting service
  --udev                   Install udev rule to allow non-root LED control
  --agy-hooks              Install Antigravity CLI hooks into ~/.gemini/config/hooks.json
  --all                    Install binary, alert daemon, boot greeting, udev rule, and AGY hooks
  -h, --help               Show this help message

If no options are passed, installs thinkdot.py and light_control.py to /usr/local/bin.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE_MODE="${2:-}"
      if [[ "$SERVICE_MODE" != "alert" && "$SERVICE_MODE" != "clock" ]]; then
        echo "Error: --service requires 'alert' or 'clock'" >&2
        exit 1
      fi
      shift 2
      ;;
    --greet)
      INSTALL_GREET=true
      shift
      ;;
    --udev)
      INSTALL_UDEV=true
      shift
      ;;
    --agy-hooks)
      INSTALL_AGY_HOOKS=true
      shift
      ;;
    --all)
      SERVICE_MODE="alert"
      INSTALL_GREET=true
      INSTALL_UDEV=true
      INSTALL_AGY_HOOKS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$INSTALL_BIN" == true ]]; then
  echo "==> Installing scripts to /usr/local/bin..."
  sudo install -m 0755 "$SCRIPT_DIR/thinkdot.py" /usr/local/bin/thinkdot.py
  sudo install -m 0755 "$SCRIPT_DIR/light_control.py" /usr/local/bin/light_control.py
  echo "    Installed /usr/local/bin/thinkdot.py and /usr/local/bin/light_control.py"
fi

if [[ "$INSTALL_UDEV" == true ]]; then
  echo "==> Installing udev rule to /etc/udev/rules.d/99-thinkdot.rules..."
  sudo install -m 0644 "$SCRIPT_DIR/udev/99-thinkdot.rules" /etc/udev/rules.d/99-thinkdot.rules
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=leds || true
  echo "    Udev rules reloaded."
fi

if [[ -n "$SERVICE_MODE" ]]; then
  UNIT_FILE="thinkdot-${SERVICE_MODE}.service"
  echo "==> Installing and enabling systemd service: $UNIT_FILE..."
  sudo install -m 0644 "$SCRIPT_DIR/systemd/$UNIT_FILE" "/etc/systemd/system/$UNIT_FILE"
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$UNIT_FILE"
  echo "    Service $UNIT_FILE is now active."
fi

if [[ "$INSTALL_GREET" == true ]]; then
  echo "==> Installing and enabling boot greeting service: thinkdot-greet.service..."
  sudo install -m 0644 "$SCRIPT_DIR/systemd/thinkdot-greet.service" /etc/systemd/system/thinkdot-greet.service
  sudo systemctl daemon-reload
  sudo systemctl enable thinkdot-greet.service
  echo "    Service thinkdot-greet.service enabled for boot."
fi

if [[ "$INSTALL_AGY_HOOKS" == true ]]; then
  HOOKS_DIR="${HOME}/.gemini/config"
  HOOKS_FILE="${HOOKS_DIR}/hooks.json"
  mkdir -p "$HOOKS_DIR"
  if [[ -f "$HOOKS_FILE" ]]; then
    BACKUP="${HOOKS_FILE}.bak.$(date +%s)"
    cp "$HOOKS_FILE" "$BACKUP"
    echo "    Backed up existing hooks.json to $BACKUP"
  fi
  cp "$SCRIPT_DIR/examples/agy-hooks.json" "$HOOKS_FILE"
  echo "==> Installed Antigravity CLI hooks to $HOOKS_FILE"
fi

echo "==> Done! Run 'thinkdot.py status' or 'thinkdot.py --help' to get started."
