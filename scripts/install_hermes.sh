#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) -ne 0 ]]; then
    echo "Dieses Skript muss mit Root-Rechten ausgeführt werden." >&2
    exit 1
fi

TARGET_USER=${TARGET_USER:-${SUDO_USER:-pi}}
if ! id "$TARGET_USER" >/dev/null 2>&1; then
    echo "Der Zielnutzer '$TARGET_USER' existiert nicht." >&2
    exit 1
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
APP_DIR=/opt/hermes
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

APT_PACKAGES=(python3 python3-venv python3-pip python3-tk rsync)

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y "${APT_PACKAGES[@]}"

mkdir -p "$APP_DIR"
rsync -a --delete --exclude ".git" --exclude "__pycache__" "$REPO_DIR"/ "$APP_DIR"/
chown -R "$TARGET_USER":"$TARGET_USER" "$APP_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
if [[ -f "$APP_DIR/requirements.txt" ]]; then
    "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

cat <<'LAUNCH' > "$APP_DIR/run.sh"
#!/usr/bin/env bash
set -e
source "$(dirname "$0")/.venv/bin/activate"
exec python "$(dirname "$0")/main.py"
LAUNCH
chmod +x "$APP_DIR/run.sh"
chown "$TARGET_USER":"$TARGET_USER" "$APP_DIR/run.sh"

SERVICE_DIR="$TARGET_HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
chown -R "$TARGET_USER":"$TARGET_USER" "$TARGET_HOME/.config"

cat <<SERVICE > "$SERVICE_DIR/hermes-app.service"
[Unit]
Description=Hermes Paketmanager Desktop Anwendung
After=graphical-session.target

[Service]
Type=simple
Environment=DISPLAY=:0
Environment=XAUTHORITY=%h/.Xauthority
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/run.sh
Restart=always

[Install]
WantedBy=graphical-session.target
SERVICE
chown "$TARGET_USER":"$TARGET_USER" "$SERVICE_DIR/hermes-app.service"

loginctl enable-linger "$TARGET_USER"

RUNTIME_DIR="/run/user/$(id -u "$TARGET_USER")"
if [[ ! -d "$RUNTIME_DIR" ]]; then
    install -d -m 700 -o "$TARGET_USER" -g "$TARGET_USER" "$RUNTIME_DIR"
fi

sudo -u "$TARGET_USER" XDG_RUNTIME_DIR="$RUNTIME_DIR" systemctl --user daemon-reload
sudo -u "$TARGET_USER" XDG_RUNTIME_DIR="$RUNTIME_DIR" systemctl --user enable --now hermes-app.service

echo "Installation abgeschlossen. Die Anwendung startet nach der nächsten Anmeldung automatisch im Vollbild." 
