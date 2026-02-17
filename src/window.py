# window.py
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

import os
import gi
import mpv
import ctypes
from typing import cast
from gettext import gettext as _

from .utils import (
    get_gpu_vendor,
    format_time,
    MBTN_MAP,
    KEY_REMAP,
    SUB_EXTS,
    SCREENSHOT_DIR,
    CONFIG_DIR,
    INPUT_CONF,
)

DEFAULT_WIDTH, DEFAULT_HEIGHT = 1088, 612

from .options import OptionsMenuButton
from .playlist import Playlist
from .preferences import settings, sync_mpv_with_settings
from .shortcuts import INTERNAL_BINDINGS, populate_shortcuts_dialog_mpv

gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkWayland", "4.0")
gi.require_version("GdkX11", "4.0")
from gi.repository import Adw, Gio, Gdk, GLib, Gtk
from gi.repository import (
    GdkWayland,  # pyright: ignore[reportAttributeAccessIssue]
    GdkX11,
)

libegl = ctypes.CDLL("libEGL.so.1")
egl_get_proc_address = libegl.eglGetProcAddress
egl_get_proc_address.restype = ctypes.c_void_p
egl_get_proc_address.argtypes = [ctypes.c_char_p]

GL_FRAMEBUFFER_BINDING = 0x8CA6
libgl = ctypes.CDLL("libGL.so.1")
glGetIntegerv = libgl.glGetIntegerv
glGetIntegerv.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]

