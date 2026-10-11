#!/usr/bin/env python3
"""Terminal self-test: VTE (same widget as Ptyxis) running bash `read -e`.
Keys are injected through a virtual keyboard -> xremap service -> focused test window.
Usage: term_selftest.py [app_id]
"""
import os, sys, time, threading, json, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from xremap_selftest import VKbd, Recorder, find_xremap_output, K

import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Vte", "3.91")
from gi.repository import Gtk, GLib, Vte, Gio

APP_ID = sys.argv[1] if len(sys.argv) > 1 else "dev.selftest.Term"
MODE = sys.argv[2] if len(sys.argv) > 2 else "bksp"
OUT = tempfile.mktemp(prefix="xremap_term_")
READY = OUT + ".ready"
res = {"app_id": APP_ID}


def tests(win, kbd, rec):
    t0 = time.time()
    while time.time() - t0 < 8 and not (win.is_active() and os.path.exists(READY)):
        time.sleep(0.1)
    if not (win.is_active() and os.path.exists(READY)):
        res["error"] = "terminal window not active/ready; aborted without injecting"
        GLib.idle_add(win.close); return
    time.sleep(0.5)
    rec.take()
    if MODE == "w":
        kbd.combo([K["ALT"]], 17)
    elif MODE == "superbksp":
        kbd.combo([K["META"]], K["BKSP"])
    elif MODE == "t":
        kbd.combo([K["ALT"]], 20)
    elif MODE == "left":
        kbd.combo([K["ALT"]], K["LEFT"]); kbd.combo([], K["A"])
    else:
        kbd.combo([K["ALT"]], K["BKSP"])
    time.sleep(0.4)
    res["xremap_emitted"] = rec.take()
    import subprocess
    res["overview_opened"] = "true" in subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "overview_check.sh")], capture_output=True, text=True).stdout
    res["window_still_focused"] = win.is_active()
    kbd.combo([], 28)  # Enter
    for _ in range(30):
        if os.path.exists(OUT): break
        time.sleep(0.1)
    res["before"] = "hello world"
    res["after"] = open(OUT).read() if os.path.exists(OUT) else None
    GLib.idle_add(win.close)


def main():
    out = find_xremap_output()
    kbd = VKbd(); time.sleep(1.5)
    rec = Recorder(out); rec.start()
    app = Gtk.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activate(a):
        win = Gtk.ApplicationWindow(application=a, title="xremap terminal self-test")
        win.set_default_size(600, 200)
        term = Vte.Terminal(); win.set_child(term); win.present(); term.grab_focus()
        script = f'touch {READY}; read -e -i "hello world" x; printf "%s" "$x" > {OUT}'
        term.spawn_async(Vte.PtyFlags.DEFAULT, os.environ["HOME"], ["/bin/bash", "-c", script],
                         None, GLib.SpawnFlags.DEFAULT, None, None, -1, None, None, None)
        threading.Thread(target=tests, args=(win, kbd, rec), daemon=True).start()

    app.connect("activate", activate); app.run([])
    rec.stop = True; kbd.close()
    for f in (OUT, READY):
        if os.path.exists(f): os.remove(f)
    print(json.dumps(res, ensure_ascii=False, indent=2))


main()
