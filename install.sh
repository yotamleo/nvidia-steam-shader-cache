#!/usr/bin/env bash
# Link the script into ~/.local/bin, install + enable the user unit.
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
ln -sfn "$repo/bin/ow-shader-sync" "$HOME/.local/bin/ow-shader-sync"
ln -sfn "$repo/systemd/ow-shader-sync.service" "$HOME/.config/systemd/user/ow-shader-sync.service"
systemctl --user daemon-reload
systemctl --user enable --now ow-shader-sync.service
systemctl --user is-active ow-shader-sync.service
