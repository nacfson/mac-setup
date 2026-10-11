#!/usr/bin/env python3
"""Spotlight self-test: Alt+Space (Cmd+Space) opens the GNOME overview search.

Injects Alt+Space into a focused GTK test window, checks OverviewActive turns
true, then presses Alt+Space again and checks it closes (restoring your state).
Also checks the input language did NOT change.
"""
import json, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xremap_selftest import VKbd, Recorder, find_xremap_output, K

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio

res = {}


def overview():
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
                          "--object-path", "/org/gnome/Shell", "--method",
                          "org.freedesktop.DBus.Properties.Get", "org.gnome.Shell", "OverviewActive"],
                         capture_output=True, text=True).stdout
    return "true" in out


def wait_overview(want, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if overview() == want:
            return True
        time.sleep(0.1)
    return False


def source():
    return subprocess.run(["ibus", "engine"], capture_output=True, text=True).stdout.strip()


def tests(win, kbd, rec):
    t0 = time.time()
    while time.time() - t0 < 6 and not win.is_active():
        time.sleep(0.1)
    if not win.is_active() or overview():
        res["error"] = "test window not focused (or overview already open); aborted"
        GLib.idle_add(win.close); return
    time.sleep(0.5)
    lang0 = source()
    rec.take(); kbd.combo([K["ALT"]], K["SPACE"])
    opened = wait_overview(True); time.sleep(0.5); emitted = rec.take(); lang1 = source()
    kbd.combo([K["ALT"]], K["SPACE"])
    closed = wait_overview(False)
    if not closed:  # safety: never leave the overview open
        kbd.combo([], 1); time.sleep(0.8)
    res["Alt+Space (Cmd+Space)"] = {
        "overview_opened": opened, "overview_closed_on_2nd_press": closed,
        "language_unchanged": lang0 == lang1, "language": lang1,
        "xremap_emitted": emitted, "pass": opened and closed and lang0 == lang1}
    GLib.idle_add(win.close)


def main():
    out = find_xremap_output()
    kbd = VKbd(); time.sleep(1.5)
    rec = Recorder(out); rec.start()
    app = Gtk.Application(application_id="dev.selftest.Spotlight", flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activate(a):
        win = Gtk.ApplicationWindow(application=a, title="spotlight self-test")
        win.set_default_size(400, 120); win.set_child(Gtk.Entry()); win.present()
        threading.Thread(target=tests, args=(win, kbd, rec), daemon=True).start()

    app.connect("activate", activate); app.run([])
    rec.stop = True; kbd.close()
    print(json.dumps(res, indent=2).replace("57", "SPACE"))


main()
