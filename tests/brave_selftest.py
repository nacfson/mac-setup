#!/usr/bin/env python3
"""Brave self-test for Alt+T (Cmd+T -> new tab) via xremap.

Launches an isolated Brave (temporary profile, own process, remote debugging),
waits until the xremap GNOME extension reports THAT window as focused, injects
Alt+T through a virtual keyboard, and counts tabs via the DevTools HTTP API.
Never injects unless the focused window is the test window.
"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from xremap_selftest import VKbd, Recorder, find_xremap_output, K

PORT = 9333
MARK = "XREMAP-SELFTEST-BRAVE"
K_T = 20
KEYS = {"t": (20, +1), "w": (17, -1)}
MODE = sys.argv[1] if len(sys.argv) > 1 else "t"
KEYCODE, DELTA = KEYS[MODE]


def active_window():
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
                          "--object-path", "/com/k0kubun/Xremap",
                          "--method", "com.k0kubun.Xremap.ActiveWindow"],
                         capture_output=True, text=True).stdout.strip()
    try:
        return json.loads(out[2:-3].encode().decode("unicode_escape"))
    except Exception:
        return {"raw": out}


def tabs():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
            return [p for p in json.load(r) if p.get("type") == "page"]
    except Exception:
        return None


def main():
    res = {}
    prof = tempfile.mkdtemp(prefix="brave-xremap-test-")
    url = f"data:text/html,<title>{MARK}</title><h1>{MARK}</h1>"
    proc = subprocess.Popen(["/opt/brave.com/brave/brave", f"--user-data-dir={prof}",
                             f"--remote-debugging-port={PORT}", "--no-first-run",
                             "--no-default-browser-check", "--ozone-platform=wayland",
                             "--new-window", url] + ([url + "<p>2"] if MODE == "w" else []),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = find_xremap_output()
    kbd = VKbd(); time.sleep(1.5)
    rec = Recorder(out); rec.start()
    try:
        win = {}
        for _ in range(100):
            win = active_window()
            if MARK in win.get("title", "") and tabs() is not None:
                break
            time.sleep(0.2)
        res["focused_window"] = win
        if MARK not in win.get("title", ""):
            res["error"] = "test Brave window never got focus; aborted without injecting"
            return res
        time.sleep(0.8)
        before = len(tabs())
        rec.take()
        kbd.combo([K["ALT"]], KEYCODE)
        time.sleep(1.5)
        after = len(tabs())
        res.update({"tabs_before": before, "tabs_after": after,
                    "key": "Alt+" + MODE.upper(), "xremap_emitted": rec.take().replace(str(KEYCODE), MODE.upper()),
                    "pass": after == before + DELTA})
        return res
    finally:
        rec.stop = True
        kbd.close()
        proc.terminate()
        try:
            proc.wait(5)
        except Exception:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)


print(json.dumps(main(), ensure_ascii=False, indent=2))
