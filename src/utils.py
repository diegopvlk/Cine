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

import ctypes
import logging
import os
from urllib.parse import urlparse

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("GdkX11", "4.0")
gi.require_version("GdkWayland", "4.0")
from gi.repository import Gdk, GdkWayland, GdkX11, GLib

logging.basicConfig(format="%(levelname)s: [%(filename)s:%(lineno)d] %(message)s")
logger = logging.getLogger(__name__)

gtk = ctypes.CDLL("libgtk-4.so.1")
display = Gdk.Display.get_default()

DEFAULT_OCCUPY_SCREEN = 0.4
# Screens with this resolution or smaller are handled as small
SMALL_SCREEN_AREA = 1280 * 1024
# For small monitors, occupy 80% of the screen area
SMALL_OCCUPY_SCREEN = 0.8

try:
    join = os.path.join

    XDG_PICTURES = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    SCREENSHOT_DIR = join(XDG_PICTURES, "Cine Screenshots") if XDG_PICTURES else ""

    BASE_CONFIG = GLib.get_user_config_dir()

    CONFIG_DIR = join(BASE_CONFIG, "cine")
    INPUT_CONF = join(CONFIG_DIR, "input.conf")
    MPV_CONF = join(CONFIG_DIR, "mpv.conf")
    WATCH_HISTORY_JSONL = join(CONFIG_DIR, "watch_history.jsonl")

    OLD_PL_FILE = join(CONFIG_DIR, "last-playlist.m3u8")
    PLAYLIST_DIR = join(CONFIG_DIR, "last-playlist")
    LAST_PLAYLIST_FILE = join(PLAYLIST_DIR, "last-playlist.m3u8")

    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(PLAYLIST_DIR, exist_ok=True)

    for file in [
        INPUT_CONF,
        MPV_CONF,
        WATCH_HISTORY_JSONL,
    ]:
        if not os.path.exists(file):
            open(file, "w").close()

    if os.path.exists(OLD_PL_FILE):
        from shutil import move

        move(OLD_PL_FILE, PLAYLIST_DIR)
    elif not os.path.exists(LAST_PLAYLIST_FILE):
        open(LAST_PLAYLIST_FILE, "w").close()

except Exception:
    logger.exception("Failed to create files/folders")


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
        logger.exception("get_has_host_permission failed")

    return False


has_host_permission = get_has_host_permission()


def get_mouse_bindings(bindings):
    active_mouse_bindings = {}
    try:
        for b in bindings:
            if "MBTN" in b["key"]:
                active_mouse_bindings[b["key"]] = b["cmd"]
    except Exception:
        logger.exception("get_mouse_bindings failed")

    return active_mouse_bindings


def parse_bindings(bindings):
    non_repeatable = set()
    has_enter, has_kp_enter = False, False
    try:
        for b in bindings:
            key = b.get("key")
            cmd = b.get("cmd", "ignore")

            if key == "ENTER" and cmd != "ignore":
                has_enter = True

            if key == "KP_ENTER" and cmd != "ignore":
                has_kp_enter = True

            if key and "nonrepeatable" in cmd:
                if len(key) == 1 and key.isupper() and key.isalpha():
                    key = f"Shift+{key}"
                non_repeatable.add(key)
    except Exception:
        logger.exception("parse_nonrepeat_bindings failed")

    return (non_repeatable, has_enter, has_kp_enter)


def is_local_path(path):
    parsed = urlparse(str(path))
    s = parsed.scheme
    return bool(not s or s == "file" or len(s) == 1)


def _run_once(func, *args, **kwargs):
    func(*args, **kwargs)
    return GLib.SOURCE_REMOVE


def idle_add_once(func, *args, **kwargs) -> int:
    return GLib.idle_add(_run_once, func, *args, **kwargs)


def timeout_add_once(interval: int, func, *args, **kwargs) -> int:
    return GLib.timeout_add(interval, _run_once, func, *args, **kwargs)


def timeout_add_seconds_once(interval: int, func, *args, **kwargs) -> int:
    return GLib.timeout_add_seconds(interval, _run_once, func, *args, **kwargs)


def get_display_param():
    param = {}

    # see https://gist.github.com/omnp/6ac3385e2b3f6cab987d84e6477e636a

    def get_pointer(display):
        ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
        ctypes.pythonapi.PyCapsule_GetPointer.argtypes = (ctypes.py_object,)
        return ctypes.pythonapi.PyCapsule_GetPointer(display.__gpointer__, None)

    try:
        if isinstance(display, GdkWayland.WaylandDisplay):
            gtk.gdk_wayland_display_get_wl_display.restype = ctypes.c_void_p
            gtk.gdk_wayland_display_get_wl_display.argtypes = [ctypes.c_void_p]
            ptr = gtk.gdk_wayland_display_get_wl_display(get_pointer(display))
            if ptr:
                param["wl_display"] = ptr
        elif isinstance(display, GdkX11.X11Display):
            gtk.gdk_x11_display_get_xdisplay.restype = ctypes.c_void_p
            gtk.gdk_x11_display_get_xdisplay.argtypes = [ctypes.c_void_p]
            ptr = gtk.gdk_x11_display_get_xdisplay(get_pointer(display))
            if ptr:
                param["x11_display"] = ptr
    except Exception:
        logger.exception("get_display_param failed")

    return param


