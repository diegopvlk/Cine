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
from typing import cast

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .preferences import settings

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

    flip_box: Gtk.Box = Gtk.Template.Child()
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

        # TODO: remove for gnome 51
        # GTK bug: not possible to close popover after opening dropdown
        self.popv_motion = Gtk.EventControllerMotion()
        for btn_num in range(1, 4):
            gesture_click = Gtk.GestureClick(button=btn_num)
            gesture_click.connect("pressed", self._popdown)
            self.popover.add_controller(gesture_click)
        self.popover.add_controller(self.popv_motion)

    def _popdown(self, *args):
        if not self.popv_motion.props.contains_pointer:
            self.grab_focus()
            self.popover.popdown()
            self.grab_focus()

    def _on_active_changed(self, *arg):
        if not self.get_active():
            return

        hwdec_on = settings.get_boolean("hwdec")
        hwdec = str(self._win.mpv.hwdec_current)
        self.flip_box.props.visible = not (hwdec_on and "-copy" not in hwdec)

        aspect_overr = cast(float, self._win.mpv["video-aspect-override"])
        target_val = aspect_overr if aspect_overr > 0 else -1
        self.aspect_reset_btn.set_sensitive(target_val != -1)

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
            reset_btn.set_sensitive(abs(val - default_val) > 0.001)

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

        rotate_val = int(self._win.mpv["video-rotate"] or 0)
        self.rotate_reset_btn.set_sensitive(rotate_val != 0)

        vf_list = cast(list, self._win.mpv["vf"])
        has_flip = any(f.get("name") in ("hflip", "vflip") for f in vf_list)
        self.flip_reset_btn.set_sensitive(has_flip)

        try:
            crop_str = cast(str, self._win.mpv["video-crop"])

            if not crop_str:
                self.crop_dropdown.set_selected(0)
                self.crop_reset_btn.set_sensitive(False)
                return

            self.crop_reset_btn.set_sensitive(True)

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
            self.crop_reset_btn.set_sensitive(False)

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
        self.aspect_reset_btn.set_sensitive(idx != 0)

    @Gtk.Template.Callback()
    def _on_aspect_reset(self, _btn):
        self.aspect_dropdown.set_selected(0)
        self.aspect_reset_btn.set_sensitive(False)

    # --- CROP ---
    @Gtk.Template.Callback()
    def _on_crop_reset(self, button):
        self.crop_dropdown.set_selected(0)
        self.crop_reset_btn.set_sensitive(False)

    @Gtk.Template.Callback()
    def _on_crop_changed(self, dropdown, *args):
        idx = dropdown.get_selected()
        self.crop_reset_btn.set_sensitive(idx != 0)

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
        curr = cast(int, self._win.mpv["video-rotate"] or 0)
        next_rot = (curr + 90) % 360
        self._win.mpv.command_async("set", "video-rotate", next_rot)
        self.rotate_reset_btn.set_sensitive(next_rot != 0)

    @Gtk.Template.Callback()
    def _on_rotate_left(self, _btn):
        curr = cast(int, self._win.mpv["video-rotate"] or 0)
        next_rot = (curr - 90) % 360
        self._win.mpv.command_async("set", "video-rotate", next_rot)
        self.rotate_reset_btn.set_sensitive(next_rot != 0)

    @Gtk.Template.Callback()
    def _on_rotate_reset(self, _btn):
        self._win.mpv.command_async("set", "video-rotate", 0)
        self.rotate_reset_btn.set_sensitive(False)

    # --- FLIP ---
    @Gtk.Template.Callback()
    def _on_flip_horiz(self, _btn):
        self._win.mpv.command("vf", "toggle", "@hflip:hflip")
        vf_list = cast(list, self._win.mpv["vf"])
        has_flip = any(f.get("name") in ("hflip", "vflip") for f in vf_list)
        self.flip_reset_btn.set_sensitive(has_flip)

    @Gtk.Template.Callback()
    def _on_flip_vert(self, _btn):
        self._win.mpv.command("vf", "toggle", "@vflip:vflip")
        vf_list = cast(list, self._win.mpv["vf"])
        has_flip = any(f.get("name") in ("hflip", "vflip") for f in vf_list)
        self.flip_reset_btn.set_sensitive(has_flip)

    @Gtk.Template.Callback()
    def _on_flip_reset(self, _btn):
        self._win.mpv.command_async("vf", "remove", "@hflip")
        self._win.mpv.command_async("vf", "remove", "@vflip")
        self.flip_reset_btn.set_sensitive(False)

    # --- ZOOM ---
    @Gtk.Template.Callback()
    def _on_zoom_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv["video-zoom"] = val
        self.zoom_reset_btn.set_sensitive(val != 0.0)

    @Gtk.Template.Callback()
    def _on_zoom_reset(self, _btn):
        self.zoom_spin.set_value(0)
        self.zoom_reset_btn.set_sensitive(False)

    # --- CONTRAST ---
    @Gtk.Template.Callback()
    def _on_contrast_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv["contrast"] = val
        self.contrast_reset_btn.set_sensitive(val != 0)

    @Gtk.Template.Callback()
    def _on_contrast_reset(self, _btn):
        self.contrast_spin.set_value(0)
        self.contrast_reset_btn.set_sensitive(False)

    # --- BRIGHTNESS ---
    @Gtk.Template.Callback()
    def _on_brightness_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv["brightness"] = val
        self.brightness_reset_btn.set_sensitive(val != 0)

    @Gtk.Template.Callback()
    def _on_brightness_reset(self, _btn):
        self.brightness_spin.set_value(0)
        self.brightness_reset_btn.set_sensitive(False)

    # --- GAMMA ---
    @Gtk.Template.Callback()
    def _on_gamma_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv["gamma"] = val
        self.gamma_reset_btn.set_sensitive(val != 0)

    @Gtk.Template.Callback()
    def _on_gamma_reset(self, _btn):
        self.gamma_spin.set_value(0)
        self.gamma_reset_btn.set_sensitive(False)

    # --- SATURATION ---
    @Gtk.Template.Callback()
    def _on_saturation_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv["saturation"] = val
        self.saturation_reset_btn.set_sensitive(val != 0)

    @Gtk.Template.Callback()
    def _on_saturation_reset(self, _btn):
        self.saturation_spin.set_value(0)
        self.saturation_reset_btn.set_sensitive(False)

    # --- HUE ---
    @Gtk.Template.Callback()
    def _on_hue_changed(self, spin):
        val = int(spin.get_value())
        self._win.mpv["hue"] = val
        self.hue_reset_btn.set_sensitive(val != 0)

    @Gtk.Template.Callback()
    def _on_hue_reset(self, _btn):
        self.hue_spin.set_value(0)
        self.hue_reset_btn.set_sensitive(False)

    # --- SUBTITLE DELAY ---
    @Gtk.Template.Callback()
    def _on_sub_delay_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv["sub-delay"] = val
        self.sub_delay_reset_btn.set_sensitive(val != 0.0)

    @Gtk.Template.Callback()
    def _on_sub_delay_reset(self, _btn):
        self.sub_delay_spin.set_value(0)
        self.sub_delay_reset_btn.set_sensitive(False)

    # --- AUDIO DELAY ---
    @Gtk.Template.Callback()
    def _on_audio_delay_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv["audio-delay"] = val
        self.audio_delay_reset_btn.set_sensitive(val != 0.0)

    @Gtk.Template.Callback()
    def _on_audio_delay_reset(self, _btn):
        self.audio_delay_spin.set_value(0)
        self.audio_delay_reset_btn.set_sensitive(False)

    # --- PLAYBACK SPEED ---
    @Gtk.Template.Callback()
    def _on_speed_changed(self, spin):
        val = round(spin.get_value(), 4)
        self._win.mpv["speed"] = val
        self.speed_reset_btn.set_sensitive(abs(val - 1.0) > 0.001)

    @Gtk.Template.Callback()
    def _on_speed_reset(self, _btn):
        self.speed_spin.set_value(1.0)
        self.speed_reset_btn.set_sensitive(False)
