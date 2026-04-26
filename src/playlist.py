# playlist.py
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
import os

gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GObject", "2.0")
from gi.repository import Adw, Gio, Gdk, GLib, Gtk, GObject
from gettext import gettext as _
from .utils import is_local_path, has_host_permission


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/playlist.ui")
class Playlist(Adw.Dialog):
    __gtype_name__ = "Playlist"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    spinner: Adw.Spinner = Gtk.Template.Child()
    playlist_clamp: Adw.Clamp = Gtk.Template.Child()
    playlist_list_box: Gtk.ListBox = Gtk.Template.Child()
    drop_indicator_revealer: Gtk.Revealer = Gtk.Template.Child()
    save_playlist_btn: Gtk.Button = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.win = window
        self.mpv = window.mpv
        uid = os.getuid()
        self.doc_path = f"/run/user/{uid}/doc/"

        self.set_content_height(window.get_height())

        self._populate_list()

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.set_gtypes([Gdk.FileList, GObject.TYPE_STRING])
        drop_target.connect("enter", self._on_drop_enter)
        drop_target.connect("leave", self._on_drop_leave)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

    def _on_drop_enter(self, target, _x, _y):
        GLib.timeout_add(10, self.drop_indicator_revealer.set_reveal_child, True)
        drop = target.get_current_drop()
        formats = drop.get_formats()
        target_type = (
            Gdk.FileList if formats.contain_gtype(Gdk.FileList) else GObject.TYPE_STRING
        )

        def on_read_done(source, result):
            try:
                source.read_value_finish(result)
                self.spinner.set_visible(True)
            except GLib.Error as e:
                toast = Adw.Toast.new(_("File Error") + f": {e.message}")
                self.toast_overlay.add_toast(toast)
                return

        drop.read_value_async(target_type, GLib.PRIORITY_DEFAULT, None, on_read_done)

        return True

    def _on_drop_leave(self, _target):
        self.spinner.set_visible(False)
        GLib.timeout_add(10, self.drop_indicator_revealer.set_reveal_child, False)

    def _on_drop(self, _target, value, _x, _y):
        items: list[Gio.File] | list[str] = (
            value.get_files()
            if isinstance(value, Gdk.FileList)
            else [value] if isinstance(value, str) else []
        )

        for item in items:
            if isinstance(item, Gio.File):
                path = item.get_path() or item.get_uri()

                # URL Thumbnail
                is_url = not is_local_path(path)

                if is_url:
                    self.mpv.loadfile(path, "append-play")
                    continue
                else:
                    info = item.query_info(
                        "standard::content-type,standard::type",
                        Gio.FileQueryInfoFlags.NONE,
                        None,
                    )

                file_type = info.get_file_type()
                mime_type = info.get_content_type() or ""

                if file_type == Gio.FileType.DIRECTORY:
                    self.mpv.loadfile(path, "append-play")
                    continue

                valid_types = ("video/", "audio/", "image/")
                if mime_type.startswith(valid_types):
                    self.mpv.loadfile(path, "append-play")

                GLib.idle_add(
                    lambda *a: self.win._on_shuffle_toggled(
                        self.win.playlist_shuffle_toggle_button
                    )
                )

            elif isinstance(item, str):  # URL string
                self.mpv.loadfile(item, "append-play")

        self._populate_list()
        self.spinner.set_visible(False)

    def _populate_list(self, row_idx=None):
        self.playlist_list_box.remove_all()
        playlist = self.mpv.playlist

        for index, item in enumerate(playlist):
            path = item.get("filename")

            if (
                self.doc_path in path
                and self.save_playlist_btn.props.sensitive
                and not has_host_permission
            ):
                self.save_playlist_btn.set_tooltip_text(
                    _("Save Playlist")
                    + " - "
                    + _(
                        "Requires flatpak permission to read the folder where the video is stored"
                    )
                )
                self.save_playlist_btn.set_sensitive(False)

            name_with_ext = os.path.basename(path)
            parent_dir = os.path.basename(os.path.dirname(path))
            dir = parent_dir if parent_dir else path
            dir = GLib.markup_escape_text(dir)

            row = Adw.ActionRow(title=dir)
            row.add_css_class("property")
            row.props.activatable = True

            icon_name = "cine-applications-multimedia-symbolic"
            file_title = os.path.splitext(name_with_ext)[0]

            if not is_local_path(path):
                content_type = "mpv-url"
                file_title = item.get("title") or file_title
            else:
                try:
                    info = Gio.File.new_for_path(path).query_info(
                        "standard::content-type", Gio.FileQueryInfoFlags.NONE, None
                    )
                    content_type = info.get_content_type()
                except:
                    content_type = "error"

            if content_type == "inode/directory":
                icon_name = "cine-folder-symbolic"
                file_title = name_with_ext
                if not os.listdir(path):
                    row.set_sensitive(False)
            elif content_type:
                if "mpegurl" in content_type:
                    icon_name = "cine-playlist-m3u-symbolic"
                elif "audio" in content_type:
                    icon_name = "cine-audio-x-generic-symbolic"
                elif "video" in content_type:
                    icon_name = "cine-video-x-generic-symbolic"
                elif "image" in content_type:
                    icon_name = "cine-image-x-generic-symbolic"
                elif content_type == "mpv-url":
                    icon_name = "cine-globe-symbolic"
                elif content_type == "error":
                    icon_name = "cine-warning-symbolic"

            file_title = GLib.markup_escape_text(file_title)
            row.set_subtitle(file_title)
            row.set_icon_name(icon_name)
            row.connect("activated", self._on_file_activated, index)

            gesture = Gtk.GestureClick.new()
            gesture.set_button(3)
            gesture.connect("pressed", self._on_row_right_click, path)
            row.add_controller(gesture)

            row_drag_source = Gtk.DragSource.new()
            row_drag_source.set_actions(Gdk.DragAction.MOVE)
            row_drag_source.connect("prepare", self._on_row_drag_prepare, index)
            row_drag_source.connect("drag-begin", self._on_row_drag_begin)
            row.add_controller(row_drag_source)

            row_drop_target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
            row_drop_target.connect("drop", self._on_row_drop, index)
            row.add_controller(row_drop_target)

            self.playlist_list_box.append(row)

        GLib.idle_add(self._scroll_to_playing, row_idx)

    def _on_row_drag_prepare(self, _source, _x, _y, index):
        return Gdk.ContentProvider.new_for_value(index)

    def _on_row_drag_begin(self, source, _drag):
        source.set_icon(Gtk.WidgetPaintable.new(source.get_widget()), 0, 0)

    def _on_row_drop(self, _target, source_index, _x, _y, dest_index):
        if source_index == dest_index:
            return

        if source_index < dest_index:
            self.mpv.command("playlist-move", source_index, dest_index + 1)
        else:
            self.mpv.command("playlist-move", source_index, dest_index)

        self._populate_list(dest_index)

    def _on_row_right_click(self, gesture, _n_press, x, y, path):
        def show_in_folder():
            gfile = Gio.File.new_for_path(path)
            launcher = Gtk.FileLauncher.new(gfile)
            launcher.open_containing_folder(self.win, None, on_launch_finished)

        def on_launch_finished(launcher, result):
            try:
                launcher.open_containing_folder_finish(result)
            except Exception as e:
                print(f"Error opening location: {e}")

        def remove_from_playlist(index):
            self.mpv.command("playlist-remove", index)
            self._populate_list(index)

        menu = Gio.Menu.new()
        menu.append(_("Open Item Location"), "row.open_location")
        menu.append(_("Remove from Playlist"), "row.remove_item")

        row = gesture.get_widget()
        index = row.get_index()

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(row)
        popover.set_has_arrow(False)
        popover.set_autohide(True)
        row.connect("destroy", lambda *_: (popover.unrealize(), popover.unparent()))

        action_group = Gio.SimpleActionGroup.new()

        if is_local_path(path):
            open_location = Gio.SimpleAction.new("open_location", None)
            open_location.connect("activate", lambda *_: show_in_folder())
            action_group.add_action(open_location)

        remove_item = Gio.SimpleAction.new("remove_item", None)
        remove_item.connect("activate", lambda *_: remove_from_playlist(index))
        action_group.add_action(remove_item)

        row.insert_action_group("row", action_group)

        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        popover.set_pointing_to(rect)
        GLib.idle_add(popover.popup)

    def _scroll_to_playing(self, idx=None):
        if hasattr(self, "curr_playing_row") and self.curr_playing_row:
            self.curr_playing_row.remove_css_class("playing-item-playlist")

        if not hasattr(self, "playing_icon") or not self.playing_icon:
            self.playing_icon = Gtk.Image.new_from_icon_name(
                "cine-playback-start-symbolic"
            )

        parent = self.playing_icon.get_parent()
        if isinstance(parent, (Gtk.Box, Adw.ActionRow)):
            parent.remove(self.playing_icon)

        current_pos = self.mpv.playlist_pos
        new_row = self.playlist_list_box.get_row_at_index(current_pos)

        if isinstance(new_row, (Gtk.Box, Adw.ActionRow)):
            if idx is None:
                new_row.grab_focus()
            elif row := self.playlist_list_box.get_row_at_index(max(0, idx - 1)):
                row.grab_focus()

            new_row.add_css_class("playing-item-playlist")
            new_row.add_suffix(self.playing_icon)

            self.curr_playing_row = new_row

    def _on_file_activated(self, _row, index):
        self.mpv.playlist_pos = index
        self.mpv.pause = False
        self.close()

    @Gtk.Template.Callback()
    def _on_add_playlist_files(self, _button):
        self.win._open_add_dialog(_("Add Files"), "playlist-add", from_playlist=True)

    @Gtk.Template.Callback()
    def _on_save_playlist(self, _button):
        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Save Playlist"))
        dialog.set_initial_name(_("Playlist") + ".m3u8")

        m3u8_filter = Gtk.FileFilter()
        m3u8_filter.add_suffix("m3u8")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(m3u8_filter)
        dialog.set_filters(filters)

        def on_save(_dialog, result):
            try:
                file = dialog.save_finish(result)
                path = file.get_path()
                self._write_m3u_file(self.mpv, path)
            except Exception as e:
                print(f"Save playlist error: {e}")

        dialog.save(self.win, None, on_save)

    def _write_m3u_file(self, mpv, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            for item in mpv.playlist:
                path = item["filename"]
                name_with_ext = os.path.basename(path)
                file_title = os.path.splitext(name_with_ext)[0]
                title = file_title

                if not is_local_path(path):
                    title = item.get("title") or file_title

                duration = -1

                f.write(f"#EXTINF:{duration},{title}\n")
                f.write(f"{path}\n")
