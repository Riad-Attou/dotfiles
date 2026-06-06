#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit, glob, json
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

def _restore_follow_mouse():
    subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"], capture_output=True)

atexit.register(_restore_follow_mouse)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_DAEMON_MODE = False

def get_brightness():
    out = subprocess.run(["brightnessctl", "-m"], capture_output=True, text=True).stdout
    parts = out.strip().split(",")
    if len(parts) >= 4:
        try:
            return int(parts[3].strip('%'))
        except ValueError:
            pass
    return 50

def find_kbd_backlight():
    """Returns (device_name, current_value, max_value) or None."""
    for path in glob.glob("/sys/class/leds/*/brightness"):
        parent = os.path.dirname(path)
        name   = os.path.basename(parent)
        if "kbd" not in name.lower() and "keyboard" not in name.lower():
            continue
        try:
            max_val = int(open(os.path.join(parent, "max_brightness")).read().strip())
            cur_val = int(open(path).read().strip())
            if max_val > 0:
                return name, cur_val, max_val
        except Exception:
            pass
    return None

def set_kbd_backlight(device, value):
    path = f"/sys/class/leds/{device}/brightness"
    try:
        with open(path, "w") as f:
            f.write(str(value))
    except PermissionError:
        subprocess.run(["sudo", "tee", path],
                       input=str(value), text=True, capture_output=True)

CSS = b"""
window {
    background-color: rgba(26, 27, 38, 0.97);
    border: 1px solid rgba(122, 162, 247, 0.3);
    border-radius: 8px;
}
scale trough {
    background-color: #2a2b3d;
    border-radius: 4px;
    min-height: 6px;
}
scale highlight {
    background-color: #e0af68;
    border-radius: 4px;
}
.kbd-section scale highlight {
    background-color: #7aa2f7;
}
scale slider {
    background-color: #c0caf5;
    border-radius: 50%;
    min-width: 14px;
    min-height: 14px;
}
label {
    color: #c0caf5;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}
separator {
    background-color: rgba(122, 162, 247, 0.15);
    min-height: 1px;
    margin: 4px 8px;
}
"""

class BrightnessPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="BrightnessPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(260, -1)
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        vbox.set_margin_start(14)
        vbox.set_margin_end(14)
        self.add(vbox)

        # --- Screen brightness ---
        brightness = get_brightness()

        self.scr_lbl = Gtk.Label()
        self.scr_lbl.set_use_markup(True)
        self.scr_lbl.set_halign(Gtk.Align.CENTER)
        self._update_scr_label(brightness)
        vbox.pack_start(self.scr_lbl, False, False, 0)

        self.scr_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.scr_scale.set_draw_value(False)
        self.scr_scale.set_size_request(220, -1)
        self.scr_scale.set_value(brightness)
        self.scr_scale.connect("value-changed", self._on_scr_changed)
        vbox.pack_start(self.scr_scale, False, False, 6)

        # --- Keyboard backlight (if available) ---
        kbd = find_kbd_backlight()
        if kbd:
            self.kbd_name, kbd_cur, self.kbd_max = kbd
            vbox.pack_start(Gtk.Separator(), False, False, 4)

            kbd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            kbd_box.get_style_context().add_class("kbd-section")

            self.kbd_lbl = Gtk.Label()
            self.kbd_lbl.set_use_markup(True)
            self.kbd_lbl.set_halign(Gtk.Align.CENTER)
            self._update_kbd_label(int(kbd_cur / self.kbd_max * 100))
            kbd_box.pack_start(self.kbd_lbl, False, False, 0)

            self.kbd_scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, self.kbd_max, 1)
            self.kbd_scale.set_draw_value(False)
            self.kbd_scale.set_size_request(220, -1)
            self.kbd_scale.set_value(kbd_cur)
            self.kbd_scale.connect("value-changed", self._on_kbd_changed)
            kbd_box.pack_start(self.kbd_scale, False, False, 6)
            vbox.pack_start(kbd_box, False, False, 0)

        self.show_all()
        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(150, self._move_below_bar)
        GLib.timeout_add(600, self.start_focus_watcher)

    def _move_below_bar(self):
        try:
            cx = int(subprocess.run(["hyprctl", "cursorpos"],
                     capture_output=True, text=True).stdout.split(",")[0].strip())
            mons = json.loads(subprocess.run(["hyprctl", "-j", "monitors"],
                              capture_output=True, text=True).stdout)
            mon   = next((m for m in mons if m.get("focused")), mons[0])
            win_w = self.get_allocated_width() or 260
            bar_y = mon["y"] + 40
            wx    = max(mon["x"] + 4,
                        min(cx - win_w // 2, mon["x"] + mon["width"] - win_w - 4))
            subprocess.run(["hyprctl", "dispatch", "movewindowpixel",
                            f"exact {wx} {bar_y},title:BrightnessPopup"],
                           capture_output=True)
        except Exception:
            pass
        return False

    def _update_scr_label(self, val):
        icon = "󰃞" if val < 33 else ("󰃟" if val < 66 else "󰃠")
        self.scr_lbl.set_markup(
            f'<span foreground="#e0af68" size="large">{icon}</span>'
            f'  <span foreground="#c0caf5" weight="bold" size="large">{val}%</span>')

    def _update_kbd_label(self, pct):
        self.kbd_lbl.set_markup(
            f'<span foreground="#7aa2f7" size="large">󰌌</span>'
            f'  <span foreground="#c0caf5" weight="bold" size="large">{pct}%</span>')

    def _on_scr_changed(self, scale):
        val = int(scale.get_value())
        subprocess.run(["brightnessctl", "set", f"{val}%", "-q"])
        self._update_scr_label(val)

    def _on_kbd_changed(self, scale):
        val = int(scale.get_value())
        set_kbd_backlight(self.kbd_name, val)
        self._update_kbd_label(int(val / self.kbd_max * 100))

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
                            if title != 'BrightnessPopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False


if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "brightness-popup.py"], capture_output=True, text=True)
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
        p = BrightnessPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
