#!/usr/bin/env bash
# Jira Indicator installer. Needs nothing beyond a standard Ubuntu GNOME desktop.
#
# Straight from GitHub (use whichever of the two your machine has):
#   wget -qO- https://raw.githubusercontent.com/jasocami/jcm-gnome-jira-indicator/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/jasocami/jcm-gnome-jira-indicator/main/install.sh | bash
# From a downloaded copy of the source:
#   ./install.sh        (or: make install)
#
# Set REF to install another branch or a release tag, e.g.  ... | REF=v1.0.0 bash
set -euo pipefail

NAME=jcm-gnome-jira-indicator
REPO=jasocami/$NAME
REF=${REF:-main}
FILES=(metadata.json extension.js fetch.py config.example.ini MANUAL.md)
CONFIG_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/$NAME

say() { printf '%s\n' "$*"; }
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

command -v gnome-extensions >/dev/null || fail "gnome-extensions not found: this needs a GNOME desktop"
command -v python3 >/dev/null || fail "python3 not found"

# Run from a copy of the source: use the files next to this script.
# Piped from the web: download the source into a temporary folder first.
script=${BASH_SOURCE[0]:-}
if [[ -n "$script" && -f "$(dirname "$script")/metadata.json" ]]; then
    SRC=$(cd "$(dirname "$script")" && pwd)
else
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    url="https://github.com/$REPO/archive/$REF.tar.gz"
    say "Downloading $url"
    if command -v curl >/dev/null; then
        curl -fsSL "$url" | tar -xz -C "$TMP"
    elif command -v wget >/dev/null; then
        wget -qO- "$url" | tar -xz -C "$TMP"
    else
        fail "need curl or wget to download the source"
    fi
    SRC=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n 1)
fi

UUID=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["uuid"])' "$SRC/metadata.json")
VERSION=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version-name"])' "$SRC/metadata.json")
EXT_DIR=${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID

# The extension itself: a fresh copy every time, so an update never mixes old and new files.
rm -rf "$EXT_DIR"
mkdir -p "$EXT_DIR"
for file in "${FILES[@]}"; do
    cp -r "$SRC/$file" "$EXT_DIR/"
done
say "Installed Jira Indicator $VERSION to $EXT_DIR"

# Your settings: created once from the example, never overwritten, readable only by you (it holds your token).
mkdir -p "$CONFIG_DIR"
if [[ -f "$CONFIG_DIR/config.ini" ]]; then
    say "Kept your settings: $CONFIG_DIR/config.ini"
else
    cp "$SRC/config.example.ini" "$CONFIG_DIR/config.ini"
    chmod 600 "$CONFIG_DIR/config.ini"
    say "Created your settings: $CONFIG_DIR/config.ini"
fi

# Turn it on. On a first install GNOME only finds the extension after a new login, so when the
# enable command fails, add it to GNOME's list of enabled extensions directly; it starts at the next login.
if ! gnome-extensions enable "$UUID" 2>/dev/null; then
    python3 - "$UUID" <<'EOF'
import ast, subprocess, sys
uuid = sys.argv[1]
current = subprocess.run(['gsettings', 'get', 'org.gnome.shell', 'enabled-extensions'],
                         capture_output=True, text=True, check=True).stdout.strip()
enabled = [] if current.startswith('@as') else ast.literal_eval(current)
if uuid not in enabled:
    enabled.append(uuid)
    subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', str(enabled)], check=True)
EOF
fi

say ""
say "Next:"
say "  1. Open $CONFIG_DIR/config.ini and fill in domain, email and token."
say "     Create the token at https://id.atlassian.com/manage-profile/security/api-tokens"
say "  2. Log out and log back in (first install only). Jira Indicator appears in the top bar."
