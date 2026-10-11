#!/usr/bin/env python3
"""End-to-end xremap self-test.

1. Creates a virtual keyboard via /dev/uinput (raw ioctls, no python-evdev).
2. The running xremap service (--watch=device) grabs it like a real keyboard.
3. Opens a GTK4 test window with an Entry + TextView; keys are injected ONLY
   once that window is active, so nothing leaks into the user's other apps.
4. Records what xremap emits on its output device and the resulting text.
"""
import fcntl, os, struct, sys, threading, time, select, glob, json

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x5501, 0x5502
EV_SYN, EV_KEY = 0, 1
EVFMT = "llHHi"
K = dict(ALT=56, BKSP=14, SHIFT=42, HOME=102, LEFT=105, END=107, SPACE=57,
         META=125, CTRL=29, A=30)
NAMES = {v: k for k, v in K.items()}


def find_xremap_output():
    for path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        if open(path).read().strip().startswith("xremap"):
            return "/dev/input/" + path.split("/")[4]
    return None


class VKbd:
    def __init__(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for code in range(1, 249):
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
        name = b"xremap-selftest-kbd"
        setup = struct.pack("HHHH80sI", 0x03, 0x1234, 0x5678, 1, name, 0)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)

    def _emit(self, t, c, v):
        os.write(self.fd, struct.pack(EVFMT, 0, 0, t, c, v))

    def key(self, code, val):
        self._emit(EV_KEY, code, val)
        self._emit(EV_SYN, 0, 0)
        time.sleep(0.03)

    def combo(self, mods, key):
        for m in mods:
            self.key(m, 1)
        self.key(key, 1)
        self.key(key, 0)
        for m in reversed(mods):
            self.key(m, 0)

    def close(self):
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


class Recorder(threading.Thread):
    def __init__(self, path):
        super().__init__(daemon=True)
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.events, self.stop = [], False

    def run(self):
        size = struct.calcsize(EVFMT)
        while not self.stop:
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if r:
                data = os.read(self.fd, size * 64)
                for i in range(0, len(data), size):
                    _, _, t, c, v = struct.unpack(EVFMT, data[i:i + size])
                    if t == EV_KEY and v in (0, 1):
                        self.events.append(f"{NAMES.get(c, c)}{'↓' if v else '↑'}")

    def take(self):
        e, self.events = self.events, []
        return " ".join(e)


results = {}


def run_tests(win, entry, tv, kbd, rec):
    def wait_active(timeout=6):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if GLib.idle_add and win.is_active():
                return True
            time.sleep(0.1)
        return False

    def on_main(fn):
        done = threading.Event(); box = {}
        def w():
            box["v"] = fn(); done.set(); return False
        GLib.idle_add(w); done.wait(3); return box.get("v")

    if not wait_active():
        results["error"] = "test window never became active; aborted without injecting keys"
        GLib.idle_add(win.close); return

    cases = [
        ("entry", "Alt+Backspace", [K["ALT"]], K["BKSP"], "hello world"),
        ("entry", "Alt+Left then type A", [K["ALT"]], K["LEFT"], "hello world"),
        ("entry", "Super+Backspace (Option: delete word)", [K["META"]], K["BKSP"], "hello world"),
        ("textview", "Alt+Backspace (2nd line)", [K["ALT"]], K["BKSP"], "line one\nline two"),
    ]
    for widget, label, mods, key, initial in cases:
        def prep():
            if widget == "entry":
                entry.set_text(initial); entry.grab_focus(); entry.set_position(-1)
            else:
                buf = tv.get_buffer(); buf.set_text(initial)
                buf.place_cursor(buf.get_end_iter()); tv.grab_focus()
        on_main(prep); time.sleep(0.3)
        if not win.is_active():
            results[label] = "window lost focus; skipped"; continue
        rec.take()
        kbd.combo(mods, key)
        if "type A" in label:
            kbd.combo([], K["A"])
        time.sleep(0.4)
        def read():
            if widget == "entry":
                return entry.get_text()
            b = tv.get_buffer(); return b.get_text(b.get_start_iter(), b.get_end_iter(), False)
        results[label] = {"before": initial, "after": on_main(read), "xremap_emitted": rec.take()}
    GLib.idle_add(win.close)


def main():
    out = find_xremap_output()
    if not out:
        print(json.dumps({"error": "xremap output device not found (service not running?)"})); return
    kbd = VKbd()
    time.sleep(1.5)  # let xremap --watch=device grab the new keyboard
    rec = Recorder(out); rec.start()

    app = Gtk.Application(application_id="dev.selftest.Xremap")

    def activate(a):
        win = Gtk.ApplicationWindow(application=a, title="xremap self-test (closes itself)")
        win.set_default_size(420, 200)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        entry = Gtk.Entry(); tv = Gtk.TextView()
        box.append(entry); box.append(tv); win.set_child(box); win.present()
        threading.Thread(target=run_tests, args=(win, entry, tv, kbd, rec), daemon=True).start()

    app.connect("activate", activate)
    app.run([])
    rec.stop = True
    kbd.close()
    grabbed = any(l.strip() for l in open("/proc/bus/input/devices").read().split("\n\n") if "xremap-selftest" in l)
    print(json.dumps({"xremap_output": out, **results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
