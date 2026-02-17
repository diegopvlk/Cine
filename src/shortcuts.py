# shortcuts.py
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
import re
from gettext import gettext as _, gettext as gt

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk

INTERNAL_BINDINGS = f"""\
UP             no-osd add volume 5; #{_("Volume Increase")}
DOWN           no-osd add volume -5; #{_("Volume Decrease")}
WHEEL_UP       no-osd add volume 5
WHEEL_DOWN     no-osd add volume -5
k              cycle pause; #{_("Play/Pause")}
p              cycle pause; #{_("Play/Pause")}
SPACE          cycle pause; #{_("Play/Pause")}
c              no-osd cycle sub-visibility; #{_("Show/Hide Subtitles")}
j              seek -10 exact; show-text "⯇⯇" #{_("Seek 10s Backward")}
l              seek 10 exact; show-text "⯈⯈" #{_("Seek 10s Forward")}
LEFT           seek -5 exact; show-text "⯇⯇" #{_("Seek 5s Backward")}
RIGHT          seek 5 exact; show-text "⯈⯈" #{_("Seek 5s Forward")}
F11            cycle fullscreen; #{_("Fullscreen")}
f              cycle fullscreen; #{_("Fullscreen")}
MBTN_LEFT_DBL  cycle fullscreen
MBTN_MID       cycle fullscreen
MBTN_RIGHT     cycle pause
MBTN_BACK      playlist-prev; 
MBTN_FORWARD   playlist-next; 
WHEEL_LEFT     seek -10; show-text "⯇⯇"
WHEEL_RIGHT    seek 10; show-text "⯈⯈"
=              add video-zoom 0.05; show-text "{_("Zoom")}: ${{video-zoom}}" #{_("Zoom In")}
+              add video-zoom 0.05; show-text "{_("Zoom")}: ${{video-zoom}}" #{_("Zoom In")}
ZOOMIN         add video-zoom 0.05; show-text "{_("Zoom")}: ${{video-zoom}}" #{_("Zoom In")}
-              add video-zoom -0.05; show-text "{_("Zoom")}: ${{video-zoom}}" #{_("Zoom Out")}
ZOOMOUT        add video-zoom -0.05; show-text "{_("Zoom")}: ${{video-zoom}}" #{_("Zoom Out")}
,              add sub-delay -0.1; show-text "{_("Subtitle Delay")}: ${{sub-delay}}" #{_("Decrease Subtitle Delay")}
.              add sub-delay +0.1; show-text "{_("Subtitle Delay")}: ${{sub-delay}}" #{_("Increase Subtitle Delay")}
PGUP           add sub-pos -1; show-text "{_("Subtitle Position")}: ${{sub-pos}}" #{_("Move Subtitles Up")}
PGDWN          add sub-pos +1; show-text "{_("Subtitle Position")}: ${{sub-pos}}" #{_("Move Subtitles Down")}
G              add sub-scale +0.05; show-text "{_("Subtitle Scale")}: ${{sub-scale}}" #{_("Increase Subtitle Scale")}
F              add sub-scale -0.05; show-text "{_("Subtitle Scale")}: ${{sub-scale}}" #{_("Decrease Subtitle Scale")}
m              no-osd cycle mute; #{_("Mute/Unmute")}
ctrl+-         add audio-delay -0.1; show-text "{_("Audio Delay")}: ${{audio-delay}}" #{_("Decrease Audio Delay")}
ctrl+=         add audio-delay 0.1; show-text "{_("Audio Delay")}: ${{audio-delay}}" #{_("Increase Audio Delay")}
ctrl++         add audio-delay 0.1; show-text "{_("Audio Delay")}: ${{audio-delay}}" #{_("Increase Audio Delay")}
PLAY           cycle pause
PAUSE          cycle pause
PLAYPAUSE      cycle pause
PLAYONLY       set pause no
PAUSEONLY      set pause yes
FORWARD        seek 60
REWIND         seek -60
NEXT           playlist-next
PREV           playlist-prev
ctrl+[         frame-step -1 seek #{_("Go Back One Frame")}
ctrl+]         frame-step 1 seek #{_("Advance One Frame")}
Ctrl+LEFT      add chapter -1 #{_("Seek to the Previous Chapter")}
Ctrl+RIGHT     add chapter 1 #{_("Seek to the Next Chapter")}
VOLUME_UP      no-osd add volume 5
VOLUME_DOWN    no-osd add volume -5
MUTE           cycle mute
s              screenshot #{_("Take Screenshot With Subtitles")}
S              screenshot video #{_("Take Screenshot Without Subtitles")}
i              script-binding stats/display-stats #{_("Statistics")}
I              script-binding stats/display-stats-toggle #{_("Statistics Overlay")}
L              cycle-values loop-file "inf" "no"; show-text "{_("Loop")}: ${{loop-file}}" #{_("Loop File")}
1              add contrast -1; show-text "{_("Contrast")}: ${{contrast}}" #{_("Decrease Contrast")}
2              add contrast 1; show-text "{_("Contrast")}: ${{contrast}}" #{_("Increase Contrast")}
3              add brightness -1; show-text "{_("Brightness")}: ${{brightness}}" #{_("Decrease Brightness")}
4              add brightness 1; show-text "{_("Brightness")}: ${{brightness}}" #{_("Increase Brightness")}
5              add gamma -1; show-text "{_("Gamma")}: ${{gamma}}" #{_("Decrease Gamma")}
6              add gamma 1; show-text "{_("Gamma")}: ${{gamma}}" #{_("Increase Gamma")}
7              add saturation -1; show-text "{_("Saturation")}: ${{saturation}}" #{_("Decrease Saturation")}
8              add saturation 1; show-text "{_("Saturation")}: ${{saturation}}" #{_("Increase Saturation")}
[              multiply speed 1/1.1; show-text "{_("Speed")}: ${{speed}}x" #{_("Decrease Playback Speed")}
]              multiply speed 1.1; show-text "{_("Speed")}: ${{speed}}x" #{_("Increase Playback Speed")}
BS             set speed 1.0; show-text "{_("Speed")}: ${{speed}}x" #{_("Reset Playback Speed")}
"""