def _get_fallback_w_h(width, height):
    aspect_ratio = width / height
    max_w, max_h = 1120, 630

    if aspect_ratio < 1:
        new_h = round(max_w / aspect_ratio)
        new_w = max_w
    else:
        new_w = round(max_w * aspect_ratio)
        new_h = max_w

    if new_w > max_w or new_h > max_h:
        scale = min(max_w / new_w, max_h / new_h)
        new_w = round(new_w * scale)
        new_h = round(new_h * scale)

    return new_w, new_h


def _get_window_w_h(window, width, height):
    # Code mostly copied from showtime/loupe:
    # https://gitlab.gnome.org/GNOME/showtime/-/blob/25066ad0ca1c20bd8b9f6f776f5be75b31277039/showtime/widgets/window.py#L467-500
    # https://gitlab.gnome.org/GNOME/loupe/-/blob/4ca5f9e03d18667db5d72325597cebc02887777a/src/widgets/image/rendering.rs#L151

    if not (surface := window.get_surface()):
        logger.error("Could not get GdkSurface to set window size")
        return _get_fallback_w_h(width, height)

    if not (monitor := window.props.display.get_monitor_at_surface(surface)):
        logger.error("Could not get GdkMonitor to set window size")
        return _get_fallback_w_h(width, height)

    hidpi_scale = surface.props.scale_factor
    monitor_rect = monitor.props.geometry
    monitor_width = monitor_rect.width
    monitor_height = monitor_rect.height

    monitor_area = monitor_width * monitor_height
    logical_monitor_area = monitor_area * pow(hidpi_scale, 2)

    occupy_area_factor = (
        SMALL_OCCUPY_SCREEN
        if logical_monitor_area <= SMALL_SCREEN_AREA
        else DEFAULT_OCCUPY_SCREEN
    )

    video_area = width * height
    size_scale = (monitor_area / video_area * occupy_area_factor) ** 0.5
    target_scale = min(1, size_scale)
    new_w = width * target_scale
    new_h = height * target_scale

    max_w = monitor_width - 96
    if new_w > max_w:
        new_w = max_w
        new_h = height * new_w / width

    max_h = monitor_height - 106 * hidpi_scale
    if new_h > max_h:
        new_h = max_h
        new_w = width * new_h / height

    target_aspect = width / height
    final_h = round(new_h)
    final_w = round(new_w)
    tolerance = 0.00001

    # More precise aspect ratio due to how size is handled during mpv ctx render
    # to prevent a 1px black line along the window border
    for _ in range(20):
        current_aspect = final_w / final_h

        if abs(current_aspect - target_aspect) <= tolerance:
            break

        if current_aspect < target_aspect:
            final_w += 1
        else:
            final_h += 1

    return final_w, final_h


def set_window_size(window, width, height):
    if width <= 0 or height <= 0:
        return

    scale_tiers = (
        (144, 1.6666),
        (240, 1.50),
        (360, 1.3333),
        (480, 1.15),
    )

    # Scale up small videos
    for threshold, multiplier in scale_tiers:
        if min(width, height) <= threshold:
            width *= multiplier
            height *= multiplier
            break

    new_w, new_h = _get_window_w_h(window, width, height)
    window.set_default_size(new_w, new_h)


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


def append_modifiers(key_state, mods: list):
    """Adds Ctrl/Alt/Shift/Meta"""
    if key_state & Gdk.ModifierType.CONTROL_MASK:
        mods.append("Ctrl")
    if key_state & Gdk.ModifierType.ALT_MASK:
        mods.append("Alt")
    if key_state & Gdk.ModifierType.SHIFT_MASK:
        mods.append("Shift")
    if key_state & Gdk.ModifierType.META_MASK:
        mods.append("Meta")


class PrimaryClick:
    PLAY_PAUSE = 0
    FOCUS_PLAY_PAUSE = 1
    BYPASS = 2


class SecondaryClick:
    PLAY_PAUSE = 0
    CONTEXT_MENU = 1
    BYPASS = 2


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
    "F21": "F21",
    "F22": "F22",
    "F23": "F23",
    "F24": "F24",
    "Escape": "ESC",
    "Return": "ENTER",
    "BackSpace": "BS",
    "Tab": "TAB",
    "ISO_Left_Tab": "TAB",
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
    "Print": "PRINT",
    "Sys_Req": "PRINT",
    "Menu": "MENU",
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
    "KP_0": "KP0",
    "KP_Decimal": "KP_DEC",
    "KP_Delete": "KP_DEL",
    "KP_Separator": "KP_SEPARATOR",
    "KP_Insert": "KP_INS",
    "KP_Enter": "KP_ENTER",
    "KP_End": "KP_END",
    "KP_Down": "KP_DOWN",
    "KP_Page_Down": "KP_PGDWN",
    "KP_Next": "KP_PGDWN",
    "KP_Left": "KP_LEFT",
    "KP_Begin": "KP_BEGIN",
    "KP_Right": "KP_RIGHT",
    "KP_Home": "KP_HOME",
    "KP_Up": "KP_UP",
    "KP_Page_Up": "KP_PGUP",
    "KP_Prior": "KP_PGUP",
    "AudioRaiseVolume": "VOLUME_UP",
    "AudioLowerVolume": "VOLUME_DOWN",
    "AudioMute": "MUTE",
    "PowerOff": "POWER",
    "AudioPlay": "PLAY",
    "AudioPause": "PAUSE",
    "AudioStop": "STOP",
    "AudioNext": "NEXT",
    "AudioPrev": "PREV",
    "AudioRewind": "PREV",
    "AudioForward": "NEXT",
    "AudioMedia": "MEDIA",
    "AudioMicMute": "MUTE",
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
