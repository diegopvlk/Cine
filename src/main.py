# main.py
#
# Copyright 2026 Diego Povliuk
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import subprocess
import sys
from gettext import gettext as _
from typing import cast

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GObject", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkX11", "4.0")
gi.require_version("GdkWayland", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Adw, Gio, GLib, Gtk

from .mpris import MPRIS
from .preferences import Preferences, settings
from .save_session import is_same_playlist
from .utils import set_window_size
from .window import CineWindow

logger = logging.getLogger(__name__)

os.environ["GSK_RENDERER"] = "gl"

# Set the icon shown in gnome sound settings
os.environ["PIPEWIRE_PROPS"] = '{application.icon-name="io.github.diegopvlk.Cine"}'


class CineApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id="io.github.diegopvlk.Cine",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
            resource_base_path="/io/github/diegopvlk/Cine",
        )

        self.mpris = MPRIS(self)

        self.can_restore_session = True

        self.add_main_option(
            "new-window",
            ord("n"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Open a new window",
            None,
        )

        self.connect("shutdown", self._on_shutdown)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().props.color_scheme = Adw.ColorScheme.FORCE_DARK

        self._create_action("new-window", lambda *a: self.activate(), ["<primary>n"])
        self._create_action("quit", lambda *a: self.quit(), ["<primary>q"])
        self._create_action("about", self._on_about_action)
        self._create_action(
            "preferences", self._on_preferences_action, ["<primary>comma"]
        )

    def do_activate(self):
        win = CineWindow(application=self)
        self._set_size_and_present(win)

    def _set_size_and_present(self, window, width=1920, height=1080):
        window.realize()
        set_window_size(window, width, height)
        window.present()

    def do_open(self, files, n_files, hint):
        self.can_restore_session = False
        win: CineWindow = cast(CineWindow, self.props.active_window)
        open_new = settings.get_boolean("open-new-windows") or not win
        vid_w, vid_h = 1920, 1080

        if open_new:
            win = CineWindow(application=self)
            win.start_page.set_visible(False)

            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height:stream_side_data=rotation",
                    "-of",
                    "csv=s=x:p=0",
                    files[0].get_path() or files[0].get_uri(),
                ]

                res = subprocess.run(cmd, check=False, capture_output=True, text=True)

                # "1920x1080x-90" or just "1920x1080"
                p = res.stdout.split("x")

                try:
                    rotation = int(p[2]) if len(p) > 2 and p[2] else 0
                except ValueError:
                    rotation = 0

                vertical = abs(rotation) in (90, 270)

                if len(p) > 1:
                    vid_w = int(p[1]) if vertical else int(p[0])
                    vid_h = int(p[0]) if vertical else int(p[1])
            except Exception:
                logger.exception("Metadata probe failed")

        self._set_size_and_present(win, vid_w, vid_h)

        if not open_new:
            if is_same_playlist(win.mpv.playlist):
                win.mpv.write_watch_later_config()
            win.mpv.stop()

        for gfile in files:
            if path := (gfile.get_path() or gfile.get_uri()):
                win.mpv.loadfile(path, "append-play")

        for window in self.get_windows():
            w = cast(CineWindow, window)
            # Pause previous opened windows
            w.mpv.command_async("set", "pause", w != win)

        win.hide_ui_timeout()

    def do_handle_local_options(self, options: GLib.VariantDict):
        # Copied from showtime: https://gitlab.gnome.org/GNOME/showtime/-/blob/25066ad0ca1c20bd8b9f6f776f5be75b31277039/showtime/main.py#L211-224
        """Handle local command line arguments."""
        self.register()  # This is so props.is_remote works

        if self.props.is_remote:
            if options.contains("new-window"):
                return -1

            print("Cine is running, to open a new window, run with --new-window.")
            return 0

        return -1

    def _on_preferences_action(self, *args):
        """Callback for the app.preferences action."""
        preferences = Preferences(self.props.active_window)
        preferences.present(self.props.active_window)

    def _on_about_action(self, *args):
        """Callback for the app.about action."""
        APP_VERSION = sys.modules["__main__"].VERSION
        about = Adw.AboutDialog(
            application_name=_("Cine"),
            application_icon="io.github.diegopvlk.Cine",
            developer_name="Diego Povliuk",
            version=APP_VERSION,
            copyright="© 2026 Diego Povliuk",
            issue_url="https://github.com/diegopvlk/Cine/issues",
            license_type=Gtk.License.GPL_3_0,
        )
        try:
            # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
            about.set_translator_credits(_("translator-credits"))
        except NameError:
            pass

        about.add_acknowledgement_section(
            None,
            [
                "MPV https://mpv.io/",
                "python-mpv https://pypi.org/project/python-mpv/",
                "Celluloid https://celluloid-player.github.io/",
                "Showtime https://apps.gnome.org/Showtime/",
                "Workbench https://apps.gnome.org/Workbench/",
            ],
        )

        about.add_link(
            "Sponsor on GitHub",
            "https://github.com/sponsors/diegopvlk",
        )

        about.add_link(
            "Donate (PayPal)",
            "https://www.paypal.com/donate?hosted_button_id=DVL7H35GA66X6",
        )

        about.add_link(
            "Doar (Pix): diego.pvlk@gmail.com",
            "diego.pvlk@gmail.com",
        )

        about.add_other_app(
            "io.github.diegopvlk.Dosage", "Dosage", "Keep track of your treatments"
        )

        about.add_other_app(
            "io.github.diegopvlk.Tomatillo", "Tomatillo", "Focus better, work smarter"
        )

        about.present(self.props.active_window)

    def _create_action(self, name, callback, shortcuts=None):
        """Add an application action."""
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

    def _on_shutdown(self, *args):
        for win in self.get_windows():
            win.close()


def main(version):
    """The application's entry point."""
    app = CineApplication()
    return app.run(sys.argv)