gtk = ctypes.CDLL("libgtk-4.so.1")
display = Gdk.Display.get_default()


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/window.ui")
class CineWindow(Adw.ApplicationWindow):
    __gtype_name__ = "CineWindow"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    video_overlay: Gtk.Overlay = Gtk.Template.Child()
    start_page: Adw.StatusPage = Gtk.Template.Child()
    revealer_pause_indicator: Gtk.Revealer = Gtk.Template.Child()
    pause_indicator: Gtk.Image = Gtk.Template.Child()
    headerbar: Adw.HeaderBar = Gtk.Template.Child()
    controls_box: Gtk.Box = Gtk.Template.Child()
    controls_separator: Gtk.Separator = Gtk.Template.Child()
    revealer_ui: Gtk.Revealer = Gtk.Template.Child()
    revealer_drop_indicator: Gtk.Revealer = Gtk.Template.Child()
    drop_label: Gtk.Label = Gtk.Template.Child()
    drop_icon: Gtk.Image = Gtk.Template.Child()
    spinner: Adw.Spinner = Gtk.Template.Child()

    open_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    primary_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    previous_button: Gtk.Button = Gtk.Template.Child()
    play_pause_button: Gtk.Button = Gtk.Template.Child()
    next_button: Gtk.Button = Gtk.Template.Child()
    volume_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    mute_toggle_button: Gtk.ToggleButton = Gtk.Template.Child()
    volume_scale: Gtk.Scale = Gtk.Template.Child()
    volume_scale_adjustment: Gtk.Adjustment = Gtk.Template.Child()
    subtitles_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    subtitles_menu: Gio.Menu = Gtk.Template.Child()
    audio_tracks_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    audio_tracks_menu: Gio.Menu = Gtk.Template.Child()
    video_tracks_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    video_tracks_menu: Gio.Menu = Gtk.Template.Child()
    options_menu_button: OptionsMenuButton = Gtk.Template.Child()
    playlist_shuffle_toggle_button: Gtk.ToggleButton = Gtk.Template.Child()
    playlist_loop_toggle_button: Gtk.ToggleButton = Gtk.Template.Child()
    loop_file_toggle_button: Gtk.ToggleButton = Gtk.Template.Child()
    fullscreen_button: Gtk.Button = Gtk.Template.Child()
    time_elapsed_label: Gtk.Label = Gtk.Template.Child()
    vid_progress_scale_box: Gtk.Box = Gtk.Template.Child()
    video_progress_scale: Gtk.Scale = Gtk.Template.Child()
    video_progress_adjustment: Gtk.Adjustment = Gtk.Template.Child()
    time_total_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app: Gtk.Application = cast(Gtk.Application, kwargs.get("application"))

        Gtk.WindowGroup().add_window(self)

        self.gl_area: Gtk.GLArea = Gtk.GLArea()
        self.offload: Gtk.GraphicsOffload = Gtk.GraphicsOffload(child=self.gl_area)
        self.offload.set_black_background(True)

        vendor: str | None = get_gpu_vendor(display, libgl)
        if vendor and "nvidia" in vendor:
            self.offload.set_enabled(Gtk.GraphicsOffloadEnabled.DISABLED)

        self.video_overlay.set_child(self.offload)

        self.can_go_prev: bool = False
        self.can_go_next: bool = False
        self.current_chapters: list = []
        self.actions: dict[str, Gio.SimpleAction] = {}
        self.prev_motion_xy: tuple = (0, 0)
        self.prev_prog_motion_xy: tuple = (0, 0)
        self.volume_update_timer_id: int = 0
        self.inhibit_id: int = 0
        self.last_seek_scroll_time: float = 0
        self.loaded_path: str
        self.startup: bool = True
        self.click_hold_id: int = 0
        self.click_holding = False
        self.prev_speed: float = 1.0

        self.mpv_ctx: mpv.MpvRenderContext

        self.mpv = mpv.MPV(
            # terminal=True,
            # log_handler=print,
            loglevel="info",
            audio_client_name=_("Cine"),
            screenshot_directory=SCREENSHOT_DIR,
            screenshot_template="cine_%n",
            config=True,
            config_dir=CONFIG_DIR,
            input_default_bindings=False,
            input_vo_keyboard=True,
            load_scripts=True,
            audio_display="embedded-first",
            audio_file_auto="fuzzy",
            sub_auto="fuzzy",
            sub_file_paths="sub:subs:subtitles:Sub:Subs:Subtitles:srt:srts:Srt:Srts",
            sub_border_size=2,
            sub_shadow_offset=0.6,
            sub_border_color="#B6000000",
            sub_shadow_color="#97000000",
            sub_color="#ebebeb",
            sub_use_margins=False,
            sub_font="Adwaita Sans SemiBold",
            osd_font="Adwaita Sans",
            osd_bold=True,
            osd_bar=False,
            osd_blur=1,
            osd_border_size=1.5,
            osd_shadow_offset=0.6,
            osd_border_color="#BE000000",
            osd_shadow_color="#1B000000",
            osd_margin_x=66,
            osd_margin_y=66,
            volume_max=150,
            keep_open=True,
            keep_open_pause=False,
        )

        self.conf_hwdec = list(
            filter(lambda x: x != "no", cast(list, self.mpv["hwdec"]))
        )
        self.mpv["vo"] = "libmpv"
        self.mpv["osc"] = "no"
        self.mpv["load-console"] = "no"
        self.mpv.command("change-list", "watch-later-options", "remove", "vid")
        self.mpv.command("change-list", "watch-later-options", "remove", "aid")

        self._setup_actions()
        self._setup_elements()
        self._setup_event_handlers()
        self._setup_observers()

        self.mpv.command("load-input-conf", f"memory://{INTERNAL_BINDINGS}")

        if os.path.exists(INPUT_CONF):
            self.mpv.command("load-input-conf", INPUT_CONF)

        sync_mpv_with_settings(self)

    def _setup_actions(self):
        self._create_action("clear-and-add", self._on_clear_and_add)
        self._create_action_stateful("select-subtitle", self._on_subtitle_selected, "i")
        self._create_action_stateful("select-audio", self._on_audio_selected, "i")
        self._create_action_stateful("select-video", self._on_video_selected, "i")
        self._create_action("add-sub-tracks", self._on_add_sub_dialog)
        self._create_action("add-audio-tracks", self._on_add_audio_dialog)
        self._create_action("add-playlist-files", self._on_add_playlist_dialog)
        self._create_action("open-folder", self._on_open_folder_dialog)
        self._create_action("add-playlist-folder", self._on_open_folder_dialog)
        self._create_action("open-playlist-dialog", self._on_open_playlist)
        self._create_action("open-sub-menu", self._on_open_sub_menu)
        self._create_action("open-audio-menu", self._on_open_audio_menu)
        self.app.set_accels_for_action("win.open-folder", ["<primary>i"])
        self.app.set_accels_for_action("win.add-playlist-folder", ["<shift><primary>i"])
        self.app.set_accels_for_action("win.open-playlist-dialog", ["<primary>p"])
        self.app.set_accels_for_action("win.clear-and-add", ["<primary>o"])
        self.app.set_accels_for_action("win.add-playlist-files", ["<shift><primary>o"])
        self.app.set_accels_for_action("win.open-sub-menu", ["<primary>s"])
        self.app.set_accels_for_action("win.open-audio-menu", ["<primary>a"])

        self._create_action("quit", lambda *a: self.close())
        self.app.set_accels_for_action("win.quit", ["q", "<primary>w"])

        self._create_action("custom-shortcuts", self._present_shortcuts)
        self.app.set_accels_for_action("win.custom-shortcuts", ["<primary>question"])
        self.app.set_accels_for_action("app.shortcuts", [])

    def _present_shortcuts(self, *a):
        builder = Gtk.Builder.new_from_resource(
            "/io/github/diegopvlk/Cine/shortcuts-dialog.ui"
        )
        self.shortcuts_dialog = cast(
            Adw.ShortcutsDialog,  # pyright: ignore[reportAttributeAccessIssue]
            builder.get_object("shortcuts_dialog"),
        )
        self.bindings = self.mpv._get_property("input-bindings")
        populate_shortcuts_dialog_mpv(self.shortcuts_dialog, self.bindings)
        self.shortcuts_dialog.present(self)
        self.set_cursor_from_name(None)

    def _setup_elements(self):
        self.set_default_size(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.set_title(_("Cine"))
        max_vol = cast(int, self.mpv.volume_max)
        self.volume_scale_adjustment.set_upper(max_vol)

        self.play_pause_button.connect("clicked", self._on_play_pause_clicked)
        self.previous_button.connect("clicked", self._on_previous_clicked)
        self.next_button.connect("clicked", self._on_next_clicked)
        self.mute_toggle_button.connect("toggled", self._on_mute_toggled)
        self.playlist_shuffle_toggle_button.connect("toggled", self._on_shuffle_toggled)
        self.playlist_loop_toggle_button.connect(
            "toggled", self._on_loop_playlist_toggled
        )
        self.loop_file_toggle_button.connect("toggled", self._on_loop_file_toggled)

        self.fullscreen_button.connect(
            "clicked",
            lambda _btn: setattr(self.mpv, "fullscreen", not self.is_fullscreen),
        )

        self.volume_handler_id = self.volume_scale.connect(
            "value-changed",
            lambda _scale: setattr(
                self.mpv, "volume", self.volume_scale_adjustment.props.value
            ),
        )
        if max_vol > 100:
            self.volume_scale.add_mark(100.0, Gtk.PositionType.BOTTOM, None)

        self.video_progress_adjustment.connect(
            "value-changed", self._on_progress_adjusted
        )

        self.chapter_popover = Gtk.Popover()
        self.chapter_popover.set_position(Gtk.PositionType.TOP)
        # video_progress_scale can be different heights because of marks, use a box instead
        self.chapter_popover.set_parent(self.vid_progress_scale_box)
        self.chapter_popover.set_autohide(False)

        self.chapter_popover_label = Gtk.Label()
        self.chapter_popover_label.set_use_markup(True)
        self.chapter_popover_label.set_justify(Gtk.Justification.CENTER)
        self.chapter_popover_label.set_xalign(0.5)
        self.chapter_popover_label.add_css_class("numeric")
        self.chapter_popover.set_child(self.chapter_popover_label)

        self.gl_area.connect("realize", self._on_realize_area)
        self.gl_area.connect("render", self._on_render_area)

    def _setup_event_handlers(self):
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.add_controller(key_controller)

        progress_hover = Gtk.EventControllerMotion()
        progress_hover.connect("motion", self._on_progress_motion)
        progress_hover.connect("leave", lambda _ctrl: self.chapter_popover.popdown())
        self.video_progress_scale.add_controller(progress_hover)

        scroll_controller_progress = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_controller_progress.connect("scroll", self._on_progress_scroll)
        self.video_progress_scale.add_controller(scroll_controller_progress)

        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(0)
        click_gesture.connect("pressed", self._on_click_pressed)
        click_gesture.connect("released", self._on_click_released)
        click_gesture.connect("cancel", self._cancel_click_hold)
        self.video_overlay.add_controller(click_gesture)

        self.connect("notify::visible-dialog", self._cancel_click_hold)

        scroll_controller_overlay = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES
        )
        scroll_controller_vol = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        self.video_overlay.add_controller(scroll_controller_overlay)
        scroll_controller_overlay.connect("scroll", self._on_mouse_scroll)
        self.volume_scale.add_controller(scroll_controller_vol)
        scroll_controller_vol.connect("scroll", self._on_mouse_scroll_volume)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("enter", self._on_drop_enter)
        drop_target.connect("leave", self._on_drop_leave)
        drop_target.connect("drop", self._on_drop)
        self.video_overlay.add_controller(drop_target)

        self.motion_header_controls = Gtk.EventControllerMotion()
        self.motion_header_controls.connect("motion", self._on_mouse_motion)
        self.revealer_ui.add_controller(self.motion_header_controls)

        self.motion_header = Gtk.EventControllerMotion()
        self.motion_controls = Gtk.EventControllerMotion()
        self.headerbar.add_controller(self.motion_header)
        self.controls_box.add_controller(self.motion_controls)

        self.motion_controls_separator = Gtk.EventControllerMotion()
        self.controls_separator.add_controller(self.motion_controls_separator)

        # Sometimes when opening dialogs from menu items,
        # contains_pointer from these still returns True, even if not hovering
        # this seems to fix it
        self.motion_header.set_propagation_limit(Gtk.PropagationLimit.NONE)
        self.motion_controls.set_propagation_limit(Gtk.PropagationLimit.NONE)

        self.connect("realize", self._on_realize)

        buttons = [
            self.primary_menu_button,
            self.open_menu_button,
            self.options_menu_button,
            self.volume_menu_button,
            self.subtitles_menu_button,
            self.audio_tracks_menu_button,
        ]
        for btn in buttons:
            if btn.props.popover:
                btn.props.popover.connect("closed", self._hide_ui_timeout)

    def _on_realize(self, _window):
        surface: Gdk.Surface | None = self.get_surface()

        if isinstance(surface, Gdk.Toplevel):
            # When dragging the window while in fullscreen
            # fullscreened signal is not triggered, so use this:
            surface.connect("notify::state", self._set_fs_state)

    def _set_fs_state(self, top_level, _pspec):
        state: Gdk.ToplevelState = top_level.get_state()
        is_fullscreen = bool(state & Gdk.ToplevelState.FULLSCREEN)
        settings: Gtk.Settings | None = Gtk.Settings.get_default()

        try:
            self.mpv.fullscreen = is_fullscreen
        except:
            pass

        if settings:
            layout = settings.get_property("gtk-decoration-layout")

            if is_fullscreen:
                left_side, _, right_side = layout.partition(":")
                close_only = "close:" if "close" in left_side else ":close"
                self.headerbar.set_decoration_layout(close_only)
            else:
                self.headerbar.set_decoration_layout(layout)

        self._hide_ui_timeout()

    def _show_ui(self):
        self.set_cursor_from_name(None)
        self.revealer_ui.set_reveal_child(True)

    def _hide_ui_timeout(self, *args, s=2):
        if hasattr(self, "_hide_timeout_id") and self._hide_timeout_id:
            GLib.source_remove(self._hide_timeout_id)
        self._hide_timeout_id = GLib.timeout_add_seconds(s, self._hide_ui)

    def _hide_ui(self, *args):
        try:
            if self.mpv:
                self._hide_timeout_id = None
                controls_hover = self.motion_controls.props.contains_pointer
                header_hover = self.motion_header.props.contains_pointer

                active_or_hover = (
                    self.mpv.idle_active
                    or header_hover
                    or controls_hover
                    or self.primary_menu_button.props.active
                    or self.open_menu_button.props.active
                    or self.options_menu_button.props.active
                    or self.volume_menu_button.props.active
                    or self.subtitles_menu_button.props.active
                    or self.audio_tracks_menu_button.props.active
                    or self.video_tracks_menu_button.props.active
                )
                if not active_or_hover:
                    self.revealer_ui.set_reveal_child(False)
                    self.chapter_popover.popdown()

                if (
                    self.is_fullscreen
                    and not active_or_hover
                    and not self.props.dialogs
                ):
                    self.set_cursor_from_name("none")
        except mpv.ShutdownError:
            return

    def _on_mouse_motion(self, _controller, x, y):
        if None not in (x, y):
            if (x, y) == self.prev_motion_xy or self.click_holding:
                return

            self.prev_motion_xy = (x, y)
            self._show_ui()

            self._hide_ui_timeout()

    def _update_track_menus(self, track_list):
        self.subtitles_menu.remove_all()
        self.subtitles_menu.append(_("Add Subtitle Track"), "win.add-sub-tracks")

        item_none_sub = Gio.MenuItem.new(_("None"), None)
        item_none_sub.set_action_and_target_value(
            "win.select-subtitle", GLib.Variant("i", 0)
        )
        self.subtitles_menu.append_item(item_none_sub)

        self.audio_tracks_menu.remove_all()
        self.audio_tracks_menu.append(_("Add Audio Track"), "win.add-audio-tracks")

        item_none_audio = Gio.MenuItem.new(_("None"), None)
        item_none_audio.set_action_and_target_value(
            "win.select-audio", GLib.Variant("i", 0)
        )
        self.audio_tracks_menu.append_item(item_none_audio)

        self.video_tracks_menu.remove_all()

        for track in track_list:
            if track["type"] in ("sub", "audio", "video"):
                self._add_track_to_menu(track)

        video_count = len(
            [t for t in track_list if t["type"] == "video" and not t.get("albumart")]
        )
        self.video_tracks_menu_button.set_visible(video_count > 1)

        def hide_box_first_modelbutton(menu_button):
            """Hide the space before add track label"""
            target = menu_button.get_popover()
            for _ in range(8):
                if target:
                    target = target.get_first_child()
            if target:
                target.set_visible(False)

        hide_box_first_modelbutton(self.subtitles_menu_button)
        hide_box_first_modelbutton(self.audio_tracks_menu_button)

    def _add_track_to_menu(self, track):
        track_id = int(track.get("id", 0))
        track_type = track.get("type")
        lang = track.get("lang")
        title = track.get("title")

        label_parts = [p for p in (title, lang) if p]
        label = (
            " – ".join(label_parts) if label_parts else (_("Track") + f" {track_id}")
        )

        if track_type == "sub":
            menu = self.subtitles_menu
            action = "win.select-subtitle"
        elif track_type == "audio":
            menu = self.audio_tracks_menu
            action = "win.select-audio"
        else:
            menu = self.video_tracks_menu
            action = "win.select-video"

        item = Gio.MenuItem.new(label, None)
        item.set_action_and_target_value(action, GLib.Variant("i", track_id))
        menu.append_item(item)

    def _create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        self.actions[name] = action

    def _create_action_stateful(self, name, callback, target_type):
        if target_type != "i":
            raise TypeError("_create_action_stateful int only")
        action = Gio.SimpleAction.new_stateful(
            name,
            GLib.VariantType.new(target_type),
            GLib.Variant("i", 0),
        )
        action.connect("activate", callback)
        self.add_action(action)
        self.actions[name] = action

    def _on_open_playlist(self, *args):
        if self.mpv.idle_active:
            return
        playlist = Playlist(self)
        playlist.present(self)

    def _on_open_folder_dialog(self, action, *arg):
        add_mode = True if action.props.name == "add-playlist-folder" else False
        title = _("Add Folder") if add_mode else _("Open Folder")
        dialog = Gtk.FileDialog(title=title)
        curr_path = self.mpv.path

        if isinstance(curr_path, str) and os.path.exists(curr_path):
            folder_path = os.path.dirname(curr_path)
            dialog.set_initial_folder(Gio.File.new_for_path(folder_path))

        def on_open(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)

                if not add_mode:
                    self.mpv.stop()

                path = folder.get_path()
                self.mpv.loadfile(path, "append-play")
                GLib.idle_add(
                    lambda *a: self._on_shuffle_toggled(
                        self.playlist_shuffle_toggle_button
                    )
                )

            except GLib.Error as e:
                print(f"Dialog error: {e.message}")

        dialog.select_folder(self, None, on_open)

    def _on_clear_and_add(self, _action, _param):
        self._open_add_dialog(_("Open Files"), "clear-and-add")

    def _on_add_playlist_dialog(self, _action, _param):
        self._open_add_dialog(_("Add Files"), "playlist-add")

    def _on_add_sub_dialog(self, _action, _param):
        self._open_add_dialog(_("Add Subtitle"), "sub-add")

    def _on_add_audio_dialog(self, _action, _param):
        self._open_add_dialog(_("Add Audio"), "audio-add")

    def _open_add_dialog(self, title, mode, from_playlist=False):
        filter = Gtk.FileFilter()
        dialog = Gtk.FileDialog(title=title)
        dialog.set_default_filter(filter)

        curr_path = self.mpv.path
        if isinstance(curr_path, str) and os.path.exists(curr_path):
            folder_path = os.path.dirname(curr_path)
            dialog.set_initial_folder(Gio.File.new_for_path(folder_path))

        if mode == "sub-add":
            filter.set_name(_("Subtitle"))
            for sub in SUB_EXTS:
                s = sub.lstrip(".")
                filter.add_suffix(s)
        elif mode == "audio-add":
            filter.set_name(_("Audio"))
            for m in ["video/*", "audio/*"]:
                filter.add_mime_type(m)
        else:
            filter.set_name(_("Media"))
            for m in ["video/*", "audio/*", "image/*"]:
                filter.add_mime_type(m)

        dialog.open_multiple(
            self,
            None,
            lambda d, res: self._on_open_response(d, res, mode, from_playlist),
        )
        if from_playlist:
            playlist_dialog = cast(Playlist, self.get_visible_dialog())
            playlist_dialog.spinner.set_visible(True)

    def _on_open_response(self, dialog, result, mode, from_playlist=False):
        try:
            files = dialog.open_multiple_finish(result)

            if mode == "clear-and-add":
                self.mpv.stop()

            for file in files:
                path = file.get_path() or file.get_uri()

                if mode == "sub-add":
                    self.mpv.sub_add(path)
                elif mode == "audio-add":
                    self.mpv.audio_add(path)
                else:
                    self.mpv.loadfile(path, "append-play")

            if mode == "clear-and-add":
                self.mpv.pause = False

            if from_playlist:
                playlist_dialog = cast(Playlist, self.get_visible_dialog())
                playlist_dialog._populate_list()
                playlist_dialog.spinner.set_visible(False)

            GLib.idle_add(
                lambda *a: self._on_shuffle_toggled(self.playlist_shuffle_toggle_button)
            )

        except GLib.Error as e:
            if from_playlist:
                playlist_dialog = cast(Playlist, self.get_visible_dialog())
                playlist_dialog._populate_list()
                playlist_dialog.spinner.set_visible(False)
            print(f"Dialog error: {e.message}")

    def _on_open_sub_menu(self, *args):
        self._show_ui()
        self.subtitles_menu_button.popup()

    def _on_open_audio_menu(self, *args):
        self._show_ui()
        self.audio_tracks_menu_button.popup()

    def _on_mute_toggled(self, button):
        is_muted = button.props.active
        self.mpv.mute = is_muted

    def _on_progress_motion(self, _controller, x, y):
        if (x, y) == self.prev_prog_motion_xy:
            return
        self.prev_prog_motion_xy = (x, y)

        width = self.video_progress_scale.get_width()
        duration = self.video_progress_adjustment.props.upper
        if width <= 0 or duration <= 0:
            return

        percentage = max(0, min(1, x / width))
        hover_time = percentage * duration
        target_chapter = None
        if self.current_chapters:
            for chapter in self.current_chapters:
                if chapter.get("time", 0) <= hover_time:
                    target_chapter = chapter
                else:
                    break

        time_str = format_time(hover_time)
        if target_chapter:
            title = target_chapter.get("title") or "Chapter"
            escaped_title = GLib.markup_escape_text(title)
            markup = f"<b>{escaped_title}</b>\n{time_str}"
        else:
            markup = f"{time_str}"

        self.chapter_popover_label.set_markup(markup)

        clamped_x = max(2, min(x, width - 2))

        rect = Gdk.Rectangle()
        rect.x = clamped_x
        rect.y = 2
        rect.width = 41

        self.chapter_popover.set_pointing_to(rect)
        self.chapter_popover.popup()

    def _on_progress_scroll(self, controller, _dx, dy):
        event: Gdk.ScrollEvent = controller.get_current_event()
        direction: Gdk.ScrollDirection = event.get_direction()
        rel_dir: Gdk.ScrollRelativeDirection = event.get_relative_direction(event)  # type: ignore
        is_natural: bool = rel_dir == Gdk.ScrollRelativeDirection.INVERTED  # type: ignore
        step = dy if direction == Gdk.ScrollDirection.SMOOTH else dy * 10

        if is_natural:
            step = -step

        adj = self.video_progress_scale.get_adjustment()
        progress = adj.get_value()
        new_progress = progress - step
        adj.set_value(new_progress)

        return True

    def _update_volume_icon(self, is_muted):
        volume = cast(int, self.mpv.volume)
        if is_muted or volume == 0:
            icon = "cine-volume-mute-symbolic"
        elif volume < 33:
            icon = "cine-volume-low-symbolic"
        elif volume < 66:
            icon = "cine-volume-mid-symbolic"
        elif volume <= 100:
            icon = "cine-volume-max-symbolic"
        else:
            icon = "cine-volume-overamp-symbolic"
        self.volume_menu_button.set_icon_name(icon)

    @Gtk.Template.Callback()
    def _toggle_elapsed_remaining(self, _btn):
        settings.set_boolean(
            "show-remaining", not settings.get_boolean("show-remaining")
        )
        pos = float(self.mpv.time_pos or 0)
        self._update_progress(pos, update_bar=False)

    def _update_progress(self, current_time, update_bar=True):
        if update_bar:
            self.video_progress_adjustment.handler_block_by_func(
                self._on_progress_adjusted
            )
            self.video_progress_adjustment.set_value(current_time)
            self.video_progress_adjustment.handler_unblock_by_func(
                self._on_progress_adjusted
            )
        try:
            if settings.get_boolean("show-remaining"):
                duration = float(self.mpv.duration or 0)
                remaining = duration - current_time
                self.time_elapsed_label.set_text(f"-{format_time(remaining)}")
                self.time_elapsed_label.props.margin_end = 3
            else:
                self.time_elapsed_label.set_text(format_time(current_time))
                self.time_elapsed_label.props.margin_end = 0
        except mpv.ShutdownError:
            pass

    def _update_chapter_marks(self, chapters):
        if not chapters:
            self.video_progress_scale.clear_marks()
            return
        for chapter in chapters:
            time_pos = chapter.get("time")
            if time_pos is not None:
                self.video_progress_scale.add_mark(
                    float(time_pos), Gtk.PositionType.TOP, None
                )

    def _on_previous_clicked(self, _):
        pos = cast(int, self.mpv.playlist_pos)
        count = cast(int, self.mpv.playlist_count)
        if pos == 0:
            self.mpv.playlist_pos = count - 1
        else:
            self.mpv.playlist_prev()

    def _on_next_clicked(self, _):
        pos = cast(int, self.mpv.playlist_pos)
        count = cast(int, self.mpv.playlist_count)
        if pos == count - 1:
            self.mpv.playlist_pos = 0
        else:
            self.mpv.playlist_next()

    def _on_subtitle_selected(self, action, parameter):
        self.mpv.command("set", "sub-visibility", "yes")
        track_id = parameter.get_int32()
        self.mpv.sid = track_id if track_id > 0 else "no"
        action.set_state(parameter)

    def _on_audio_selected(self, action, parameter):
        track_id = parameter.get_int32()
        self.mpv.aid = track_id
        action.set_state(parameter)

    def _on_video_selected(self, action, parameter):
        track_id = parameter.get_int32()
        self.mpv.vid = track_id
        action.set_state(parameter)

    def _update_play_pause_icon(self, is_paused):
        play_icon = "cine-playback-start-symbolic"
        pause_icon = "cine-playback-pause-symbolic"

        icon = play_icon if is_paused else pause_icon
        icon_indicator = pause_icon if is_paused else play_icon

        self.play_pause_button.set_icon_name(icon)
        self.pause_indicator.props.icon_name = icon_indicator

        text = _("Pause") if is_paused else _("Play")
        self.play_pause_button.update_property([Gtk.AccessibleProperty.LABEL], [text])

        if not self.mpv.idle_active:
            self.revealer_pause_indicator.set_reveal_child(True)
            GLib.timeout_add(350, self.revealer_pause_indicator.set_reveal_child, False)

    def _update_duration(self, duration):
        self.time_total_label.set_text(format_time(duration))

        if duration == 0:
            self.video_progress_scale.set_sensitive(False)
            self.chapter_popover.popdown()
            return

        self.video_progress_scale.set_sensitive(True)

        self.video_progress_adjustment.set_upper(duration)

        if duration >= 86400:
            chars = 10
        elif duration >= 3600:
            chars = 7
        elif duration >= 600:
            chars = 6
        else:
            chars = 5

        self.time_elapsed_label.set_width_chars(chars)

    def _on_play_pause_clicked(self, _button):
        self.mpv.pause = not self.mpv.pause

    def _on_progress_adjusted(self, adjustment):
        self.mpv.time_pos = adjustment.props.value

    def _on_shuffle_toggled(self, button):
        if button.props.active:
            self.mpv.command("playlist-shuffle")
        else:
            self.mpv.command("playlist-unshuffle")

        if dialog := cast(Playlist, self.get_visible_dialog()):
            dialog._populate_list()

    def _on_loop_playlist_toggled(self, button):
        if button.props.active:
            self.mpv.loop_playlist = "inf"
            self.mpv.loop_file = "no"
            self.loop_file_toggle_button.set_active(False)
        else:
            self.mpv.loop_playlist = "no"
        self._update_playlist_nav_sensitivity()

    def _on_loop_file_toggled(self, button):
        if button.props.active:
            self.mpv.loop_file = "inf"
            self.mpv.loop_playlist = "no"
            self.playlist_loop_toggle_button.props.active = False
        else:
            self.mpv.loop_file = "no"

    def _update_playlist_nav_sensitivity(self):
        count: int = cast(int, self.mpv.playlist_count) or 0
        pos: int = cast(int, self.mpv.playlist_pos) or 0
        loop_list_enabled: bool = self.mpv.loop_playlist != False
        shuffle_enabled: bool = self.playlist_shuffle_toggle_button.props.active

        has_multiple: bool = count > 1

        self.can_always_nav: bool = has_multiple and (
            shuffle_enabled or loop_list_enabled
        )

        self.can_go_prev = self.can_always_nav or (has_multiple and pos > 0)
        self.can_go_next = self.can_always_nav or (has_multiple and pos < count - 1)

        self.previous_button.props.sensitive = self.can_go_prev
        self.next_button.props.sensitive = self.can_go_next

        self.playlist_shuffle_toggle_button.props.visible = has_multiple
        self.playlist_loop_toggle_button.props.visible = has_multiple

    def _on_drop_enter(self, target, _x, _y):
        GLib.timeout_add(10, self.revealer_drop_indicator.set_reveal_child, True)
        drop = target.get_current_drop()

        def on_read_done(source, result):
            try:
                value = source.read_value_finish(result)
                files = value.get_files()
                f_name = files[0].get_basename().lower()
                is_playing = not self.mpv.idle_active

                if is_playing and any(f_name.endswith(ext) for ext in SUB_EXTS):
                    self.drop_icon.props.icon_name = "cine-subtitles-symbolic"
                    self.drop_label.props.label = _("Add Subtitle Track")
                    return

                self.drop_icon.props.icon_name = "cine-playback-start-symbolic"
                self.drop_label.props.label = _("Play")

            except GLib.Error as e:
                print(f"File error path: {self.loaded_path}")
                toast = Adw.Toast.new(_("File Error") + f": {e.message}")
                self.toast_overlay.add_toast(toast)
                self.spinner.set_visible(False)
                return

        drop.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, on_read_done)

        return True

    def _on_drop_leave(self, _target):
        GLib.timeout_add(10, self.revealer_drop_indicator.set_reveal_child, False)
        GLib.timeout_add(100, self.drop_icon.set_from_icon_name, "")
        GLib.timeout_add(100, self.drop_label.set_text, "")

    def _on_drop(self, _target, list: Gdk.FileList, _x, _y):
        first_file = True

        for file in list.get_files():
            info = file.query_info(
                "standard::content-type,standard::type",
                Gio.FileQueryInfoFlags.NONE,
                None,
            )
            path = file.get_path() or file.get_uri()
            file_type = info.get_file_type()
            mime_type = info.get_content_type() or ""

            mode = "replace" if first_file else "append-play"

            if file_type == Gio.FileType.DIRECTORY:
                self.mpv.loadfile(path, mode)
                first_file = False
                continue

            name = cast(str, file.get_basename()).lower()
            if name.endswith(SUB_EXTS):
                if not self.mpv.idle_active:
                    self.mpv.command("sub-add", path, "select")
                continue

            valid_types = ("video/", "audio/", "image/")
            if mime_type.startswith(valid_types):
                self.mpv.loadfile(path, mode)
                first_file = False

        GLib.idle_add(
            lambda *a: self._on_shuffle_toggled(self.playlist_shuffle_toggle_button)
        )

    def _sync_fullscreen(self, mpv_is_fs):
        self.is_fullscreen = mpv_is_fs
        if mpv_is_fs:
            self.fullscreen()
        else:
            self.unfullscreen()

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        key_name = Gdk.keyval_name(keyval)

        if key_name == "Escape":
            self.mpv.fullscreen = False
            return

        if key_name in ("Tab", "ISO_Left_Tab", "Return"):
            self.revealer_ui.set_reveal_child(True)
            self._hide_ui_timeout(s=3)
            return

        app: Gtk.Application | None = self.get_application()
        clean_state = state & Gtk.accelerator_get_default_mod_mask()
        accel_name = Gtk.accelerator_name(keyval, clean_state)
        if app and app.get_actions_for_accel(accel_name):
            return

        mpv_key = KEY_REMAP.get(key_name, key_name)
        mods = []

        if state & Gdk.ModifierType.CONTROL_MASK:
            mods.append("ctrl")
        if state & Gdk.ModifierType.ALT_MASK:
            mods.append("alt")
        if state & Gdk.ModifierType.SHIFT_MASK:
            if len(mpv_key) == 1 and mpv_key.isalpha():
                mpv_key = mpv_key.upper()
            else:
                mods.append("shift")

        full_combo = "+".join(mods + [mpv_key])

        try:
            self.mpv.command("keypress", full_combo)
            return True
        except Exception:
            return

    def _on_click_pressed(self, gesture, n_press, _x, _y):
        gtk_button = gesture.get_current_button()
        button = MBTN_MAP.get(gtk_button)

        controls_hover = self.motion_controls.props.contains_pointer
        header_hover = self.motion_header.props.contains_pointer
        separator_hover = self.motion_controls_separator.props.contains_pointer

        if not button or (
            button != "MBTN_RIGHT"
            and (controls_hover or header_hover)
            and not separator_hover
        ):
            return

        if button in ("MBTN_BACK", "MBTN_FORWARD"):
            self.mpv.keypress(button)
        else:
            self.mpv.keydown(button)

        def on_click_hold():
            self.click_hold_id = 0

            try:
                self.click_holding = True
                self.prev_speed = cast(float, self.mpv["speed"])
                new_speed = self.prev_speed * 2
                self.mpv["speed"] = new_speed
                self.mpv.show_text(f"{new_speed:g}× ⯈⯈", "100000000")
                self.mpv.keypress(button)
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            except mpv.ShutdownError:
                pass

        if button == "MBTN_LEFT" and n_press == 1 and not self.mpv.pause:
            if self.click_hold_id:
                GLib.source_remove(self.click_hold_id)

            self.click_hold_id = GLib.timeout_add(400, on_click_hold)

        self._show_ui()
        self._hide_ui_timeout()

        if button != "MBTN_LEFT":
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        elif button == "MBTN_LEFT" and n_press == 2:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _on_click_released(self, gesture, _n_press, _x, _y):
        gtk_button = gesture.get_current_button()
        button = MBTN_MAP.get(gtk_button)

        self._cancel_click_hold()

        if not button:
            return

        self.mpv.keyup(button)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _cancel_click_hold(self, *args):
        if self.click_hold_id:
            GLib.source_remove(self.click_hold_id)
            self.click_hold_id = 0

        if self.click_holding:
            self.mpv["speed"] = self.prev_speed
            self.click_holding = False
            self.mpv.show_text(f"{self.mpv["speed"]:g}×")

    def _on_mouse_scroll(self, controller, dx, dy):
        event: Gdk.ScrollEvent = controller.get_current_event()
        rel_dir: Gdk.ScrollRelativeDirection = event.get_relative_direction(event)  # type: ignore
        is_natural: bool = rel_dir == Gdk.ScrollRelativeDirection.INVERTED  # type: ignore
        UP: str = "WHEEL_DOWN" if is_natural else "WHEEL_UP"
        DOWN: str = "WHEEL_UP" if is_natural else "WHEEL_DOWN"
        LEFT: str = "WHEEL_RIGHT" if is_natural else "WHEEL_LEFT"
        RIGHT: str = "WHEEL_LEFT" if is_natural else "WHEEL_RIGHT"
        wheel: str | None = None

        # Only trigger if scrolled a full 'unit'
        if abs(dy) >= 1:
            wheel = UP if dy < 0 else DOWN
        elif abs(dx) >= 1:
            wheel = RIGHT if dx > 0 else LEFT

        if wheel:
            self.mpv.keypress(wheel)
            return True

    def _on_mouse_scroll_volume(self, controller, _dx, dy):
        event: Gdk.ScrollEvent = controller.get_current_event()
        direction: Gdk.ScrollDirection = event.get_direction()
        rel_dir: Gdk.ScrollRelativeDirection = event.get_relative_direction(event)  # type: ignore
        is_natural: bool = rel_dir == Gdk.ScrollRelativeDirection.INVERTED  # type: ignore
        max_vol = cast(float, self.mpv.volume_max)
        step = dy if direction == Gdk.ScrollDirection.SMOOTH else dy * 5

        if is_natural:
            step = -step

        adj = self.volume_scale.get_adjustment()
        volume = adj.get_value()
        new_vol = int(volume - step)
        new_vol = max(adj.get_lower(), min(new_vol, max_vol))
        adj.set_value(new_vol)

        return True

    def _get_display_param(self):
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
        except Exception as e:
            print(f"Error getting display param: {e}")

        return param

    def _on_realize_area(self, area):
        area.make_current()

        proc_address_fn = mpv.MpvGlGetProcAddressFn(
            lambda _inst, name: egl_get_proc_address(name)
        )

        display_param = self._get_display_param()

        self.mpv_ctx = mpv.MpvRenderContext(
            self.mpv,
            "opengl",
            opengl_init_params={
                "get_proc_address": proc_address_fn,
            },
            **display_param,
        )

        self.mpv_ctx.update_cb = lambda: GLib.idle_add(
            self.gl_area.queue_render,
            priority=GLib.PRIORITY_HIGH_IDLE,  # pyright: ignore[reportCallIssue]
        )

        self.fbo = ctypes.c_int()

    def _on_render_area(self, area, _context):
        if not self.mpv_ctx:
            return
        try:
            glGetIntegerv(GL_FRAMEBUFFER_BINDING, self.fbo)
            scale = area.props.scale_factor

            self.mpv_ctx.render(
                flip_y=True,
                opengl_fbo={
                    "w": int(area.get_width() * scale),
                    "h": int(area.get_height() * scale),
                    "fbo": self.fbo.value,
                },
            )
        except Exception as e:
            print(f"Render error: {e}")
            return

    def _set_window_size(self, width, height):
        if width <= 0 or height <= 0:
            return

        MAX_WIDTH, MAX_HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT

        aspect_ratio = width / height
        new_w = width
        new_h = height

        if new_w > MAX_WIDTH:
            new_w = MAX_WIDTH
            new_h = int(new_w / aspect_ratio)

        if new_h > MAX_HEIGHT:
            new_h = MAX_HEIGHT
            new_w = int(new_h * aspect_ratio)

        self.set_default_size(new_w, new_h)

    def _sync_inhibit(self):
        should_inhibit = not self.mpv.pause and not self.mpv.idle_active

        if should_inhibit and self.inhibit_id == 0:
            self.inhibit_id = self.app.inhibit(
                self,
                Gtk.ApplicationInhibitFlags.IDLE,
                "Playing Video",
            )
        elif not should_inhibit and self.inhibit_id != 0:
            self.app.uninhibit(self.inhibit_id)
            self.inhibit_id = 0

    def _setup_observers(self):
        @self.mpv.event_callback("start-file")
        def on_start_file(event):
            GLib.idle_add(self.spinner.set_visible, True)
            self.loaded_path = str(self.mpv.path)

        @self.mpv.event_callback("file-loaded")
        def on_files_loaded(event):
            GLib.idle_add(self.spinner.set_visible, False)

        @self.mpv.event_callback("end-file")
        def on_end_file(event):
            GLib.idle_add(self.spinner.set_visible, False)
            info = event.as_dict()
            reason = info["reason"]
            if reason == b"error":
                print(f"File error path: {self.loaded_path}")
                error = info["file_error"]
                toast = Adw.Toast.new(_("File Error") + f": {error.decode('utf-8')}")
                self.toast_overlay.add_toast(toast)
                self.mpv.stop()

        @self.mpv.property_observer("path")
        def on_path_change(_name, has_file):
            if has_file:
                GLib.idle_add(self.play_pause_button.set_sensitive, has_file)

        @self.mpv.property_observer("playlist-count")
        def on_playlist_count_change(_name, _count):
            GLib.idle_add(self._update_playlist_nav_sensitivity)

        @self.mpv.property_observer("loop-playlist")
        def on_loop_playlist_change(_name, value):
            GLib.idle_add(self.playlist_loop_toggle_button.set_active, value == "inf")
            GLib.idle_add(self._update_playlist_nav_sensitivity)

        @self.mpv.property_observer("loop-file")
        def on_loop_file_change(_name, value):
            GLib.idle_add(self.loop_file_toggle_button.set_active, value == "inf")

        @self.mpv.property_observer("fullscreen")
        def on_fs_change(_name, value):
            def update():
                icon = (
                    "cine-view-restore-symbolic"
                    if value
                    else "cine-view-fullscreen-symbolic"
                )
                text = _("Exit Fullscreen") if value else _("Fullscreen")
                self.fullscreen_button.set_tooltip_text(text)
                self.fullscreen_button.set_icon_name(icon)
                self._sync_fullscreen(value)

            GLib.idle_add(update)

        @self.mpv.property_observer("time-pos")
        def on_time_change(_name, value):
            GLib.idle_add(self._update_progress, float(value or 0))

        @self.mpv.property_observer("duration")
        def on_duration_change(_name, value):
            GLib.idle_add(self._update_duration, float(value or 0))

        @self.mpv.property_observer("volume")
        def on_volume_change(_name, value):
            def update_icon_and_vol_adj():
                # block the signal to not trigger value-changed
                self.volume_scale.handler_block(self.volume_handler_id)
                self.volume_scale_adjustment.set_value(int(value))
                self.mpv.show_text(_("Volume") + f": {int(value)}%")
                self.volume_scale.handler_unblock(self.volume_handler_id)
                self._update_volume_icon(self.mpv.mute)
                settings.set_int("volume", int(value))

            GLib.idle_add(update_icon_and_vol_adj)

        track_map = {
            "sid": "select-subtitle",
            "aid": "select-audio",
            "vid": "select-video",
        }

        def on_track_change(name, value):
            def set_track():
                action_name = track_map.get(name) or ""
                val = value if isinstance(value, int) else 0
                if action := self.lookup_action(action_name):
                    action.set_state(  # pyright: ignore[reportAttributeAccessIssue]
                        GLib.Variant("i", val)
                    )

            GLib.idle_add(set_track)

        for prop in track_map.keys():
            self.mpv.property_observer(prop)(on_track_change)

        @self.mpv.property_observer("track-list")
        def on_track_list_change(_name, track_list):
            GLib.idle_add(self._update_track_menus, track_list)

        @self.mpv.property_observer("playlist-pos")
        def on_pl_pos_change(_name, _value):
            def update():
                self._update_playlist_nav_sensitivity()
                if dialog := cast(Playlist, self.get_visible_dialog()):
                    dialog._scroll_to_playing()

            GLib.idle_add(update)

        @self.mpv.property_observer("chapter-list")
        def on_chapters_change(_name, value):
            self.current_chapters = (
                sorted(value, key=lambda x: x.get("time", 0)) if value else []
            )
            GLib.idle_add(self._update_chapter_marks, value)

        @self.mpv.property_observer("pause")
        def on_pause_change(_name, paused):
            GLib.idle_add(self._sync_inhibit)
            GLib.idle_add(self._update_play_pause_icon, paused)

        @self.mpv.property_observer("eof-reached")
        def watch_eof(_name, value):
            # allow to replay at eof, requires keep-open
            if value:
                self.mpv.seek(0, reference="absolute")
                self.mpv.pause = True

        @self.mpv.property_observer("idle-active")
        def on_idle_change(_name, is_idle):
            def update_state():
                self.actions["open-sub-menu"].set_enabled(not is_idle)
                self.actions["open-audio-menu"].set_enabled(not is_idle)

                self.start_page.set_visible(is_idle)
                self.controls_box.set_visible(not is_idle)
                self.gl_area.set_visible(not is_idle)

                if is_idle:
                    self.revealer_ui.set_reveal_child(True)
                    self.set_title(_("Cine"))

                self._sync_inhibit()

            if not self.mpv.keep_open and is_idle and not self.startup:
                self.close()

            self.startup = False

            GLib.idle_add(update_state)

        @self.mpv.property_observer("media-title")
        def on_title_change(_name, title):
            def set():
                if title == self.mpv.filename:
                    title_no_ext = os.path.splitext(title)[0]
                    self.set_title(title_no_ext)
                else:
                    self.set_title(title)

            if title:
                GLib.idle_add(set)

        @self.mpv.property_observer("mute")
        def on_mute_change(_name, value):
            def update():
                self.mute_toggle_button.set_active(value)
                self._update_volume_icon(value)

            GLib.idle_add(update)

        @self.mpv.property_observer("sub-scale")
        def on_sub_scale_change(_name, value):
            settings.set_double("subtitle-scale", value)

        @self.mpv.property_observer("sub-visibility")
        @self.mpv.property_observer("sid")
        def on_sub_vis_change(_name, value):
            def set_icon():
                try:
                    sub_on = (value == "auto" or value) and self.mpv.sid
                    self.subtitles_menu_button.props.icon_name = (
                        "cine-subtitles-symbolic"
                        if sub_on
                        else "cine-subtitles-off-symbolic"
                    )
                except mpv.ShutdownError:
                    pass

            GLib.idle_add(set_icon)

        @self.mpv.property_observer("aid")
        def on_aid_change(_name, value):
            def set_icon():
                try:
                    audio_on = value == "auto" or value
                    self.audio_tracks_menu_button.props.icon_name = (
                        "cine-audio-symbolic" if audio_on else "cine-audio-off-symbolic"
                    )
                except mpv.ShutdownError:
                    pass

            GLib.idle_add(set_icon)

        @self.mpv.event_callback("shutdown")
        def on_quit(_event):
            GLib.idle_add(self.close)
