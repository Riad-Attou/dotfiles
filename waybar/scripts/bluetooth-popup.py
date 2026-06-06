#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit, time, re
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
_device_cache: list = []
_powered_cache: bool = True
_cache_lock = threading.Lock()
_last_close = [0.0]   # monotonic time of the last window destroy (toggle debounce)

def bt_cmd(*args):
    return subprocess.run(["bluetoothctl"] + list(args),
                          capture_output=True, text=True).stdout.strip()

def is_powered():
    return "Powered: yes" in bt_cmd("show")

def get_devices():
    lines = bt_cmd("devices").splitlines()
    macs_names = []
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) >= 3:
            macs_names.append((parts[1], parts[2]))

    results = []
    lock = threading.Lock()

    def fetch(mac, name):
        info = bt_cmd("info", mac)
        connected = "Connected: yes" in info
        paired    = "Paired: yes" in info
        battery   = None
        m = re.search(r'Battery Percentage.*?\((\d+)\)', info)
        if m:
            battery = int(m.group(1))
        with lock:
            results.append((mac, name, connected, paired, battery))

    threads = [threading.Thread(target=fetch, args=(mac, name)) for mac, name in macs_names]
    for t in threads: t.start()
    for t in threads: t.join()

    # Sort: connected first, then paired, then discovered
    results.sort(key=lambda x: (not x[2], not x[3], x[1].lower()))
    return results


class BluetoothPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="BluetoothPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(360, -1)
        self._scanning = False
        self._needs_refresh = True   # one-shot guard for the background cache refresh
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

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(320)
        scroll.set_propagate_natural_height(True)
        scroll.add(self.vbox)
        outer.pack_start(scroll, True, True, 0)

        self._build_ui()

        self.connect("destroy", self.on_destroy)
        self.connect("key-press-event", self.on_key)
        GLib.timeout_add(600, self.start_focus_watcher)

    def _build_ui(self):
        if self._closed:
            return
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        powered = is_powered()

        # Header row
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon  = "󰂱" if powered else "󰂲"
        color = "#7aa2f7" if powered else "#565f89"
        title = Gtk.Label()
        title.set_markup(f'<span foreground="{color}" size="large">{icon}</span>'
                         f'  <span foreground="#c0caf5" weight="bold">Bluetooth</span>')
        title.set_halign(Gtk.Align.START)
        hbox.pack_start(title, True, True, 0)

        toggle = Gtk.Button(label="On" if powered else "Off")
        toggle.get_style_context().add_class("toggle-on" if powered else "toggle-off")
        toggle.connect("clicked", self.on_toggle)
        hbox.pack_end(toggle, False, False, 0)

        if powered:
            scan_btn = Gtk.Button(label="Scanning…" if self._scanning else "↻ Scan")
            scan_btn.set_sensitive(not self._scanning)
            scan_btn.connect("clicked", self.on_scan)
            hbox.pack_end(scan_btn, False, False, 0)

        self.vbox.pack_start(hbox, False, False, 0)

        if powered:
            self.vbox.pack_start(Gtk.Separator(), False, False, 0)

            with _cache_lock:
                devices = list(_device_cache) if _device_cache else get_devices()
            # Refresh cache once in the background, then rebuild with fresh data.
            # Guarded by _needs_refresh: without it, every rebuild scheduled another
            # rebuild → endless loop that kept tearing down the buttons (unclickable).
            if self._needs_refresh:
                self._needs_refresh = False
                threading.Thread(target=lambda: (
                    _refresh_bt_cache(),
                    GLib.idle_add(self._build_ui) if self.get_realized() else None
                ), daemon=True).start()
            if devices:
                showed_nearby_header = False
                for mac, name, connected, paired, battery in devices:
                    if not paired and not showed_nearby_header:
                        nearby_lbl = Gtk.Label()
                        nearby_lbl.set_markup(
                            '<span foreground="#565f89" size="small">Nearby</span>')
                        nearby_lbl.set_halign(Gtk.Align.START)
                        self.vbox.pack_start(nearby_lbl, False, False, 2)
                        showed_nearby_header = True

                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

                    name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    name_lbl = Gtk.Label(label=name)
                    name_lbl.set_halign(Gtk.Align.START)
                    name_lbl.set_ellipsize(3)
                    name_lbl.set_max_width_chars(24)
                    name_box.pack_start(name_lbl, False, False, 0)
                    if battery is not None:
                        bat_lbl = Gtk.Label()
                        bat_lbl.set_markup(
                            f'<span foreground="#565f89" size="small">󰁹 {battery}%</span>')
                        bat_lbl.set_halign(Gtk.Align.START)
                        name_box.pack_start(bat_lbl, False, False, 0)
                    row.pack_start(name_box, True, True, 0)

                    if paired:
                        if connected:
                            btn = Gtk.Button(label="Disconnect")
                            btn.get_style_context().add_class("connected")
                            btn.connect("clicked", self.on_disconnect, mac)
                            row.pack_end(btn, False, False, 0)
                        else:
                            remove_btn = Gtk.Button(label="Remove")
                            remove_btn.get_style_context().add_class("danger")
                            remove_btn.connect("clicked", self.on_remove, mac)
                            row.pack_end(remove_btn, False, False, 0)

                            conn_btn = Gtk.Button(label="Connect")
                            conn_btn.connect("clicked", self.on_connect, mac)
                            row.pack_end(conn_btn, False, False, 0)
                    else:
                        pair_btn = Gtk.Button(label="Pair")
                        pair_btn.connect("clicked", self.on_pair, mac)
                        row.pack_end(pair_btn, False, False, 0)

                    self.vbox.pack_start(row, False, False, 2)
            else:
                lbl = Gtk.Label(label="No devices found")
                lbl.set_halign(Gtk.Align.CENTER)
                self.vbox.pack_start(lbl, False, False, 4)

        self.show_all()

    def on_toggle(self, _):
        powered = is_powered()
        bt_cmd("power", "off" if powered else "on")
        self._needs_refresh = True
        GLib.timeout_add(300, self._build_ui)

    def on_scan(self, _):
        if self._scanning:
            return
        self._scanning = True
        self._build_ui()

        def do_scan():
            proc = subprocess.Popen(
                ["bluetoothctl"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.stdin.write("scan on\n")
            proc.stdin.flush()
            time.sleep(8)
            try:
                proc.stdin.write("scan off\nquit\n")
                proc.stdin.flush()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

        threading.Thread(target=do_scan, daemon=True).start()
        GLib.timeout_add(8500, self._finish_scan)

    def _finish_scan(self):
        self._scanning = False
        self._needs_refresh = True
        if self.get_realized():
            self._build_ui()
        return False

    def on_connect(self, _, mac):
        threading.Thread(target=lambda: bt_cmd("connect", mac), daemon=True).start()
        self._needs_refresh = True
        GLib.timeout_add(1500, self._build_ui)

    def on_disconnect(self, _, mac):
        threading.Thread(target=lambda: bt_cmd("disconnect", mac), daemon=True).start()
        self._needs_refresh = True
        GLib.timeout_add(1000, self._build_ui)

    def on_pair(self, _, mac):
        threading.Thread(target=lambda: bt_cmd("pair", mac), daemon=True).start()
        self._needs_refresh = True
        GLib.timeout_add(3000, self._build_ui)

    def on_remove(self, _, mac):
        threading.Thread(target=lambda: bt_cmd("remove", mac), daemon=True).start()
        self._needs_refresh = True
        GLib.timeout_add(500, self._build_ui)

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
                            if title != 'BluetoothPopup':
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=watch, daemon=True).start()
        return False


def _refresh_bt_cache():
    global _powered_cache, _device_cache
    powered = is_powered()
    devices = get_devices() if powered else []
    with _cache_lock:
        _powered_cache = powered
        _device_cache  = devices

if __name__ == "__main__":
    mypid = os.getpid()
    result = subprocess.run(["pgrep", "-f", "bluetooth-popup.py"], capture_output=True, text=True)
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
        p = BluetoothPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    # Pre-warm bluetooth device cache so first open is instant
    threading.Thread(target=_refresh_bt_cache, daemon=True).start()
    GLib.timeout_add_seconds(30, lambda: threading.Thread(
        target=_refresh_bt_cache, daemon=True).start() or True)
    Gtk.main()
