# options.py
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


import logging
import os
from typing import cast

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

logger = logging.getLogger(__name__)

RATIOS = [
    None,
    16 / 9,
    4 / 3,
    1 / 1,
    16 / 10,
    2.00,
    2.21,
    2.35,
    2.39,
    5 / 4,
]

DIR = os.path.dirname(__file__)
FLIP_H = os.path.join(DIR, "flip-h.glsl")
FLIP_V = os.path.join(DIR, "flip-v.glsl")


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/options.ui")
class OptionsMenuButton(Gtk.MenuButton):
    __gtype_name__ = "OptionsMenuButton"

    popover: Gtk.Popover = Gtk.Template.Child()
    aspect_reset_btn: Gtk.Button = Gtk.Template.Child()
    crop_reset_btn: Gtk.Button = Gtk.Template.Child()
    rotate_reset_btn: Gtk.Button = Gtk.Template.Child()
    flip_reset_btn: Gtk.Button = Gtk.Template.Child()
    zoom_reset_btn: Gtk.Button = Gtk.Template.Child()
    contrast_reset_btn: Gtk.Button = Gtk.Template.Child()
    brightness_reset_btn: Gtk.Button = Gtk.Template.Child()
    gamma_reset_btn: Gtk.Button = Gtk.Template.Child()
    saturation_reset_btn: Gtk.Button = Gtk.Template.Child()
    hue_reset_btn: Gtk.Button = Gtk.Template.Child()
    sub_delay_reset_btn: Gtk.Button = Gtk.Template.Child()
    audio_delay_reset_btn: Gtk.Button = Gtk.Template.Child()
    speed_reset_btn: Gtk.Button = Gtk.Template.Child()

    aspect_dropdown: Gtk.DropDown = Gtk.Template.Child()
    aspect_list: Gtk.StringList = Gtk.Template.Child()
    crop_dropdown: Gtk.DropDown = Gtk.Template.Child()
    crop_list: Gtk.StringList = Gtk.Template.Child()
    zoom_spin: Gtk.SpinButton = Gtk.Template.Child()
    contrast_spin: Gtk.SpinButton = Gtk.Template.Child()
    brightness_spin: Gtk.SpinButton = Gtk.Template.Child()
    gamma_spin: Gtk.SpinButton = Gtk.Template.Child()
    saturation_spin: Gtk.SpinButton = Gtk.Template.Child()
    hue_spin: Gtk.SpinButton = Gtk.Template.Child()
    sub_delay_spin: Gtk.SpinButton = Gtk.Template.Child()
    audio_delay_spin: Gtk.SpinButton = Gtk.Template.Child()
    speed_spin: Gtk.SpinButton = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("realize", self._on_realize)
        self.connect("notify::active", self._on_active_changed)

    def _on_realize(self, *arg):
        from .window import CineWindow

        self._win = cast(CineWindow, self.get_root())

        for spin in [
            self.zoom_spin,
            self.contrast_spin,
            self.brightness_spin,
            self.gamma_spin,
            self.saturation_spin,
            self.hue_spin,
            self.sub_delay_spin,
            self.audio_delay_spin,
            self.speed_spin,
        ]:
            spin_text = cast(Gtk.Text, spin.get_first_child())
            spin_down = cast(Gtk.Button, spin_text.get_next_sibling())
            spin_up = cast(Gtk.Button, spin_down.get_next_sibling())
            spin_text.props.xalign = 1.0
            spin_down.props.css_classes = ["button"]
            spin_up.props.css_classes = ["button"]
            spin_down.props.margin_end = 8
            spin_down.props.margin_start = 8
            spin_down.props.width_request = 50
            spin_up.props.width_request = 50

    def _set_sensitive(self, button: Gtk.Button, sensitive: bool):
        # Sometimes when clicking a reset button, motion_controls contains pointer
        # will change to True even though the cursor is not hovering
        # which will result in clicks not working and ui not hiding (likely a GTK issue).
        # Using can_target and can_focus instead of set_sensitive to fix this.
        button.set_can_target(sensitive)
        button.set_can_focus(sensitive)
        button.props.opacity = 1 if sensitive else 0.4

    def _on_active_changed(self, *arg):
        if not self.get_active():
            return

        aspect_overr = cast(float, self._win.mpv.video_aspect_override)
        target_val = aspect_overr if aspect_overr > 0 else -1
        self._set_sensitive(self.aspect_reset_btn, target_val != -1)

        aspects = self.aspect_list
        for i in range(aspects.get_n_items()):
            item_str = aspects.get_string(i)

            if not item_str:
                continue

            if i == 0:
                mapped_val = -1.0
            else:
                try:
                    num, den = map(float, item_str.split(":"))
                    mapped_val = num / den
                except Exception:
                    logger.exception("Failed to get aspect val")
                    mapped_val = -1.0

            if abs(mapped_val - target_val) < 0.001:
                if self.aspect_dropdown.get_selected() != i:
                    self.aspect_dropdown.set_selected(i)
                break

        def set_open_val(spin, reset_btn, val, default_val=0.0):
            if spin.get_value() != val:
                spin.set_value(val)
            self._set_sensitive(reset_btn, abs(val - default_val) > 0.001)

        controls = [
            ("video-zoom", self.zoom_spin, self.zoom_reset_btn, 0.0),
            ("contrast", self.contrast_spin, self.contrast_reset_btn, 0),
            ("brightness", self.brightness_spin, self.brightness_reset_btn, 0),
            ("gamma", self.gamma_spin, self.gamma_reset_btn, 0),
            ("saturation", self.saturation_spin, self.saturation_reset_btn, 0),
            ("hue", self.hue_spin, self.hue_reset_btn, 0),
            ("sub-delay", self.sub_delay_spin, self.sub_delay_reset_btn, 0.0),
            ("audio-delay", self.audio_delay_spin, self.audio_delay_reset_btn, 0.0),
            ("speed", self.speed_spin, self.speed_reset_btn, 1.0),
        ]

        for mpv_key, spin, reset_btn, default in controls:
            val = cast(float, self._win.mpv[mpv_key])
            set_open_val(spin, reset_btn, val, default_val=default)

        rotate_val = int(self._win.mpv.video_rotate or 0)
        self._set_sensitive(self.rotate_reset_btn, rotate_val != 0)

        self._set_sensitive(self.flip_reset_btn, self._has_flip())

        try:
            crop_str = cast(str, self._win.mpv.video_crop)

            if not crop_str:
                self.crop_dropdown.set_selected(0)
                self._set_sensitive(self.crop_reset_btn, False)
                return

            self._set_sensitive(self.crop_reset_btn, True)

            # Crop from cine: 1900x958
            # from autocrop: 1900x958+0+60
            parts = crop_str.split("x")
            w = int(parts[0])
            h = int(parts[1].split("+")[0])
            current_ratio = int(w) / int(h)

            for i, r in enumerate(RATIOS):
                if i > 0 and abs(current_ratio - r) < 0.01:
                    self.crop_dropdown.set_selected(i)
                    break
        except Exception:
            logger.exception("Failed to get crop")
            self.crop_dropdown.set_selected(0)
            self._set_sensitive(self.crop_reset_btn, False)

    @Gtk.Template.Callback()
    def _on_reset_all_options(self, _btn):
        self.aspect_dropdown.set_selected(0)
        self.crop_dropdown.set_selected(0)
        self._on_rotate_reset(None)
        self._on_flip_reset(None)
        self.zoom_spin.set_value(0)
        self.contrast_spin.set_value(0)
        self.brightness_spin.set_value(0)
        self.gamma_spin.set_value(0)
        self.saturation_spin.set_value(0)
        self.hue_spin.set_value(0)
        self.sub_delay_spin.set_value(0)
        self.audio_delay_spin.set_value(0)
        self.speed_spin.set_value(1.0)

    # --- ASPECT ---
    @Gtk.Template.Callback()
    def _on_aspect_changed(self, dropdown, *arg):
        idx = dropdown.get_selected()
        model = dropdown.get_model()
        item_str = model.get_string(idx)
        val = "no" if idx == 0 else item_str
        self._win.mpv.command_async("set", "video-aspect-override", val)
        self._set_sensitive(self.aspect_reset_btn, idx != 0)

    @Gtk.Template.Callback()
    def _on_aspect_reset(self, _btn):
        self.aspect_dropdown.set_selected(0)
        self._set_sensitive(self.aspect_reset_btn, False)

    # --- CROP ---
    @Gtk.Template.Callback()
    def _on_crop_reset(self, button):
        self.crop_dropdown.set_selected(0)
        self._set_sensitive(self.crop_reset_btn, False)

    @Gtk.Template.Callback()
    def _on_crop_changed(self, dropdown, *args):
        idx = dropdown.get_selected()
        self._set_sensitive(self.crop_reset_btn, idx != 0)

        if idx == 0:
            self._win.mpv.command_async("set", "video-crop", "")
            return

        w = cast(int, self._win.mpv._get_property("video-params/w"))
        h = cast(int, self._win.mpv._get_property("video-params/h"))

        target_ratio = RATIOS[idx]
        current_ratio = w / h

        if current_ratio > target_ratio:
            # wider: crop the sides
            new_w = int(h * target_ratio)
            new_h = h
        else:
            # taller: crop the top/bottom
            new_w = w
            new_h = int(w / target_ratio)

        self._win.mpv.command_async("set", "video-crop", f"{new_w}x{new_h}")

    # --- ROTATE ---
    @Gtk.Template.Callback()
    def _on_rotate_right(self, _btn):
        curr = cast(int, self._win.mpv.video_rotate or 0)
        next_rot = (curr + 90) % 360
        self._win.mpv.command_async("set", "video-rotate", next_rot)
        self._set_sensitive(self.rotate_reset_btn, next_rot != 0)

    @Gtk.Template.Callback()
    def _on_rotate_left(self, _btn):
        curr = cast(int, self._win.mpv.video_rotate or 0)
        next_rot = (curr - 90) % 360
        self._win.mpv.command_async("set", "video-rotate", next_rot)
        self._set_sensitive(self.rotate_reset_btn, next_rot != 0)

    @Gtk.Template.Callback()
    def _on_rotate_reset(self, _btn):
        self._win.mpv.command_async("set", "video-rotate", 0)
        self._set_sensitive(self.rotate_reset_btn, False)

    def _has_flip(self):
        shaders = cast(list, self._win.mpv.glsl_shaders)
        return any(s == FLIP_H or s == FLIP_V for s in shaders)

    # --- FLIP ---
    @Gtk.Template.Callback()
    def _on_flip_horiz(self, _btn):
        mpv = self._win.mpv
        mpv.command("change-list", "glsl-shaders", "toggle", FLIP_H)
        self._set_sensitive(self.flip_reset_btn, self._has_flip())

    @Gtk.Template.Callback()
    def _on_flip_vert(self, _btn):
        mpv = self._win.mpv
        mpv.command("change-list", "glsl-shaders", "toggle", FLIP_V)
        self._set_sensitive(self.flip_reset_btn, self._has_flip())

    @Gtk.Template.Callback()
    def _on_flip_reset(self, _btn):
        mpv = self._win.mpv
        mpv.command_async("change-list", "glsl-shaders", "remove", FLIP_H)
        mpv.command_async("change-list", "glsl-shaders", "remove", FLIP_V)
        self._set_sensitive(self.flip_reset_btn, False)

    # --- ZOOM ---
    @Gtk.Template.Callback()
    def _on_zoom_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv.video_zoom = val
        self._set_sensitive(self.zoom_reset_btn, val != 0.0)

    @Gtk.Template.Callback()
    def _on_zoom_reset(self, _btn):
        self.zoom_spin.set_value(0)
        self._set_sensitive(self.zoom_reset_btn, False)

    # --- CONTRAST ---
    @Gtk.Template.Callback()
    def _on_contrast_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv.contrast = val
        self._set_sensitive(self.contrast_reset_btn, val != 0)

    @Gtk.Template.Callback()
    def _on_contrast_reset(self, _btn):
        self.contrast_spin.set_value(0)
        self._set_sensitive(self.contrast_reset_btn, False)

    # --- BRIGHTNESS ---
    @Gtk.Template.Callback()
    def _on_brightness_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv.brightness = val
        self._set_sensitive(self.brightness_reset_btn, val != 0)

    @Gtk.Template.Callback()
    def _on_brightness_reset(self, _btn):
        self.brightness_spin.set_value(0)
        self._set_sensitive(self.brightness_reset_btn, False)

    # --- GAMMA ---
    @Gtk.Template.Callback()
    def _on_gamma_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv.gamma = val
        self._set_sensitive(self.gamma_reset_btn, val != 0)

    @Gtk.Template.Callback()
    def _on_gamma_reset(self, _btn):
        self.gamma_spin.set_value(0)
        self._set_sensitive(self.gamma_reset_btn, False)

    # --- SATURATION ---
    @Gtk.Template.Callback()
    def _on_saturation_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv.saturation = val
        self._set_sensitive(self.saturation_reset_btn, val != 0)

    @Gtk.Template.Callback()
    def _on_saturation_reset(self, _btn):
        self.saturation_spin.set_value(0)
        self._set_sensitive(self.saturation_reset_btn, False)

    # --- HUE ---
    @Gtk.Template.Callback()
    def _on_hue_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv.hue = val
        self._set_sensitive(self.hue_reset_btn, val != 0)

    @Gtk.Template.Callback()
    def _on_hue_reset(self, _btn):
        self.hue_spin.set_value(0)
        self._set_sensitive(self.hue_reset_btn, False)

    # --- SUBTITLE DELAY ---
    @Gtk.Template.Callback()
    def _on_sub_delay_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv.sub_delay = val
        self._set_sensitive(self.sub_delay_reset_btn, val != 0.0)

    @Gtk.Template.Callback()
    def _on_sub_delay_reset(self, _btn):
        self.sub_delay_spin.set_value(0)
        self._set_sensitive(self.sub_delay_reset_btn, False)

    # --- AUDIO DELAY ---
    @Gtk.Template.Callback()
    def _on_audio_delay_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv.audio_delay = val
        self._set_sensitive(self.audio_delay_reset_btn, val != 0.0)

    @Gtk.Template.Callback()
    def _on_audio_delay_reset(self, _btn):
        self.audio_delay_spin.set_value(0)
        self._set_sensitive(self.audio_delay_reset_btn, False)

    # --- PLAYBACK SPEED ---
    @Gtk.Template.Callback()
    def _on_speed_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv.speed = val
        self._set_sensitive(self.speed_reset_btn, abs(val - 1.0) > 0.001)

    @Gtk.Template.Callback()
    def _on_speed_reset(self, _btn):
        self.speed_spin.set_value(1.0)
        self._set_sensitive(self.speed_reset_btn, False)
