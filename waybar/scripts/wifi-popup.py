#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit, time
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
button.toggle-on {
    border-color: rgba(122, 162, 247, 0.5);
    color: #7aa2f7;
}
button.toggle-off {
    border-color: rgba(86, 95, 137, 0.5);
    color: #565f89;
}
button.danger {
    border-color: rgba(247, 118, 142, 0.5);
    color: #f7768e;
}
separator {
    background-color: rgba(122, 162, 247, 0.15);
    min-height: 1px;
    margin: 4px 8px;
}
"""

_DAEMON_MODE = False
_last_close = [0.0]   # monotonic time of the last window destroy (toggle debounce)

def nm(*args):
    return subprocess.run(["nmcli"] + list(args),
                          capture_output=True, text=True).stdout.strip()

def is_wifi_enabled():
    return nm("radio", "wifi").strip() == "enabled"

def get_wifi_interface():
    out = nm("-t", "-f", "DEVICE,TYPE", "device", "status")
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "wifi":
            return parts[0]
    return None

def get_saved_ssids():
    out = nm("-t", "-f", "NAME,TYPE", "connection", "show")
    saved = set()
    for line in out.splitlines():
        parts = line.rsplit(":", 1)
        if len(parts) == 2 and parts[1] == "802-11-wireless":
            saved.add(parts[0].replace("\\:", ":"))
    return saved

def get_networks():
    out = nm("-t", "-f", "IN-USE,SSID,SIGNAL", "dev", "wifi", "list")
    networks = []
    seen = set()
    for line in out.splitlines():
        parts = line.rsplit(":", 1)
        if len(parts) != 2 or not parts[1].strip().isdigit():
            continue
        signal = parts[1].strip()
        rest = parts[0].strip()
        if rest.startswith("*:"):
            in_use, ssid = True, rest[2:]
        elif rest.startswith(":"):
            in_use, ssid = False, rest[1:]
        else:
            continue
        ssid = ssid.replace("\\:", ":")
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        networks.append((in_use, ssid, signal))
    return networks

def get_current_ip():
    iface = get_wifi_interface()
    if not iface:
        return None
    out = nm("-t", "-f", "IP4.ADDRESS[1]", "device", "show", iface)
    for line in out.splitlines():
        if "IP4.ADDRESS" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1]:
                return parts[1].strip().split("/")[0]
    return None

def signal_icon(sig_str):
    try:
        sig = int(sig_str)
    except ValueError:
        return "󰤯"
    if sig >= 75: return "󰤨"
    if sig >= 50: return "󰤥"
    if sig >= 25: return "󰤢"
    return "󰤟"


class WifiPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="WifiPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(380, -1)
        self._closed = False
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.vbox.set_margin_top(10)
        self.vbox.set_margin_bottom(10)
        self.vbox.set_margin_start(12)
        self.vbox.set_margin_end(12)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_max_content_height(320)
        self.scroll.set_propagate_natural_height(True)
        self.scroll.add(self.vbox)
        outer.pack_start(self.scroll, True, True, 0)

        self._build_ui()
        self._auto_rescan()

        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(600, self.start_focus_watcher)

    def _build_ui(self):
        # Stray timers (auto-rescan, action rebuilds) can fire after the window
        # was closed; without this guard they re-map a bare, empty toplevel.
        if self._closed:
            return
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        enabled = is_wifi_enabled()

        # Header row
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = "󰤨" if enabled else "󰤭"
        color = "#7aa2f7" if enabled else "#565f89"
        title = Gtk.Label()
        title.set_markup(f'<span foreground="{color}" size="large">{icon}</span>'
                         f'  <span foreground="#c0caf5" weight="bold">Wi-Fi</span>')
        title.set_halign(Gtk.Align.START)
        hbox.pack_start(title, True, True, 0)

        toggle = Gtk.Button(label="On" if enabled else "Off")
        toggle.get_style_context().add_class("toggle-on" if enabled else "toggle-off")
        toggle.connect("clicked", self.on_toggle)
        hbox.pack_end(toggle, False, False, 0)

        if enabled:
            rescan_btn = Gtk.Button(label="↻")
            rescan_btn.connect("clicked", self.on_rescan)
            hbox.pack_end(rescan_btn, False, False, 0)

        self.vbox.pack_start(hbox, False, False, 0)

        if enabled:
            sep = Gtk.Separator()
            self.vbox.pack_start(sep, False, False, 0)

            saved = get_saved_ssids()
            networks = get_networks()
            if networks:
                for in_use, ssid, sig in networks:
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    lbl = Gtk.Label()
                    lbl.set_markup(f'{signal_icon(sig)}  {GLib.markup_escape_text(ssid)}')
                    lbl.set_halign(Gtk.Align.START)
                    lbl.set_ellipsize(3)
                    lbl.set_max_width_chars(28)
                    row.pack_start(lbl, True, True, 0)

                    if in_use:
                        btn = Gtk.Button(label="Disconnect")
                        btn.get_style_context().add_class("connected")
                        btn.connect("clicked", self.on_disconnect)
                        row.pack_end(btn, False, False, 0)

                        ip = get_current_ip()
                        if ip:
                            ip_lbl = Gtk.Label()
                            ip_lbl.set_markup(
                                f'<span foreground="#565f89" size="small">{ip}</span>')
                            row.pack_end(ip_lbl, False, False, 4)
                    else:
                        is_saved = ssid in saved
                        btn = Gtk.Button(label="Connect")
                        btn.connect("clicked", self.on_connect, ssid, is_saved)
                        row.pack_end(btn, False, False, 0)

                        if is_saved:
                            forget_btn = Gtk.Button(label="Forget")
                            forget_btn.get_style_context().add_class("danger")
                            forget_btn.connect("clicked", self.on_forget, ssid)
                            row.pack_end(forget_btn, False, False, 0)

                    self.vbox.pack_start(row, False, False, 2)
            else:
                lbl = Gtk.Label(label="No networks found")
                lbl.set_halign(Gtk.Align.CENTER)
                self.vbox.pack_start(lbl, False, False, 4)

        self.show_all()

    def _auto_rescan(self):
        if not is_wifi_enabled():
            return
        threading.Thread(
            target=lambda: subprocess.run(
                ["nmcli", "device", "wifi", "rescan"], capture_output=True),
            daemon=True).start()
        GLib.timeout_add(2500, self._build_ui)

    def on_toggle(self, _):
        enabled = is_wifi_enabled()
        subprocess.run(["nmcli", "radio", "wifi", "off" if enabled else "on"])
        GLib.timeout_add(500, self._build_ui)

    def on_connect(self, _, ssid, is_saved):
        # For known networks, use `connection up` — more reliable after an
        # explicit disconnect than `device wifi connect`.
        if is_saved:
            cmd = ["nmcli", "connection", "up", "id", ssid]
        else:
            cmd = ["nmcli", "device", "wifi", "connect", ssid]
        threading.Thread(
            target=lambda: subprocess.run(cmd, capture_output=True),
            daemon=True).start()
        GLib.timeout_add(3000, self._build_ui)

    def on_disconnect(self, _):
        iface = get_wifi_interface()
        if iface:
            threading.Thread(
                target=lambda: subprocess.run(
                    ["nmcli", "device", "disconnect", iface], capture_output=True),
                daemon=True).start()
        GLib.timeout_add(1500, self._build_ui)

    def on_forget(self, _, ssid):
        threading.Thread(
            target=lambda: subprocess.run(
                ["nmcli", "connection", "delete", "id", ssid], capture_output=True),
            daemon=True).start()
        GLib.timeout_add(500, self._build_ui)

    def on_rescan(self, _):
        threading.Thread(
            target=lambda: subprocess.run(
                ["nmcli", "device", "wifi", "rescan"], capture_output=True),
            daemon=True).start()
        GLib.timeout_add(2000, self._build_ui)

    def on_destroy(self, _):
        self._closed = True
        _last_close[0] = time.monotonic()
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
                            if title != 'WifiPopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False


if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "wifi-popup.py"], capture_output=True, text=True)
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
        # A waybar click that closes the popup also fires the focus-watcher's
        # auto-close; both race. If a window was just destroyed, treat this as
        # the close (don't re-open an empty one).
        if time.monotonic() - _last_close[0] < 0.5:
            return
        if _inst[0]:
            try: _inst[0].destroy()
            except: pass
        p = WifiPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
