#!/usr/bin/env python3
import gi, subprocess, threading, os, time
os.environ["G_MESSAGES_DEBUG"] = ""
os.environ["GTK_DEBUG"] = ""
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

FIFO = "/tmp/copy_indicator_fifo"

CSS = b"""
window {
    background-color: rgba(26, 27, 38, 0.88);
    border: 1px solid rgba(122, 162, 247, 0.45);
    border-radius: 14px;
}
label {
    color: #7aa2f7;
    font-family: "JetBrainsMono Nerd Font Mono";
    font-size: 26px;
    padding: 12px 16px;
}
"""

prov = Gtk.CssProvider()
prov.load_from_data(CSS)

_active = None

class CopyIndicator(Gtk.Window):
    def __init__(self):
        super().__init__(title="CopyIndicator")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_app_paintable(True)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.add(Gtk.Label(label="󰆏"))
        self.props.opacity = (0)
        self.show_all()

        self._step = 0
        GLib.timeout_add(18, self._tick)

    def _tick(self):
        self._step += 1
        if self._step <= 15:        # 270ms fade in
            self.props.opacity = (self._step / 15.0)
        elif self._step <= 42:      # 486ms hold
            self.props.opacity = (1.0)
        elif self._step <= 62:      # 360ms fade out
            self.props.opacity = (1.0 - (self._step - 42) / 20.0)
        else:
            self.destroy()
            return False
        return True


def show_indicator():
    global _active
    if _active:
        try:
            _active.destroy()
        except Exception:
            pass
    _active = CopyIndicator()
    return False


def watch_clipboard():
    try:
        os.unlink(FIFO)
    except FileNotFoundError:
        pass
    os.mkfifo(FIFO)

    subprocess.Popen(
        ["wl-paste", "--type", "text", "--watch",
         "sh", "-c", f"printf 'x' > {FIFO}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    while True:
        try:
            with open(FIFO, "r") as f:
                f.read()
            GLib.idle_add(show_indicator)
        except Exception:
            time.sleep(0.1)


if __name__ == "__main__":
    threading.Thread(target=watch_clipboard, daemon=True).start()
    Gtk.main()
