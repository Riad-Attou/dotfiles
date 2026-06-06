#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, time, signal, atexit
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

def _restore_follow_mouse():
    subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"],
                   capture_output=True)

atexit.register(_restore_follow_mouse)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_DAEMON_MODE = False

BAT = "/sys/class/power_supply/BAT0"

def read_int(name):
    try: return int(open(f"{BAT}/{name}").read().strip())
    except: return 0

def read_str(name):
    try: return open(f"{BAT}/{name}").read().strip()
    except: return "N/A"

def get_profile():
    try: return open("/sys/firmware/acpi/platform_profile").read().strip()
    except: return "unknown"

def build_markup():
    capacity    = read_int("capacity")
    status      = read_str("status")
    energy_now  = read_int("energy_now")
    energy_full = read_int("energy_full")
    energy_des  = read_int("energy_full_design")
    power_now   = read_int("power_now")
    profile     = get_profile()

    full_wh  = energy_full / 1_000_000
    des_wh   = energy_des  / 1_000_000
    power_w  = power_now   / 1_000_000
    health   = (energy_full / energy_des * 100) if energy_des else 0
    icon     = "󰂄" if status == "Charging" else ("󰚥" if status == "Full" else "󰁹")

    time_line = ""
    if status == "Discharging" and power_now > 0:
        h = energy_now / power_now
        time_line = f'\n<span foreground="#7dcfff">⏱</span>  <span foreground="#c0caf5">{int(h)}h {int((h%1)*60):02d}m remaining</span>'
    elif status == "Charging" and power_now > 0:
        h = (energy_full - energy_now) / power_now
        time_line = f'\n<span foreground="#7dcfff">⏱</span>  <span foreground="#c0caf5">{int(h)}h {int((h%1)*60):02d}m to full</span>'

    p_colors = {"power-saver": "#7aa2f7", "balanced": "#c0caf5", "performance": "#f7768e", "max-power": "#bb9af7"}
    p_labels = {"power-saver": "🔵  Low Power", "balanced": "⚪  Balanced", "performance": "🔴  Performance", "max-power": "🟣  Max Power"}
    sep = '<span foreground="#2a2b3d">──────────────────────</span>'

    return (
        f'<span foreground="#7aa2f7" weight="bold" size="large">{icon}  {capacity}%</span>'
        f'  <span foreground="#545c7e">{status}</span>\n{sep}\n'
        f'<span foreground="#e0af68">⚡</span>  <span foreground="#c0caf5">{power_w:.1f}W</span>'
        f'   <span foreground="#f7768e">❤</span>  <span foreground="#c0caf5">{health:.0f}%</span>\n'
        f'<span foreground="#9ece6a">🔋</span>  <span foreground="#c0caf5">{full_wh:.1f}Wh</span>'
        f'  <span foreground="#545c7e">/ {des_wh:.1f}Wh</span>'
        + time_line +
        f'\n{sep}\n'
        f'<span foreground="{p_colors.get(profile, "#c0caf5")}" weight="bold">'
        f'{p_labels.get(profile, profile)}</span>'
    )

CSS = b"""
window {
    background-color: rgba(26, 27, 38, 0.97);
    border: 1px solid rgba(122, 162, 247, 0.3);
    border-radius: 8px;
}
label {
    color: #c0caf5;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
    padding: 12px 16px;
}
button {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid rgba(122, 162, 247, 0.25);
    border-radius: 4px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 10px;
    padding: 3px 6px;
    margin: 4px 3px;
}
button:hover { background-color: #283457; }
"""

class BatteryPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="BatteryPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        self.label = Gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_markup(build_markup())
        vbox.pack_start(self.label, True, True, 0)

        profile = get_profile()
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_box.set_margin_bottom(8)
        btn_box.set_margin_start(8)
        btn_box.set_margin_end(8)
        for lbl, pname in [
            ("🔵 Save" + (" ✓" if profile == "power-saver"  else ""), "power-saver"),
            ("⚪ Bal"  + (" ✓" if profile == "balanced"     else ""), "balanced"),
            ("🔴 Perf" + (" ✓" if profile == "performance"  else ""), "performance"),
        ]:
            btn = Gtk.Button(label=lbl)
            btn.connect("clicked", self.on_profile, pname)
            btn_box.pack_start(btn, True, True, 0)
        vbox.pack_start(btn_box, False, False, 0)

        GLib.timeout_add_seconds(3, self.refresh)
        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(600, self.start_focus_watcher)

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
                            if title != 'BatteryPopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False  # Don't repeat the GLib timeout

    def refresh(self):
        self.label.set_markup(build_markup())
        return True

    def on_profile(self, _, pname):
        subprocess.run(["powerprofilesctl", "set", pname])
        subprocess.run(["pkill", "-36", "waybar"])
        self.destroy()

if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "battery-popup.py"], capture_output=True, text=True)
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
        p = BatteryPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
