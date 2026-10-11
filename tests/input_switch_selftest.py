#!/usr/bin/env python3
"""Input-language switch self-test: Ctrl+Space and Alt+Space (Cmd+Space via xremap).

Injects each combo into a focused GTK test window and checks that the active
input source flips (and flips back on a second press, restoring your state).
"""
import json, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xremap_selftest import VKbd, Recorder, find_xremap_output, K

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio

COMBOS = [("Ctrl+Space", [K["CTRL"]]), ("Alt+Space (Cmd+Space)", [K["ALT"]]), ("Super+Space", [K["META"]])]
res = {}


def source():
    return subprocess.run(["ibus", "engine"], capture_output=True, text=True).stdout.strip()


def tests(win, kbd, rec):
    t0 = time.time()
    while time.time() - t0 < 6 and not win.is_active():
        time.sleep(0.1)
    if not win.is_active():
        res["error"] = "test window never focused; aborted"; GLib.idle_add(win.close); return
    time.sleep(0.5)
    for name, mods in COMBOS:
        start = source()
        rec.take(); kbd.combo(mods, K["SPACE"]); time.sleep(0.8)
        mid = source(); emitted = rec.take()
        kbd.combo(mods, K["SPACE"]); time.sleep(0.8)
        end = source()
        res[name] = {"before": start, "after_1st_press": mid, "after_2nd_press": end,
                     "xremap_emitted": emitted, "pass": mid != start and end == start,
                     "window_still_focused": win.is_active()}
    GLib.idle_add(win.close)


def main():
    out = find_xremap_output()
    kbd = VKbd(); time.sleep(1.5)
    rec = Recorder(out); rec.start()
    app = Gtk.Application(application_id="dev.selftest.InputSwitch", flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activate(a):
        win = Gtk.ApplicationWindow(application=a, title="input switch self-test")
        win.set_default_size(400, 120); win.set_child(Gtk.Entry()); win.present()
        threading.Thread(target=tests, args=(win, kbd, rec), daemon=True).start()

    app.connect("activate", activate); app.run([])
    rec.stop = True; kbd.close()
    print(json.dumps(res, ensure_ascii=False, indent=2).replace("META", "SUPER").replace("57", "SPACE"))


main()
