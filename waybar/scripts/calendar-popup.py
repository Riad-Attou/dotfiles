#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit, json
import calendar as cal
from datetime import date
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

def _restore_follow_mouse():
    subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"], capture_output=True)

atexit.register(_restore_follow_mouse)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_DAEMON_MODE = False

cal.setfirstweekday(0)  # Monday first
DAYS   = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

CSS = b"""
window {
    background-color: rgba(26, 27, 38, 0.97);
    border: 1px solid rgba(122, 162, 247, 0.3);
    border-radius: 8px;
}
label {
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
    color: #c0caf5;
}
button {
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
    min-height: 0;
    min-width: 0;
    padding: 2px 10px;
    color: #565f89;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 15px;
    outline: none;
}
button:hover {
    color: #c0caf5;
    background-color: transparent;
}
.month-label {
    color: #7aa2f7;
    font-weight: bold;
}
.dayname {
    color: #565f89;
    font-size: 11px;
    padding: 0 6px 6px 6px;
}
.day {
    padding: 5px 6px;
    min-width: 26px;
    min-height: 18px;
    border-radius: 5px;
}
.today {
    background-color: #7aa2f7;
    color: #1a1b26;
    font-weight: bold;
}
.other-month {
    color: #3b4261;
}
"""


class CalendarPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="CalendarPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        today = date.today()
        self._year  = today.year
        self._month = today.month
        self._today = today
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        self.add(outer)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.pack_start(self.vbox, True, True, 0)

        self._build_ui()

        self.show_all()
        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(150, self._move_below_bar)
        GLib.timeout_add(600, self.start_focus_watcher)

    def _build_ui(self):
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        # Header: ‹ Month Year ›
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        prev_btn = Gtk.Button(label="‹")
        prev_btn.connect("clicked", self._on_prev)
        hbox.pack_start(prev_btn, False, False, 0)

        month_lbl = Gtk.Label(label=f"{MONTHS[self._month - 1]}  {self._year}")
        month_lbl.get_style_context().add_class("month-label")
        hbox.pack_start(month_lbl, True, True, 0)

        next_btn = Gtk.Button(label="›")
        next_btn.connect("clicked", self._on_next)
        hbox.pack_end(next_btn, False, False, 0)
        self.vbox.pack_start(hbox, False, False, 0)

        # Grid
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(2)
        grid.set_row_spacing(2)
        grid.set_margin_top(6)

        for col, name in enumerate(DAYS):
            lbl = Gtk.Label(label=name)
            lbl.get_style_context().add_class("dayname")
            lbl.set_halign(Gtk.Align.CENTER)
            lbl.set_valign(Gtk.Align.CENTER)
            grid.attach(lbl, col, 0, 1, 1)

        for row, week in enumerate(cal.monthcalendar(self._year, self._month)):
            for col, day in enumerate(week):
                if day == 0:
                    lbl = Gtk.Label(label="")
                else:
                    lbl = Gtk.Label(label=str(day))
                    lbl.get_style_context().add_class("day")
                    if (day == self._today.day and
                            self._month == self._today.month and
                            self._year == self._today.year):
                        lbl.get_style_context().add_class("today")
                lbl.set_halign(Gtk.Align.CENTER)
                lbl.set_valign(Gtk.Align.CENTER)
                grid.attach(lbl, col, row + 1, 1, 1)

        self.vbox.pack_start(grid, False, False, 0)
        self.show_all()

    def _on_prev(self, _):
        self._month -= 1
        if self._month < 1:
            self._month = 12
            self._year -= 1
        self._build_ui()

    def _on_next(self, _):
        self._month += 1
        if self._month > 12:
            self._month = 1
            self._year += 1
        self._build_ui()

    def _move_below_bar(self):
        try:
            cx = int(subprocess.run(["hyprctl", "cursorpos"],
                     capture_output=True, text=True).stdout.split(",")[0].strip())
            mons = json.loads(subprocess.run(["hyprctl", "-j", "monitors"],
                              capture_output=True, text=True).stdout)
            mon   = next((m for m in mons if m.get("focused")), mons[0])
            win_w = self.get_allocated_width() or 280
            bar_y = mon["y"] + 40
            wx    = max(mon["x"] + 4,
                        min(cx - win_w // 2, mon["x"] + mon["width"] - win_w - 4))
            subprocess.run(["hyprctl", "dispatch", "movewindowpixel",
                            f"exact {wx} {bar_y},title:CalendarPopup"],
                           capture_output=True)
        except Exception:
            pass
        return False

    def on_destroy(self, _):
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"])
        if not _DAEMON_MODE:
            Gtk.main_quit()

    def on_key(self, _, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def start_focus_watcher(self):
        def watch():
            runtime_dir = os.environ.get('XDG_RUNTIME_DIR', '')
            instance    = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
            sock_path   = f"{runtime_dir}/hypr/{instance}/.socket2.sock"
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(sock_path)
                buf = ""
                while True:
                    data = s.recv(4096).decode('utf-8', errors='ignore')
                    if not data:
                        break
                    buf += data
                    while '\n' in buf:
                        line, buf = buf.split('\n', 1)
                        if line.startswith('activewindow>>'):
                            title = line.split(',', 1)[-1] if ',' in line else ''
                            if title != 'CalendarPopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False


if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "calendar-popup.py"], capture_output=True, text=True)
    def _is_py(pid):
        try:
            with open(f"/proc/{pid}/comm") as fh: return fh.read().startswith("python")
        except Exception: return False
    others = [int(p) for p in result.stdout.split()
              if p and int(p) != mypid and _is_py(int(p))]
    if others:
        for pid in others:
            try: os.kill(pid, signal.SIGUSR1)
            except: pass
        sys.exit(0)

    _DAEMON_MODE = True
    _inst = [None]

    def _toggle():
        if _inst[0] and _inst[0].get_visible():
            _inst[0].destroy()
            return
        if _inst[0]:
            try: _inst[0].destroy()
            except: pass
        p = CalendarPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
