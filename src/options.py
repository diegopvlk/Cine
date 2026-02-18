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


import gi
from typing import cast
from gettext import gettext as _

from .preferences import settings

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/options.ui")
class OptionsMenuButton(Gtk.MenuButton):
    __gtype_name__ = "OptionsMenuButton"

    flip_box: Gtk.Box = Gtk.Template.Child()
    aspect_dropdown: Gtk.DropDown = Gtk.Template.Child()
    aspect_list: Gtk.StringList = Gtk.Template.Child()
    zoom_spin: Gtk.SpinButton = Gtk.Template.Child()
    contrast_spin: Gtk.SpinButton = Gtk.Template.Child()
    brightness_spin: Gtk.SpinButton = Gtk.Template.Child()
    gamma_spin: Gtk.SpinButton = Gtk.Template.Child()
    saturation_spin: Gtk.SpinButton = Gtk.Template.Child()
    hue_spin: Gtk.SpinButton = Gtk.Template.Child()
    sub_delay_spin: Gtk.SpinButton = Gtk.Template.Child()
    audio_delay_spin: Gtk.SpinButton = Gtk.Template.Child()
    speed_spin: Gtk.SpinButton = Gtk.Template.Child()
    hold_speed_spin: Gtk.SpinButton = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("realize", self._on_realize)
        self.connect("notify::active", self._on_active)

    def _on_realize(self, *arg):
        from .window import CineWindow

        self.win = cast(CineWindow, self.get_root())

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
            self.hold_speed_spin,
        ]:
            spin_text = cast(Gtk.Text, spin.get_first_child())
            spin_down = cast(Gtk.Button, spin_text.get_next_sibling())
            spin_up = cast(Gtk.Button, spin_down.get_next_sibling())
            spin_text.props.xalign = 1.0
            spin_down.props.css_classes = ["button"]
            spin_up.props.css_classes = ["button"]
            spin_down.props.margin_end = 8
            spin_down.props.margin_start = 3
            spin_down.props.width_request = 50
            spin_up.props.width_request = 50

        # This is not pretty, but for some reason is not possible to close
        # the OptionsMenuButton popover after opening aspect_dropdown
        popover_drop = self.aspect_dropdown.get_first_child().get_next_sibling()  # type: ignore
        popover_drop.set_autohide(False)  # type: ignore

    def _on_active(self, *arg):
        if not self.get_active():
            return

        hwdec_on = settings.get_boolean("hwdec")
        hwdec = str(self.win.mpv.hwdec_current)
        self.flip_box.props.visible = not (hwdec_on and "-copy" not in hwdec)

        aspect_overr = self.win.mpv["video-aspect-override"]
        target_val = (
            float(aspect_overr) if (aspect_overr and aspect_overr != -1) else -1.0
        )

        list = self.aspect_list

        for i in range(list.get_n_items()):
            item_str = cast(str, list.get_string(i))

            if i == 0:
                mapped_val = -1.0
            else:
                try:
                    num, den = map(float, item_str.split(":"))
                    mapped_val = num / den
                except:
                    mapped_val = -1.0

            if abs(mapped_val - target_val) < 0.001:
                if self.aspect_dropdown.get_selected() != i:
                    self.aspect_dropdown.set_selected(i)
                break

        def set_open_val(spin, val):
            if spin.get_value() != val:
                spin.set_value(val)

        set_open_val(self.zoom_spin, float(self.win.mpv["video-zoom"] or 0))
        set_open_val(self.contrast_spin, float(self.win.mpv["contrast"] or 0))
        set_open_val(self.brightness_spin, float(self.win.mpv["brightness"] or 0))
        set_open_val(self.gamma_spin, float(self.win.mpv["gamma"] or 0))
        set_open_val(self.saturation_spin, float(self.win.mpv["saturation"] or 0))
        set_open_val(self.hue_spin, float(self.win.mpv["hue"] or 0))
        set_open_val(self.sub_delay_spin, float(self.win.mpv["sub-delay"] or 0))
        set_open_val(self.audio_delay_spin, float(self.win.mpv["audio-delay"] or 0))
        set_open_val(self.speed_spin, float(self.win.mpv["speed"] or 1.0))
        set_open_val(self.hold_speed_spin, self.win._hold_speed_value)

    @Gtk.Template.Callback()
    def _on_reset_all_options(self, _btn):
        self.aspect_dropdown.set_selected(0)
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
        self.hold_speed_spin.set_value(2.0)

    @Gtk.Template.Callback()
    def _on_aspect_changed(self, dropdown, *arg):
        idx = dropdown.get_selected()
        model = dropdown.get_model()
        item_str = model.get_string(idx)
        val = "-1" if item_str == _("Original") else item_str
        self.win.mpv.command_async("set", "video-aspect-override", val)

    @Gtk.Template.Callback()
    def _on_aspect_reset(self, _btn):
        self.aspect_dropdown.set_selected(0)

    # --- ROTATE ---
    @Gtk.Template.Callback()
    def _on_rotate_right(self, _btn):
        curr = cast(int, self.win.mpv["video-rotate"] or 0)
        self.win.mpv.command_async("set", "video-rotate", (curr + 90) % 360)

    @Gtk.Template.Callback()
    def _on_rotate_left(self, _btn):
        curr = cast(int, self.win.mpv["video-rotate"] or 0)
        self.win.mpv.command_async("set", "video-rotate", (curr - 90) % 360)

    @Gtk.Template.Callback()
    def _on_rotate_reset(self, _btn):
        self.win.mpv.command_async("set", "video-rotate", 0)

    # --- FLIP ---
    @Gtk.Template.Callback()
    def _on_flip_horiz(self, _btn):
        self.win.mpv.command_async("vf", "toggle", "@hflip:hflip")

    @Gtk.Template.Callback()
    def _on_flip_vert(self, _btn):
        self.win.mpv.command_async("vf", "toggle", "@vflip:vflip")

    @Gtk.Template.Callback()
    def _on_flip_reset(self, _btn):
        self.win.mpv.command_async("vf", "remove", "@hflip")
        self.win.mpv.command_async("vf", "remove", "@vflip")

    # --- ZOOM ---
    @Gtk.Template.Callback()
    def _on_zoom_changed(self, spin):
        self.win.mpv["video-zoom"] = spin.get_value()

    @Gtk.Template.Callback()
    def _on_zoom_reset(self, _btn):
        self.zoom_spin.set_value(0)

    # --- CONTRAST ---
    @Gtk.Template.Callback()
    def _on_contrast_changed(self, spin):
        self.win.mpv["contrast"] = int(spin.get_value())

    @Gtk.Template.Callback()
    def _on_contrast_reset(self, _btn):
        self.contrast_spin.set_value(0)

    # --- BRIGHTNESS ---
    @Gtk.Template.Callback()
    def _on_brightness_changed(self, spin):
        self.win.mpv["brightness"] = int(spin.get_value())

    @Gtk.Template.Callback()
    def _on_brightness_reset(self, _btn):
        self.brightness_spin.set_value(0)

    # --- GAMMA ---
    @Gtk.Template.Callback()
    def _on_gamma_changed(self, spin):
        self.win.mpv["gamma"] = int(spin.get_value())

    @Gtk.Template.Callback()
    def _on_gamma_reset(self, _btn):
        self.gamma_spin.set_value(0)

    # --- SATURATION ---
    @Gtk.Template.Callback()
    def _on_saturation_changed(self, spin):
        self.win.mpv["saturation"] = int(spin.get_value())

    @Gtk.Template.Callback()
    def _on_saturation_reset(self, _btn):
        self.saturation_spin.set_value(0)

    # --- HUE ---
    @Gtk.Template.Callback()
    def _on_hue_changed(self, spin):
        self.win.mpv["hue"] = int(spin.get_value())

    @Gtk.Template.Callback()
    def _on_hue_reset(self, _btn):
        self.hue_spin.set_value(0)

    # --- SUBTITLE DELAY ---
    @Gtk.Template.Callback()
    def _on_sub_delay_changed(self, spin):
        self.win.mpv["sub-delay"] = spin.get_value()

    @Gtk.Template.Callback()
    def _on_sub_delay_reset(self, _btn):
        self.sub_delay_spin.set_value(0)

    # --- AUDIO DELAY ---
    @Gtk.Template.Callback()
    def _on_audio_delay_changed(self, spin):
        self.win.mpv["audio-delay"] = spin.get_value()

    @Gtk.Template.Callback()
    def _on_audio_delay_reset(self, _btn):
        self.audio_delay_spin.set_value(0)

    # --- PLAYBACK SPEED ---
    @Gtk.Template.Callback()
    def _on_speed_changed(self, spin):
        self.win.mpv["speed"] = spin.get_value()

    @Gtk.Template.Callback()
    def _on_speed_reset(self, _btn):
        self.speed_spin.set_value(1.0)

    # --- HOLD SPEED ---
    @Gtk.Template.Callback()
    def _on_hold_speed_changed(self, spin):
        val = spin.get_value()
        self.win._hold_speed_value = val
        settings.set_double("hold-speed", val)

    @Gtk.Template.Callback()
    def _on_hold_speed_reset(self, _btn):
        self.hold_speed_spin.set_value(2.0)
