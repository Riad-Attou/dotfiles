#!/usr/bin/env python3
import gi, subprocess, sys, os, socket, threading, signal, atexit, hashlib, urllib.request, json
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

def _restore():
    subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"], capture_output=True)
atexit.register(_restore)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_DAEMON_MODE = False

CACHE = os.path.expanduser("~/.cache/waybar-media")
os.makedirs(CACHE, exist_ok=True)
W = 280


def sh(*args):
    try:
        return subprocess.run(list(args), capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ""


def pick_player():
    playing = paused = ""
    for p in sh("playerctl", "-l").splitlines():
        s = sh("playerctl", "-p", p, "status")
        if s == "Playing" and not playing:
            playing = p
        elif s == "Paused" and not paused:
            paused = p
    return playing or paused


def get_info(player):
    if not player:
        return None
    try:
        dur_us = int(sh("playerctl", "-p", player, "metadata", "mpris:length") or "0")
    except ValueError:
        dur_us = 0
    try:
        pos = float(sh("playerctl", "-p", player, "position") or "0")
    except ValueError:
        pos = 0.0
    return {
        "player":   player,
        "status":   sh("playerctl", "-p", player, "status"),
        "title":    sh("playerctl", "-p", player, "metadata", "title"),
        "artist":   sh("playerctl", "-p", player, "metadata", "artist"),
        "album":    sh("playerctl", "-p", player, "metadata", "album"),
        "art_url":  sh("playerctl", "-p", player, "metadata", "mpris:artUrl"),
        "position": pos,
        "duration": dur_us / 1_000_000,
    }


def fetch_art(url):
    if not url:
        return None
    key = hashlib.md5(url.encode()).hexdigest()
    path = os.path.join(CACHE, f"{key}.jpg")
    if not os.path.exists(path):
        try:
            if url.startswith("file://"):
                GdkPixbuf.Pixbuf.new_from_file(url[7:]).savev(path, "jpeg", [], [])
            else:
                tmp = path + ".tmp"
                urllib.request.urlretrieve(url, tmp)
                os.rename(tmp, path)
        except Exception:
            return None
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, W, W, True)
    except Exception:
        return None


def dominant_color(pixbuf):
    """Average of saturated, mid-brightness pixels → accent color."""
    try:
        px  = pixbuf.get_pixels()
        ch  = pixbuf.get_n_channels()
        w   = pixbuf.get_width()
        h   = pixbuf.get_height()
        rs  = pixbuf.get_rowstride()
        rt = gt = bt = n = 0
        for y in range(0, h, 8):
            for x in range(0, w, 8):
                off = y * rs + x * ch
                r, g, b = px[off], px[off + 1], px[off + 2]
                bright = (r + g + b) / 3
                sat    = max(r, g, b) - min(r, g, b)
                if 40 < bright < 215 and sat > 35:
                    rt += r; gt += g; bt += b; n += 1
        if n:
            r, g, b = rt // n, gt // n, bt // n
            # Boost if too dark to be visible on dark background
            br = (r + g + b) / 3
            if br < 90:
                f = 90 / max(br, 1)
                r, g, b = min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f))
            return r, g, b
    except Exception:
        pass
    return 122, 162, 247  # Tokyo Night blue fallback


def fmt(s):
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


BASE_CSS = b"""
window {
    background-color: rgba(22, 22, 30, 0.97);
    border: 1px solid rgba(122, 162, 247, 0.2);
    border-radius: 12px;
}
.no-art { background-color: #16161e; }
label { font-family: "JetBrainsMono Nerd Font"; color: #c0caf5; }
.title  { font-size: 13px; font-weight: bold; }
.artist { font-size: 11px; color: #7aa2f7; }
.album  { font-size: 10px; color: #414868; font-style: italic; }
.time   { font-size: 9px; color: #414868; }
progressbar trough {
    background-color: #1e2030;
    border-radius: 3px; min-height: 4px; border: none;
}
progressbar progress {
    background-color: #7aa2f7;
    border-radius: 3px; min-height: 4px;
}
.controls button {
    background-color: transparent;
    color: #7aa2f7;
    border: none; border-radius: 6px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 18px;
    padding: 4px 14px; margin: 0; min-width: 0;
}
.controls button:hover { background-color: rgba(122, 162, 247, 0.1); }
.controls button.play  { font-size: 24px; color: #c0caf5; }
.controls button.play:hover { background-color: rgba(192, 202, 245, 0.08); }
separator { background-color: rgba(122, 162, 247, 0.1); min-height: 1px; }
"""