def translate_mpv_to_gtk(key):
    """Converts mpv key strings to GTK accelerator format with symbol support."""
    mapping = {
        "UP": "Up",
        "DOWN": "Down",
        "LEFT": "Left",
        "RIGHT": "Right",
        "ENTER": "Return",
        "BS": "BackSpace",
        "SPACE": "space",
        "ESC": "Escape",
        "PGUP": "Page_Up",
        "PGDWN": "Page_Down",
        "DEL": "Delete",
        "HOME": "Home",
        "END": "End",
        ".": "period",
        ",": "comma",
        "/": "slash",
        ";": "semicolon",
        "[": "bracketleft",
        "]": "bracketright",
        "{": "braceleft",
        "}": "braceright",
        "\\": "backslash",
        "=": "equal",
        "-": "minus",
        "~": "asciitilde",
        "!": "exclam",
        "@": "at",
        "#": "numbersign",
        "$": "dollar",
        "%": "percent",
        "^": "asciicircum",
        "&": "ampersand",
        "*": "asterisk",
        "(": "parenleft",
        ")": "parenright",
        "_": "underscore",
        "+": "plus",
        ":": "colon",
        '"': "quotedbl",
        "<": "less",
        ">": "greater",
        "?": "question",
        "|": "bar",
        "`": "grave",
        "'": "apostrophe",
    }

    # Handle single uppercase chars
    if len(key) == 1 and key.isupper():
        key = f"<Shift>{key.lower()}"

    # Replace mpv modifiers with GTK format
    key = re.sub(r"ctrl\+", "<Control>", key, flags=re.IGNORECASE)
    key = re.sub(r"alt\+", "<Alt>", key, flags=re.IGNORECASE)
    key = re.sub(r"shift\+", "<Shift>", key, flags=re.IGNORECASE)
    key = re.sub(r"meta\+", "<Meta>", key, flags=re.IGNORECASE)

    parts = key.split(">")
    base_key = parts[-1]

    # Map the base key if it exists in our dictionary
    if base_key.upper() in mapping:
        base_key = mapping[base_key.upper()]
    elif base_key in mapping:
        base_key = mapping[base_key]
    elif len(base_key) == 1:
        # GTK accelerators must be lowercase (e.g., <Control>a, not <Control>A)
        base_key = base_key.lower()

    return ">".join(parts[:-1]) + (">" if len(parts) > 1 else "") + base_key


