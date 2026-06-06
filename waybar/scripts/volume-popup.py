#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit, json
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

def _restore_follow_mouse():
    subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"], capture_output=True)

atexit.register(_restore_follow_mouse)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_DAEMON_MODE = False

def get_volume(target):
    out = subprocess.run(["wpctl", "get-volume", target],
                         capture_output=True, text=True).stdout.strip()
    muted = "MUTED" in out
    try:
        vol = int(float(out.split()[1]) * 100)
    except Exception:
        vol = 0
    return vol, muted

def get_sinks():
    try:
        out = subprocess.run(["pactl", "--format=json", "list", "sinks"],
                             capture_output=True, text=True).stdout
        sinks   = json.loads(out)
        default = subprocess.run(["pactl", "get-default-sink"],
                                 capture_output=True, text=True).stdout.strip()
        return [(s["name"], s.get("description", s["name"]), s["name"] == default)
                for s in sinks]
    except Exception:
        return []

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
    background-color: #7aa2f7;
    border-radius: 4px;
}
.mic-section scale highlight {
    background-color: #9ece6a;
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
button {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid rgba(122, 162, 247, 0.25);
    border-radius: 4px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 10px;
    padding: 3px 8px;
    margin: 2px 8px;
}
button:hover { background-color: #283457; }
button.active-sink {
    border-color: rgba(122, 162, 247, 0.6);
    color: #7aa2f7;
}
separator {
    background-color: rgba(122, 162, 247, 0.15);
    min-height: 1px;
    margin: 4px 8px;
}
"""

class VolumePopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="VolumePopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(260, -1)
        self._updating = False
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(4)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        self.add(vbox)

        # --- Output ---
        self.out_lbl = Gtk.Label()
        self.out_lbl.set_use_markup(True)
        self.out_lbl.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(self.out_lbl, False, False, 0)

        self.out_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.out_scale.set_draw_value(False)
        self.out_scale.set_size_request(220, -1)
        self.out_scale.add_mark(100, Gtk.PositionType.BOTTOM, None)
        vbox.pack_start(self.out_scale, False, False, 4)

        self.out_mute_btn = Gtk.Button()
        self.out_mute_btn.connect("clicked", self.on_mute_out)
        vbox.pack_start(self.out_mute_btn, False, False, 0)

        vbox.pack_start(Gtk.Separator(), False, False, 3)

        # --- Mic ---
        mic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        mic_box.get_style_context().add_class("mic-section")

        self.mic_lbl = Gtk.Label()
        self.mic_lbl.set_use_markup(True)
        self.mic_lbl.set_halign(Gtk.Align.CENTER)
        mic_box.pack_start(self.mic_lbl, False, False, 0)

        self.mic_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.mic_scale.set_draw_value(False)
        self.mic_scale.set_size_request(220, -1)
        self.mic_scale.add_mark(100, Gtk.PositionType.BOTTOM, None)
        mic_box.pack_start(self.mic_scale, False, False, 4)

        self.mic_mute_btn = Gtk.Button()
        self.mic_mute_btn.connect("clicked", self.on_mute_mic)
        mic_box.pack_start(self.mic_mute_btn, False, False, 0)
        vbox.pack_start(mic_box, False, False, 0)

        # --- Output device switcher (only shown if >1 sink) ---
        sinks = get_sinks()
        if len(sinks) > 1:
            vbox.pack_start(Gtk.Separator(), False, False, 3)
            hdr = Gtk.Label()
            hdr.set_markup('<span foreground="#565f89" size="small">Output device</span>')
            hdr.set_halign(Gtk.Align.CENTER)
            hdr.set_margin_bottom(2)
            vbox.pack_start(hdr, False, False, 0)
            for sink_name, sink_desc, is_default in sinks:
                short = sink_desc if len(sink_desc) <= 32 else sink_desc[:30] + "…"
                btn = Gtk.Button(label=("✓  " if is_default else "    ") + short)
                if is_default:
                    btn.get_style_context().add_class("active-sink")
                btn.connect("clicked", self.on_set_sink, sink_name)
                vbox.pack_start(btn, False, False, 0)

        self._sync_from_system()
        self.out_scale.connect("value-changed", self.on_out_changed)
        self.mic_scale.connect("value-changed", self.on_mic_changed)

        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(150, self._move_below_bar)
        GLib.timeout_add(600, self.start_focus_watcher)
        threading.Thread(target=self._watch_pulseaudio, daemon=True).start()

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
                            f"exact {wx} {bar_y},title:VolumePopup"],
                           capture_output=True)
        except Exception:
            pass
        return False

    def _sync_from_system(self):
        out_vol, out_muted = get_volume("@DEFAULT_AUDIO_SINK@")
        mic_vol, mic_muted = get_volume("@DEFAULT_AUDIO_SOURCE@")
        self._updating = True
        self.out_scale.set_value(out_vol)
        self.mic_scale.set_value(mic_vol)
        self._updating = False
        self._refresh_out(out_vol, out_muted)
        self._refresh_mic(mic_vol, mic_muted)

    def _refresh_out(self, vol, muted):
        if muted:
            icon, color = "󰝟", "#565f89"
        elif vol == 0:
            icon, color = "󰕿", "#c0caf5"
        elif vol < 50:
            icon, color = "󰖀", "#c0caf5"
        else:
            icon, color = "󰕾", "#7aa2f7"
        self.out_lbl.set_markup(
            f'<span foreground="{color}" size="large">{icon}</span>'
            f'  <span foreground="#c0caf5" weight="bold" size="large">{vol}%</span>')
        self.out_mute_btn.set_label("󰝟  Unmute" if muted else "󰕾  Mute")

    def _refresh_mic(self, vol, muted):
        icon, color = ("󰍭", "#565f89") if muted else ("󰍬", "#9ece6a")
        self.mic_lbl.set_markup(
            f'<span foreground="{color}" size="large">{icon}</span>'
            f'  <span foreground="#c0caf5" weight="bold" size="large">{vol}%</span>')
        self.mic_mute_btn.set_label("󰍭  Unmute mic" if muted else "󰍬  Mute mic")

    def on_out_changed(self, scale):
        if self._updating: return
        vol = int(scale.get_value())
        subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol}%"])
        _, muted = get_volume("@DEFAULT_AUDIO_SINK@")
        self._refresh_out(vol, muted)

    def on_mic_changed(self, scale):
        if self._updating: return
        vol = int(scale.get_value())
        subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", f"{vol}%"])
        _, muted = get_volume("@DEFAULT_AUDIO_SOURCE@")
        self._refresh_mic(vol, muted)

    def on_mute_out(self, _):
        subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
        self._sync_from_system()

    def on_mute_mic(self, _):
        subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
        self._sync_from_system()

    def on_set_sink(self, _, sink_name):
        subprocess.run(["pactl", "set-default-sink", sink_name])
        self.destroy()

    def _watch_pulseaudio(self):
        proc = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
        for line in proc.stdout:
            if ("sink" in line or "source" in line) and ("change" in line or "new" in line):
                GLib.idle_add(self._sync_from_system)

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
                            if title != 'VolumePopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False


if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "volume-popup.py"], capture_output=True, text=True)
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
        p = VolumePopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