class MediaPopup(Gtk.Window):
    def __init__(self):
        super().__init__(title="MediaPopup")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_default_size(W, -1)
        self._player = None
        self._closed = False
        self._dyn    = Gtk.CssProvider()
        self._last_art_url = None

        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "3"])

        base = Gtk.CssProvider()
        base.load_from_data(BASE_CSS)
        scr = Gdk.Screen.get_default()
        pri = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        Gtk.StyleContext.add_provider_for_screen(scr, base, pri)
        Gtk.StyleContext.add_provider_for_screen(scr, self._dyn, pri + 1)

        self._build()

        self._player = pick_player()
        info = get_info(self._player)
        if info:
            self._apply(info)
            self._last_art_url = info["art_url"]
            threading.Thread(target=self._load_art, args=(info["art_url"],), daemon=True).start()
        else:
            self._title_lbl.set_text("Nothing playing")

        self.connect("destroy", self._on_destroy)
        self.connect("key-press-event",
                     lambda _, e: self.destroy() if e.keyval == Gdk.KEY_Escape else None)
        GLib.timeout_add(150,  self._reposition)
        GLib.timeout_add(700,  self._start_watcher)
        GLib.timeout_add(1500, self._tick)

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        # Album art
        self._art = Gtk.Image()
        self._art.set_size_request(W, W // 2)
        self._art.get_style_context().add_class("no-art")
        root.pack_start(self._art, False, False, 0)

        # Metadata
        meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        meta.set_margin_top(12);  meta.set_margin_bottom(2)
        meta.set_margin_start(14); meta.set_margin_end(14)

        self._title_lbl  = self._lbl("", "title",  28)
        self._artist_lbl = self._lbl("", "artist", 34)
        self._album_lbl  = self._lbl("", "album",  34)
        for w in (self._title_lbl, self._artist_lbl, self._album_lbl):
            meta.pack_start(w, False, False, 0)
        root.pack_start(meta, False, False, 0)

        # Progress bar
        self._prog = Gtk.ProgressBar()
        self._prog.set_margin_start(14); self._prog.set_margin_end(14)
        self._prog.set_margin_top(8)
        root.pack_start(self._prog, False, False, 0)

        # Timestamps
        trow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        trow.set_margin_start(14); trow.set_margin_end(14); trow.set_margin_top(2)
        self._pos_lbl = Gtk.Label(label="")
        self._pos_lbl.get_style_context().add_class("time")
        self._dur_lbl = Gtk.Label(label="")
        self._dur_lbl.get_style_context().add_class("time")
        self._dur_lbl.set_halign(Gtk.Align.END)
        trow.pack_start(self._pos_lbl, True, True, 0)
        trow.pack_start(self._dur_lbl, True, True, 0)
        root.pack_start(trow, False, False, 0)

        root.pack_start(Gtk.Separator(), False, False, 6)

        # Controls
        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        ctrl.set_halign(Gtk.Align.CENTER)
        ctrl.set_margin_bottom(12)
        ctrl.get_style_context().add_class("controls")

        prev_btn = Gtk.Button(label="󰒮")
        prev_btn.connect("clicked", lambda _: self._action("previous"))
        self._play_btn = Gtk.Button(label="󰐊")
        self._play_btn.get_style_context().add_class("play")
        self._play_btn.connect("clicked", lambda _: self._action("play-pause"))
        next_btn = Gtk.Button(label="󰒭")
        next_btn.connect("clicked", lambda _: self._action("next"))

        for b in (prev_btn, self._play_btn, next_btn):
            ctrl.pack_start(b, False, False, 0)
        root.pack_start(ctrl, False, False, 0)

    def _lbl(self, text, css_class, max_chars):
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_max_width_chars(max_chars)
        lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        lbl.get_style_context().add_class(css_class)
        return lbl

    # ── Data ──────────────────────────────────────────────────────────

    def _apply(self, info):
        self._title_lbl.set_text(info.get("title") or "Unknown")

        artist = info.get("artist") or ""
        self._artist_lbl.set_text(artist)
        self._artist_lbl.set_visible(bool(artist))

        album = info.get("album") or ""
        self._album_lbl.set_text(album)
        self._album_lbl.set_visible(bool(album))

        self._play_btn.set_label("󰏤" if info.get("status") == "Playing" else "󰐊")

        dur = info.get("duration", 0)
        pos = info.get("position", 0)
        if dur > 0:
            self._prog.set_fraction(min(pos / dur, 1.0))
            self._pos_lbl.set_text(fmt(pos))
            self._dur_lbl.set_text(fmt(dur))
        else:
            self._prog.set_fraction(0)
            self._pos_lbl.set_text("")
            self._dur_lbl.set_text("")

    def _load_art(self, url):
        pb = fetch_art(url)
        GLib.idle_add(self._set_art, pb)

    def _set_art(self, pb):
        if pb:
            self._art.set_from_pixbuf(pb)
            self._art.set_size_request(W, pb.get_height())
            self._art.get_style_context().remove_class("no-art")
            self._art.set_visible(True)
            r, g, b = dominant_color(pb)
            self._dyn.load_from_data(f"""
                .artist {{ color: rgb({r},{g},{b}); }}
                progressbar progress {{ background-color: rgb({r},{g},{b}); }}
                window {{ border-color: rgba({r},{g},{b},0.4); }}
                .controls button {{ color: rgb({r},{g},{b}); }}
                .controls button.play {{ color: #c0caf5; }}
            """.encode())
        else:
            self._art.set_size_request(W, 0)
            self._art.set_visible(False)
        self.show_all()
        if not pb:
            self._art.hide()
        GLib.timeout_add(80, self._reposition)
        return False

    def _action(self, cmd):
        if self._player:
            subprocess.run(["playerctl", "-p", self._player, cmd], capture_output=True)

        def _after():
            info = get_info(self._player or pick_player())
            if info:
                self._apply(info)
            return False
        GLib.timeout_add(200, _after)

    def _tick(self):
        if self._closed:
            return False
        threading.Thread(target=self._bg_refresh, daemon=True).start()
        return True

    def _bg_refresh(self):
        player = pick_player()
        info   = get_info(player)
        def _update():
            if self._closed:
                return False
            self._player = player
            if info:
                self._apply(info)
                # Reload art only when track changes
                if info["art_url"] != self._last_art_url:
                    self._last_art_url = info["art_url"]
                    threading.Thread(target=self._load_art,
                                     args=(info["art_url"],), daemon=True).start()
            return False
        GLib.idle_add(_update)

    # ── Window ────────────────────────────────────────────────────────

    def _reposition(self):
        try:
            cx   = int(sh("hyprctl", "cursorpos").split(",")[0])
            mons = json.loads(sh("hyprctl", "-j", "monitors"))
            mon  = next((m for m in mons if m.get("focused")), mons[0])
            wx   = max(mon["x"] + 4,
                       min(cx - W // 2, mon["x"] + mon["width"] - W - 4))
            subprocess.run(
                ["hyprctl", "dispatch", "movewindowpixel",
                 f"exact {wx} {mon['y'] + 40},title:MediaPopup"],
                capture_output=True)
        except Exception:
            pass
        return False

    def _start_watcher(self):
        def _run():
            rd   = os.environ.get("XDG_RUNTIME_DIR", "")
            inst = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
            sock = f"{rd}/hypr/{inst}/.socket2.sock"
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(sock)
                buf = ""
                while True:
                    data = s.recv(4096).decode("utf-8", errors="ignore")
                    if not data:
                        break
                    buf += data
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.startswith("activewindow>>"):
                            title = line.split(",", 1)[-1] if "," in line else ""
                            if title != "MediaPopup":
                                GLib.idle_add(self.destroy)
                                return
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
        return False

    def _on_destroy(self, _):
        self._closed = True
        subprocess.run(["hyprctl", "keyword", "input:follow_mouse", "1"])
        if not _DAEMON_MODE:
            Gtk.main_quit()


if __name__ == "__main__":
    mypid = os.getpid()
    def _is_py(pid):
        try:
            with open(f"/proc/{pid}/comm") as fh: return fh.read().startswith("python")
        except Exception: return False
    pids  = [int(p) for p in sh("pgrep", "-f", "media-popup.py").splitlines()
             if p and int(p) != mypid and _is_py(int(p))]
    if pids:
        for p in pids:
            try: os.kill(p, signal.SIGUSR1)
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
        p = MediaPopup()
        _inst[0] = p
        p.show_all()

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *_: (_toggle(), True)[1])
    Gtk.main()
