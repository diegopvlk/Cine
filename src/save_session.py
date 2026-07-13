# save-session.py
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

import os
from gettext import gettext as _
from .utils import LAST_PLAYLIST_FILE, is_local_path, idle_add_once
from .preferences import settings


def save_last_playlist_file(win_mpv):
    """Saves the current playlist to a m3u8 file."""

    try:
        win_mpv.write_watch_later_config()
        with open(LAST_PLAYLIST_FILE, "w", encoding="utf-8") as f:
            if win_mpv.idle_active:
                f.write("")
                return

            f.write("#EXTM3U\n")
            for item in win_mpv.playlist:
                path = item.get("filename")
                name_with_ext = os.path.basename(path)
                file_title = os.path.splitext(name_with_ext)[0]
                title = file_title

                if not is_local_path(path):
                    title = item.get("title") or file_title

                f.write(f"#EXTINF:{-1},{title}\n")
                f.write(f"{path}\n")

    except Exception as e:
        print(f"Error saving last playlist file: {e}")


def restore_last_playlist(window, app, win_mpv):
    """Restore the last playlist if its the first window."""

    try:
        if len(app.get_windows()) > 1:
            return

        FILE = LAST_PLAYLIST_FILE

        if not os.path.exists(FILE) or os.path.getsize(FILE) == 0:
            return

        window.start_page.set_sensitive(False)
        window._show_toast(_("Restoring Session…"), force_dismiss=True)
        idle_add_once(win_mpv.loadfile, LAST_PLAYLIST_FILE, "replace")
    except Exception as e:
        print(f"Error restoring last playlist file: {e}")


def is_same_playlist(mpv_playlist):
    """Compares current playlist with the saved file from last session."""

    if not settings.get_boolean("save-session"):
        return

    try:
        with open(LAST_PLAYLIST_FILE, "r", encoding="utf-8") as f:
            saved_filenames = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]

        curr_filenames = [item.get("filename") for item in mpv_playlist]

        return saved_filenames == curr_filenames

    except Exception as e:
        print(f"Error reading last playlist file: {e}")
        return False
