# preferences.py
#
# Copyright 2025 Diego Povliuk
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
from gettext import gettext as _

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, Gtk
from .utils import has_host_permission

settings = Gio.Settings.new("io.github.diegopvlk.Cine")


def sync_mpv_with_settings(window):
    """Apply settings values to the mpv instance"""
    player = window.mpv
    player["sub-color"] = settings.get_string("subtitle-color")
    player["sub-scale"] = settings.get_double("subtitle-scale")
    player["sub-font"] = settings.get_string("subtitle-font")
    player["slang"] = settings.get_string("subtitle-languages")
    player["alang"] = settings.get_string("audio-languages")
    player["volume"] = settings.get_int("volume")
    hwdec_enabled = settings.get_boolean("hwdec")
    norm_enabled = settings.get_boolean("normalize-volume")

    sub_bg = settings.get_boolean("subtitle-bg")
    player["sub-border-style"] = "background-box" if sub_bg else "outline-and-shadow"
    player["sub-shadow-offset"] = 8 if sub_bg else 0.6
    player["sub-back-color"] = (
        settings.get_string("subtitle-bg-color") if sub_bg else "#97000000"
    )

    if hwdec_enabled:
        player.command_async("vf", "remove", "@hflip")
        player.command_async("vf", "remove", "@vflip")
        player["hwdec"] = window.conf_hwdec + ["auto"]
    else:
        player["hwdec"] = "no"

    if norm_enabled:
        player.command("af", "add", "@cine_loudnorm:lavfi=[loudnorm=I=-20]")


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/preferences.ui")
class Preferences(Adw.Dialog):
    __gtype_name__ = "Preferences"

    open_new_row: Adw.SwitchRow = Gtk.Template.Child()
    sub_color_row: Adw.ActionRow = Gtk.Template.Child()
    reset_sub_color: Gtk.Button = Gtk.Template.Child()
    reset_sub_font: Gtk.Button = Gtk.Template.Child()
    font_row: Adw.ActionRow = Gtk.Template.Child()
    font_label: Gtk.Label = Gtk.Template.Child()
    subtitle_scale_row: Adw.SpinRow = Gtk.Template.Child()
    sub_color_btn: Gtk.ColorDialogButton = Gtk.Template.Child()
    sub_bg_color_btn: Gtk.ColorDialogButton = Gtk.Template.Child()
    subtitle_bg_switch: Gtk.Switch = Gtk.Template.Child()
    subtitle_lang_row: Adw.EntryRow = Gtk.Template.Child()
    audio_lang_row: Adw.EntryRow = Gtk.Template.Child()
    thumb_preview_row: Adw.SwitchRow = Gtk.Template.Child()
    hwdec_row: Adw.SwitchRow = Gtk.Template.Child()
    normalize_volume_row: Adw.SwitchRow = Gtk.Template.Child()
    save_session_switch: Gtk.Switch = Gtk.Template.Child()
    save_position_switch: Gtk.Switch = Gtk.Template.Child()

    def __init__(self, active_window, **kwargs):
        super().__init__(**kwargs)
        self.win = active_window
        self.player = active_window.mpv

        self._bind_ui()
        self._setup_mpv_updates()

        font = settings.get_string("subtitle-font")
        self.font_label.set_label(font)

        self.sub_color_btn.connect("notify::rgba", self._on_sub_color_selected)
        self.reset_sub_color.connect("clicked", self._on_sub_color_reset)
        self.font_row.connect("activated", self._on_font_activated)
        self.reset_sub_font.connect("clicked", self._on_font_reset)

        self.sub_color = Gdk.RGBA()
        self.sub_color.parse(settings.get_string("subtitle-color"))
        self.sub_color_btn.set_dialog(
            Gtk.ColorDialog(title=_("Subtitle Color"), modal=True, with_alpha=False)
        )
        self.sub_color_btn.set_rgba(self.sub_color)

        self.sub_bg_color_btn.connect("notify::rgba", self._on_sub_bg_color_selected)

        bg_hex = settings.get_string("subtitle-bg-color").lstrip("#")
        self.sub_bg_color = Gdk.RGBA()
        self.sub_bg_color.alpha = int(bg_hex[0:2], 16) / 255
        self.sub_bg_color.red = int(bg_hex[2:4], 16) / 255
        self.sub_bg_color.green = int(bg_hex[4:6], 16) / 255
        self.sub_bg_color.blue = int(bg_hex[6:8], 16) / 255

        self.sub_bg_color_btn.set_dialog(
            Gtk.ColorDialog(title=_("Subtitle Background"), modal=True, with_alpha=True)
        )
        self.sub_bg_color_btn.set_rgba(self.sub_bg_color)

        self.connect("closed", self._disconnect_settings)

    def _bind_ui(self):
        settings.bind(
            "open-new-windows",
            self.open_new_row,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "subtitle-scale",
            self.subtitle_scale_row,
            "value",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "subtitle-bg",
            self.subtitle_bg_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "subtitle-languages",
            self.subtitle_lang_row,
            "text",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "audio-languages",
            self.audio_lang_row,
            "text",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "hwdec",
            self.hwdec_row,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "thumbnail-preview",
            self.thumb_preview_row,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "normalize-volume",
            self.normalize_volume_row,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "save-session",
            self.save_session_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )
        settings.bind(
            "save-video-position",
            self.save_position_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )

    def _setup_mpv_updates(self):
        handlers = {
            "subtitle-color": self._on_sub_color_changed,
            "subtitle-scale": self._on_sub_scale_changed,
            "subtitle-font": self._on_sub_font_changed,
            "subtitle-languages": self._on_slang_changed,
            "subtitle-bg-color": self._on_sub_bg_color_changed,
            "subtitle-bg": self._on_sub_bg_changed,
            "audio-languages": self._on_alang_changed,
            "thumbnail-preview": self._on_thumb_preview_changed,
            "hwdec": self._on_hwdec_changed,
            "normalize-volume": self._on_norm_volume_changed,
        }

        self._setting_ids = [
            settings.connect(f"changed::{key}", callback)
            for key, callback in handlers.items()
        ]

    def _disconnect_settings(self, *a):
        for connection_id in self._setting_ids:
            settings.disconnect(connection_id)

    def _on_sub_color_changed(self, settings, key):
        self.player["sub-color"] = settings.get_string(key)

    def _on_sub_bg_color_changed(self, _settings, key):
        if settings.get_boolean("subtitle-bg"):
            self.player["sub-back-color"] = settings.get_string(key)

    def _on_sub_scale_changed(self, settings, key):
        self.player["sub-scale"] = settings.get_double(key)

    def _on_sub_font_changed(self, settings, key):
        self.player["sub-font"] = settings.get_string(key)

    def _on_sub_bg_changed(self, settings, key):
        sub_bg = settings.get_boolean(key)
        if sub_bg:
            self.player["sub-shadow-offset"] = 8
            self.player["sub-border-style"] = "background-box"
            self.player["sub-back-color"] = settings.get_string("subtitle-bg-color")
        else:
            self.player["sub-shadow-offset"] = 0.6
            self.player["sub-border-style"] = "outline-and-shadow"
            self.player["sub-shadow-color"] = "#97000000"

    def _on_slang_changed(self, settings, key):
        self.player["slang"] = settings.get_string(key)

    def _on_alang_changed(self, settings, key):
        self.player["alang"] = settings.get_string(key)

    def _on_thumb_preview_changed(self, settings, key):
        if not settings.get_boolean(key) and self.win.preview_player:
            self.win.preview_player.terminate()
            self.win.preview_player = None
            self.win.thumb_preview.props.visible = False
        elif not self.player.idle_active:
            self.win.thumb_preview.props.visible = True
            self.win.setup_preview_player()

    def _on_hwdec_changed(self, settings, key):
        hwdec_enabled = settings.get_boolean(key)
        if hwdec_enabled:
            self.player.command_async("vf", "remove", "@hflip")
            self.player.command_async("vf", "remove", "@vflip")
            self.player["hwdec"] = self.win.conf_hwdec + ["auto"]
        else:
            self.player["hwdec"] = "no"

    def _on_norm_volume_changed(self, settings, key):
        norm_enabled = settings.get_boolean(key)
        if norm_enabled:
            self.player.command("af", "add", "@cine_loudnorm:lavfi=[loudnorm=I=-20]")
        else:
            self.player.command("af", "remove", "@cine_loudnorm")

    def _on_sub_color_selected(self, color_btn, *arg):
        rgba = color_btn.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
        )
        settings.set_string("subtitle-color", hex_color)

    def _on_sub_bg_color_selected(self, color_btn, *arg):
        rgba = color_btn.get_rgba()
        # sub-back-color is #AARRGGBB
        hex_color = "#{:02x}{:02x}{:02x}{:02x}".format(
            int(rgba.alpha * 255),
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        settings.set_string("subtitle-bg-color", hex_color)

    def _on_sub_color_reset(self, _button):
        default_color = "#ebebeb"
        self.sub_color.parse(default_color)
        self.sub_color_btn.set_rgba(self.sub_color)

    def _on_font_activated(self, _row):
        dialog = Gtk.FontDialog()

        def callback(dialog, result):
            try:
                face = dialog.choose_face_finish(result)

                family_obj = face.get_family()
                family_name = family_obj.get_name()
                style_name = face.get_face_name()

                ignored_styles = [
                    "Regular",
                    "Normal",
                    "Roman",
                    "Book",
                    "Standard",
                    "Plain",
                    "Text",
                    "Semi",
                    "Semi-Bold",
                    "Demi",
                    "Demi-Bold",
                    "Upright",
                    "Alt",
                ]

                if any(s == style_name for s in ignored_styles):
                    font_full = family_name
                else:
                    # prevents "Font Bold Bold"
                    if style_name.lower() in family_name.lower():
                        font_full = family_name
                    else:
                        font_full = f"{family_name} {style_name}"

                font_full = " ".join(font_full.split())

                settings.set_string("subtitle-font", font_full)
                self.font_label.set_label(font_full)

            except Exception as e:
                print(f"Features selection error: {e}")

        dialog.choose_face(self.win, None, None, callback)

    def _on_font_reset(self, _button):
        default_font = "Adwaita Sans SemiBold"
        settings.set_string("subtitle-font", default_font)
        self.font_label.set_label(default_font)

    @Gtk.Template.Callback()
    def _on_btn_warning_map(self, button):
        button.set_visible(not has_host_permission)
