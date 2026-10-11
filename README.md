# mac-setup

macOS-style keyboard shortcuts and dock for **Fedora 44 / GNOME 50 (Wayland)** on a ThinkPad.

Key positions follow the Mac layout:

| PC key | Acts as Mac key |
|---|---|
| **Alt** (next to Space) | **Cmd** |
| **Super** (Windows key) | **Option** |

## Install

```bash
git clone <this-repo> ~/mac-setup
cd ~/mac-setup && ./install.sh
```

`install.sh` is safe to re-run. It asks for sudo only when system files need changing, and tells you if you must log out and back in.

**Live files are symlinks into this repo**, so edit them in place and commit:

| Live path | Repo file |
|---|---|
| `~/.config/xremap/config.yml` | `xremap/config.yml` |
| `~/.config/systemd/user/xremap.service` | `systemd/xremap.service` |

Saving `config.yml` restarts xremap automatically via `xremap-reload.path`, but **only if the new config is valid**. A typo keeps the previous config running, and `journalctl --user -u xremap-reload` shows `INVALID`.

> xremap's own `--watch=config` stops working after the first save by an editor that replaces the file (vim, `sed -i`, GNOME Text Editor), which is why the watcher exists.

## What's in here

| Path | Purpose |
|---|---|
| `xremap/config.yml` | The shortcuts. Terminal-specific overrides are in the `mac-terminal` keymap (it must stay first). |
| `systemd/xremap.service` | Runs xremap at login with GNOME window detection (`--desktop gnome`). |
| `systemd/xremap-reload.{path,service}` | Validates the config and restarts xremap whenever `config.yml` changes. |
| `system/` | udev rule and module config so xremap can use `/dev/uinput` without root. |
| `gnome/settings.dconf` | GNOME shortcuts, dock settings, Korean (ibus-hangul) input settings. |
| `gnome/macos-dock/*.patch` | Fixes for MacOS Dock v11 on GNOME 50: disposed-signal crash, window focus on Wayland, dock shortcut indexing. |
| `tests/` | Automated end-to-end tests (see below). |

Dependencies installed by `install.sh`:
- [xremap](https://github.com/xremap/xremap) `v0.15.14` (GNOME build)
- GNOME extension [Xremap](https://extensions.gnome.org/extension/5060/xremap/), which tells xremap which window is focused
- GNOME extension [MacOS Dock](https://extensions.gnome.org/extension/10719/macos-dock/) v11, with the patch applied

## Shortcuts

| Mac shortcut | Apps | Terminals |
|---|---|---|
| Cmd+← / Cmd+→ | Home / End | same |
| Cmd+Backspace | Delete to line start | Ctrl+U |
| Option+← / Option+→ | Word left / right | same |
| Option+Backspace | Delete previous word | Alt+Backspace |
| Cmd+T / Cmd+Shift+T | New tab / reopen closed tab | New tab (Ctrl+Shift+T) |
| Cmd+W | Close tab | Close tab (Ctrl+Shift+W) |
| Cmd+C / V / X / A | Copy / paste / cut / select all | (not yet terminal-adjusted) |
| Cmd+Space or Ctrl+Space | Switch input language | same |
| Cmd+Q | Quit (Alt+F4) | same |
| Cmd+H | Hide (minimize) | same |
| Ctrl+Cmd+Q | Lock screen | same |
| Cmd+Shift+3 / 4 / 5 | Screenshot | same |
| Cmd+[ / Cmd+] | Back / forward | same |
| Cmd+Shift+[ / ] | Previous / next tab | same |
| Cmd+= / - / 0 | Zoom in / out / reset | same |
| Cmd+L | Address bar | same |

See `xremap/config.yml` for the exact mappings.

## Tests

The tests create a virtual keyboard, send real key presses through the running xremap service into self-closing test windows, and check the result. Keys are only sent once the test window has focus, so nothing goes into your other apps.

```bash
python3 tests/xremap_selftest.py                    # GTK text fields
python3 tests/term_selftest.py org.gnome.Ptyxis bksp  # terminal (same widget as Ptyxis); modes: bksp, left, superbksp, t, w
python3 tests/brave_selftest.py t                   # isolated throwaway Brave profile; modes: t, w
```

They need your user in the `input` group (done by `install.sh`).

## Troubleshooting

```bash
systemctl --user status xremap.service               # should be active (running)
journalctl --user -u xremap.service -f               # live log; shows "application: <wm_class>" on focus change
~/.local/bin/xremap --validate-config xremap/config.yml
gdbus call --session --dest org.gnome.Shell --object-path /com/k0kubun/Xremap \
  --method com.k0kubun.Xremap.ActiveWindow          # what xremap sees as the focused app
```
