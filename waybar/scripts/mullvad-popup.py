#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

def _restore_follow_mouse():
    subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"], capture_output=True)

atexit.register(_restore_follow_mouse)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

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
}
button {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid rgba(122, 162, 247, 0.25);
    border-radius: 4px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 10px;
    padding: 3px 10px;
}
button:hover { background-color: #283457; }
button.connected {
    border-color: rgba(115, 218, 202, 0.5);
    color: #73daca;
}
button.toggle-off {
    border-color: rgba(86, 95, 137, 0.5);
    color: #565f89;
}
separator {
    background-color: rgba(122, 162, 247, 0.15);
    min-height: 1px;
    margin: 4px 8px;
}
"""

_DAEMON_MODE = False

def get_status():
    out = subprocess.run(["mullvad", "status"], capture_output=True, text=True).stdout.strip()
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if not lines:
        return False, "", []
    connected = lines[0].lower().startswith("connected")
    location  = lines[0] if connected else ""
    details   = lines[1:] if connected else []
    return connected, location, details


class MullvadPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="MullvadPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(320, -1)
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.vbox.set_margin_top(10)
        self.vbox.set_margin_bottom(10)
        self.vbox.set_margin_start(12)
        self.vbox.set_margin_end(12)
        self.add(self.vbox)

        self._build_ui()

        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(600, self.start_focus_watcher)

    def _build_ui(self):
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        connected, location, details = get_status()

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon  = "󰒃" if connected else "󰒄"
        color = "#73daca" if connected else "#565f89"
        title = Gtk.Label()
        title.set_markup(f'<span foreground="{color}" size="large">{icon}</span>'
                         f'  <span foreground="#c0caf5" weight="bold">Mullvad VPN</span>')
        title.set_halign(Gtk.Align.START)
        hbox.pack_start(title, True, True, 0)

        btn = Gtk.Button(label="Disconnect" if connected else "Connect")
        btn.get_style_context().add_class("connected" if connected else "toggle-off")
        btn.connect("clicked", self.on_toggle, connected)
        hbox.pack_end(btn, False, False, 0)
        self.vbox.pack_start(hbox, False, False, 0)

        if connected and (location or details):
            self.vbox.pack_start(Gtk.Separator(), False, False, 0)

            if location:
                loc_lbl = Gtk.Label()
                loc_lbl.set_markup(
                    f'<span foreground="#c0caf5">{GLib.markup_escape_text(location)}</span>')
                loc_lbl.set_halign(Gtk.Align.START)
                loc_lbl.set_line_wrap(True)
                self.vbox.pack_start(loc_lbl, False, False, 0)

            for detail in details:
                d_lbl = Gtk.Label()
                d_lbl.set_markup(
                    f'<span foreground="#565f89" size="small">'
                    f'{GLib.markup_escape_text(detail)}</span>')
                d_lbl.set_halign(Gtk.Align.START)
                self.vbox.pack_start(d_lbl, False, False, 0)

        self.show_all()

    def on_toggle(self, _, connected):
        cmd = ["mullvad", "disconnect"] if connected else ["mullvad", "connect"]
        threading.Thread(
            target=lambda: subprocess.run(cmd, capture_output=True),
            daemon=True).start()
        GLib.timeout_add(2000, self._build_ui)

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
                            if title != 'MullvadPopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False


if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "mullvad-popup.py"], capture_output=True, text=True)
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
        p = MullvadPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