def get_section_name(cmd):
    """Categorizes an mpv command into a section title."""
    cmd = cmd.lower()

    def is_match(keyword, cmd):
        # matches the boundary between a word char and a non-word char
        return re.search(rf"\b{re.escape(keyword)}\b", cmd)

    mapping = [
        (
            _("Display & Video"),
            [
                "video",
                "fullscreen",
                "contrast",
                "brightness",
                "gamma",
                "saturation",
                "hue",
                "panscan",
                "zoom",
                "rotate",
                "aspect",
                "vf",
            ],
        ),
        (_("Subtitles"), ["sub", "sid"]),
        (_("Audio & Volume"), ["volume", "mute", "audio", "aid", "af", "ao"]),
        (_("Navigation"), ["seek", "chapter", "playlist", "frame", "revert-seek"]),
        (_("Playback"), ["pause", "stop", "quit", "speed", "loop"]),
    ]

    if "screenshot" in cmd:
        return _("Miscellaneous")

    for section, keywords in mapping:
        if any(is_match(k, cmd) for k in keywords):
            return section

    return _("Miscellaneous")


def populate_shortcuts_dialog_mpv(dialog, mpv_bindings):
    """
    Populates an Adw.ShortcutsDialog, joining multiple keys
    if they trigger the same command.
    """
    # Key: (label, section_title), Value: List of gtk_accelerators
    grouped_bindings = {}

    # First Pass: Resolve which keys are active (handling priority)
    resolved_keys = {}
    for b in mpv_bindings:
        key = b.get("key")
        if not key or "MBTN" in key or "WHEEL" in key or b.get("cmd") == "ignore":
            continue
        if b.get("is_weak", False):
            continue

        priority = b.get("priority", 0)
        if key not in resolved_keys or priority >= resolved_keys[key].get(
            "priority", 0
        ):
            resolved_keys[key] = b

    # Second Pass: Group keys by their command/label
    for key, b in resolved_keys.items():
        cmd = b.get("cmd", "")
        gtk_accel = translate_mpv_to_gtk(key)

        success, _, _ = Gtk.accelerator_parse(gtk_accel)
        if not success:
            continue

        # Determine the label (translatable)
        label = b.get("comment")
        if not label:
            clean_cmd = cmd.split(";")[0].strip()
            label = clean_cmd.replace("-", " ")
            label = label.capitalize()

        section_title = get_section_name(cmd)

        # Group by the unique combination of the label and its section
        group_key = (label, section_title)
        if group_key not in grouped_bindings:
            grouped_bindings[group_key] = []
        grouped_bindings[group_key].append(gtk_accel)

    sections = {
        gt("Subtitles"): [],
        gt("Audio & Volume"): [],
        gt("Navigation"): [],
        gt("Display & Video"): [],
        gt("Playback"): [],
        gt("Miscellaneous"): [],
    }

    for (label, title), accels in grouped_bindings.items():
        target = title if title in sections else gt("Miscellaneous")
        # Allows space-separated accelerators
        # e.g. "<Control>q q" shows both shortcuts for the same item
        sections[target].append((label, " ".join(accels)))

    for title, items in sections.items():
        if items:
            section_widget = (
                Adw.ShortcutsSection(  # pyright: ignore[reportAttributeAccessIssue]
                    title=title
                )
            )
            dialog.add(section_widget)
            for label, accels in items:
                section_widget.add(
                    Adw.ShortcutsItem(  # pyright: ignore[reportAttributeAccessIssue]
                        title=label, accelerator=accels
                    )
                )
