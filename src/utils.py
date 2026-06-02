# utils.py
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

import gi
import os
import ctypes
from urllib.parse import urlparse

gi.require_version("GLib", "2.0")
from gi.repository import GLib

xdg_pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
SCREENSHOT_DIR = os.path.join(xdg_pictures, "Cine Screenshots") if xdg_pictures else ""

base_config = GLib.get_user_config_dir()
CONFIG_DIR = os.path.join(base_config, "cine")
INPUT_CONF = os.path.join(CONFIG_DIR, "input.conf")

old_last_pl_file = os.path.join(CONFIG_DIR, "last-playlist.m3u8")
playlist_dir = os.path.join(CONFIG_DIR, "last-playlist")
LAST_PLAYLIST_FILE = os.path.join(playlist_dir, "last-playlist.m3u8")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(playlist_dir, exist_ok=True)

if os.path.exists(old_last_pl_file):
    from shutil import move

    move(old_last_pl_file, playlist_dir)

is_flatpak = os.environ.get("container") == "flatpak"


def get_has_host_permission():
    if not is_flatpak:
        return True

    try:
        with open("/.flatpak-info", "r") as f:
            for line in f:
                if line.startswith("filesystems="):
                    perms = line.split("=")[-1].strip().split(";")
                    return "host" in perms
    except Exception:
        pass

    return False


has_host_permission = get_has_host_permission()


def get_mouse_bindings(mpv):
    bindings = mpv._get_property("input-bindings")
    active_mouse_bindings = {}

    for b in bindings:
        if "MBTN" in b["key"]:
            active_mouse_bindings[b["key"]] = b["cmd"]

    return active_mouse_bindings


def parse_nonrepeat_bindings(bindings):
    non_repeatable = set()
    try:
        for b in bindings:
            key = b.get("key")
            cmd = b.get("cmd", "")

            if key and "nonrepeatable" in cmd:
                if len(key) == 1 and key.isupper() and key.isalpha():
                    key = f"Shift+{key}"

                non_repeatable.add(key)
    except Exception as e:
        print("parse_nonrepeat_bindings error:", e)

    return non_repeatable


def is_local_path(path):
    parsed = urlparse(str(path))
    if not parsed.scheme or parsed.scheme == "file" or len(parsed.scheme) == 1:
        return True
    return False


def get_gpu_vendor(display, libgl):
    try:
        context = display.get_default_seat().get_display().create_gl_context()
        context.realize()
        context.make_current()

        glGetString = libgl.glGetString
        glGetString.restype = ctypes.c_char_p
        glGetString.argtypes = [ctypes.c_uint]

        # GL_VENDOR is 0x1F00
        return glGetString(0x1F00).decode("utf-8").lower()
    except Exception as e:
        print(f"get_gpu_vendor error: {e}")
        return None


def format_time(seconds):
    if not seconds:
        return "0:00"

    seconds = int(seconds)
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if d > 0:
        return f"{d}:{h:02d}:{m:02d}:{s:02d}"
    elif h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m}:{s:02d}"


MBTN_MAP: dict = {
    1: "MBTN_LEFT",
    2: "MBTN_MID",
    3: "MBTN_RIGHT",
    8: "MBTN_BACK",
    9: "MBTN_FORWARD",
}


KEY_REMAP: dict = {
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "F10": "F10",
    "F11": "F11",
    "F12": "F12",
    "F13": "F13",
    "F14": "F14",
    "F15": "F15",
    "F16": "F16",
    "F17": "F17",
    "F18": "F18",
    "F19": "F19",
    "F20": "F20",
    "Escape": "ESC",
    "BackSpace": "BS",
    "Page_Up": "PGUP",
    "Page_Down": "PGDWN",
    "Left": "LEFT",
    "Right": "RIGHT",
    "Up": "UP",
    "Down": "DOWN",
    "Home": "HOME",
    "End": "END",
    "Insert": "INS",
    "Delete": "DEL",
    "Pause": "PAUSE",
    "space": "SPACE",
    "KP_Add": "KP_ADD",
    "KP_Subtract": "KP_SUBTRACT",
    "KP_Divide": "KP_DIVIDE",
    "KP_Multiply": "KP_MULTIPLY",
    "KP_1": "KP1",
    "KP_2": "KP2",
    "KP_3": "KP3",
    "KP_4": "KP4",
    "KP_5": "KP5",
    "KP_6": "KP6",
    "KP_7": "KP7",
    "KP_8": "KP8",
    "KP_9": "KP9",
    "KP_End": "KP_END",
    "KP_Down": "KP_DOWN",
    "KP_Page_Down": "KP_PGDWN",
    "KP_Left": "KP_LEFT",
    "KP_Begin": "KP_BEGIN",
    "KP_Right": "KP_RIGHT",
    "KP_Home": "KP_HOME",
    "KP_Up": "KP_UP",
    "KP_Page_Up": "KP_PGUP",
    "XF86AudioRaiseVolume": "VOLUME_UP",
    "XF86AudioLowerVolume": "VOLUME_DOWN",
    "XF86AudioMute": "MUTE",
    "XF86PowerOff": "POWER",
    "XF86AudioPlay": "PLAY",
    "XF86AudioPause": "PAUSE",
    "XF86AudioStop": "STOP",
    "XF86AudioNext": "NEXT",
    "XF86AudioPrev": "PREV",
    "ZoomIn": "ZOOMIN",
    "ZoomOut": "ZOOMOUT",
}

SUB_EXTS: tuple = (
    ".aqt",
    ".ass",
    ".dfxp",
    ".idx",
    ".jss",
    ".lrc",
    ".mks",
    ".mpl",
    ".pgs",
    ".rt",
    ".sbv",
    ".scc",
    ".smi",
    ".srt",
    ".ssa",
    ".sub",
    ".sup",
    ".ttml",
    ".txt",
    ".vtt",
)
