#!/usr/bin/env bash
# mac-setup installer — macOS-style keyboard shortcuts + dock on Fedora GNOME (Wayland).
# Idempotent: safe to re-run. Live config files become symlinks into this repo,
# so edits are tracked by git automatically.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XREMAP_VERSION="v0.15.14"
XREMAP_EXT_UUID="xremap@k0kubun.com"
XREMAP_EXT_TAG="69781"          # extensions.gnome.org build for GNOME 50
DOCK_UUID="macos-dock@vinnytherobot.github.io"
DOCK_TAG="75984"                # MacOS Dock v11 (patch targets this exact version)

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

link() {  # link <repo-file> <target>
  local src="$REPO/$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ] && [ "$(readlink -f "$dst")" = "$(readlink -f "$src")" ]; then
    echo "  ok      $dst"; return
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mv "$dst" "$dst.bak.$(date +%s)"; echo "  backup  $dst"
  fi
  ln -s "$src" "$dst"; echo "  linked  $dst -> $src"
}

install_ego_extension() {  # install_ego_extension <uuid> <version_tag>
  local uuid="$1" tag="$2" tmp
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/ext.zip" \
    "https://extensions.gnome.org/download-extension/${uuid}.shell-extension.zip?version_tag=${tag}"
  gnome-extensions install --force "$tmp/ext.zip"
  rm -rf "$tmp"
}

say "1/6 xremap binary ($XREMAP_VERSION, GNOME variant)"
if [ -x "$HOME/.local/bin/xremap" ]; then
  echo "  ok      $("$HOME/.local/bin/xremap" --version)"
else
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/x.zip" \
    "https://github.com/xremap/xremap/releases/download/${XREMAP_VERSION}/xremap-linux-$(uname -m)-gnome.zip"
  unzip -q "$tmp/x.zip" -d "$tmp"
  install -Dm755 "$tmp/xremap" "$HOME/.local/bin/xremap"
  rm -rf "$tmp"; echo "  installed ~/.local/bin/xremap"
fi

say "2/6 Config files (symlinked into this repo)"
link xremap/config.yml       "$HOME/.config/xremap/config.yml"
link systemd/xremap.service  "$HOME/.config/systemd/user/xremap.service"
link systemd/xremap-reload.path    "$HOME/.config/systemd/user/xremap-reload.path"
link systemd/xremap-reload.service "$HOME/.config/systemd/user/xremap-reload.service"

say "3/6 Device permissions for xremap (needs sudo)"
need_relogin=0
if ! cmp -s "$REPO/system/99-xremap-uinput.rules" /etc/udev/rules.d/99-xremap-uinput.rules 2>/dev/null; then
  sudo install -m644 "$REPO/system/99-xremap-uinput.rules" /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
fi
if ! cmp -s "$REPO/system/uinput.conf" /etc/modules-load.d/uinput.conf 2>/dev/null; then
  sudo install -m644 "$REPO/system/uinput.conf" /etc/modules-load.d/
  sudo modprobe uinput
fi
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  sudo usermod -aG input "$USER"; need_relogin=1
fi
echo "  ok"

say "4/6 GNOME extensions"
install_ego_extension "$XREMAP_EXT_UUID" "$XREMAP_EXT_TAG"
echo "  installed $XREMAP_EXT_UUID"
DOCK_DIR="$HOME/.local/share/gnome-shell/extensions/$DOCK_UUID"
if [ -f "$DOCK_DIR/lib/signalManager.js" ] && grep -q "Ignore if already disposed" "$DOCK_DIR/lib/signalManager.js"; then
  echo "  ok      $DOCK_UUID (already patched)"
else
  install_ego_extension "$DOCK_UUID" "$DOCK_TAG"
  patch -d "$DOCK_DIR" -p1 < "$REPO/gnome/macos-dock/macos-dock-v11-fixes.patch"
  echo "  installed + patched $DOCK_UUID"
fi
mkdir -p "$HOME/.local/share/glib-2.0/schemas"
cp -f "$DOCK_DIR"/schemas/*.gschema.xml "$HOME/.local/share/glib-2.0/schemas/"
glib-compile-schemas "$HOME/.local/share/glib-2.0/schemas/"
for uuid in "$XREMAP_EXT_UUID" "$DOCK_UUID"; do
  if ! gnome-extensions enable "$uuid" 2>/dev/null; then
    # Shell hasn't scanned it yet (fresh install): queue it for the next login.
    python3 - "$uuid" <<'PY'
import ast, subprocess, sys
cur = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                     capture_output=True, text=True).stdout.strip().removeprefix("@as ")
exts = ast.literal_eval(cur)
if sys.argv[1] not in exts:
    exts.append(sys.argv[1])
    subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions", str(exts)], check=True)
PY
    warn "$uuid will be active after you log out/in"; need_relogin=1
  fi
done

say "5/6 GNOME settings (shortcuts, dock, Korean input)"
dconf load / < "$REPO/gnome/settings.dconf"
echo "  loaded gnome/settings.dconf"

say "6/6 xremap service"
systemctl --user daemon-reload
systemctl --user enable xremap.service >/dev/null
systemctl --user enable --now xremap-reload.path >/dev/null
if [ "$need_relogin" = 0 ]; then
  systemctl --user restart xremap.service
  sleep 1; systemctl --user is-active xremap.service
fi

say "Done"
[ "$need_relogin" = 1 ] && warn "Log out and back in to finish (input group / extensions)."
echo "Verify with:  python3 $REPO/tests/xremap_selftest.py"
