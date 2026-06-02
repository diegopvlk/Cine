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
import unicodedata

gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GObject", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gio, Gdk, GLib, Gtk, GObject, Pango

from gettext import gettext as _
from gettext import ngettext
from .utils import is_local_path


class PlaylistItemObj(GObject.Object):
    item = GObject.Property(type=object)
    playing = GObject.Property(type=bool, default=False)
    url_title = GObject.Property(type=str, default="")
    position = GObject.Property(type=int, default=0)

    def __init__(self, item, position):
        super().__init__()
        self.item = item
        self.playing = item.get("playing", False)
        self.url_title = item.get("title", "")
        self.position = position


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/playlist.ui")
class Playlist(Adw.Dialog):
    __gtype_name__ = "Playlist"

    title_widget: Adw.WindowTitle = Gtk.Template.Child()
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    spinner: Adw.Spinner = Gtk.Template.Child()
    playlist_clamp: Adw.Clamp = Gtk.Template.Child()
    playlist_list_view: Gtk.ListView = Gtk.Template.Child()
    factory: Gtk.SignalListItemFactory = Gtk.Template.Child()
    drop_indicator_revealer: Gtk.Revealer = Gtk.Template.Child()
    search_btn: Gtk.ToggleButton = Gtk.Template.Child()
    search_bar: Gtk.SearchBar = Gtk.Template.Child()
    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    no_results_label: Gtk.Label = Gtk.Template.Child()
    save_playlist_btn: Gtk.Button = Gtk.Template.Child()

    def __init__(self, win, **kwargs):
        super().__init__(**kwargs)
        self.win = win
        self.mpv = win.mpv

        ls_n_items = win.playlist_ls.get_n_items()
        shuffle_btn = win.shuffle_toggle_btn
        shuffle_changed = win.last_shuffle != shuffle_btn.props.active
        count = self.mpv.playlist_count

        if ls_n_items == 0 or ls_n_items != count or shuffle_changed:
            win._splice_playlist()

        self.set_content_height(win.get_height())
        self._set_item_count()

        list_filter = Gtk.CustomFilter()
        list_filter_model = Gtk.FilterListModel(
            model=win.playlist_ls, filter=list_filter
        )

        list_filter_model.connect(
            "items-changed",
            lambda *a: self.no_results_label.set_visible(
                not list_filter_model.get_item(0)
            ),
        )

        def search_filter(*args):
            def remove_diacritics(text):
                normalized = unicodedata.normalize("NFD", text)
                return "".join(c for c in normalized if unicodedata.category(c) != "Mn")

            query = remove_diacritics(self.search_entry.props.text.strip())

            def filter_func(obj):
                try:
                    item_name = remove_diacritics(obj.item["title"]).lower()
                    normalized_query = remove_diacritics(query).lower()
                    return normalized_query in item_name
                except Exception:
                    return True

            list_filter.set_filter_func(filter_func)
            self._set_item_count(list_amt=list_filter_model.get_n_items())

        self.search_entry.connect("search-changed", search_filter)
        self.search_entry.set_placeholder_text(_("Search") + "…")

        model = Gtk.NoSelection(model=list_filter_model)

        shortcut_search = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<primary>f"),
            action=Gtk.CallbackAction.new(self._set_search_mode_enabled),
        )
        shortcut_add_files = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<shift><primary>o"),
            action=Gtk.CallbackAction.new(self.win._on_add_playlist_dialog),
        )
        shortcut_add_folder = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<shift><primary>i"),
            action=Gtk.CallbackAction.new(self.win._on_open_folder_dialog),
        )
        shortcut_add_url = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<shift><primary>u"),
            action=Gtk.CallbackAction.new(self.win._on_add_url),
        )

        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.add_shortcut(shortcut_search)
        shortcut_controller.add_shortcut(shortcut_add_files)
        shortcut_controller.add_shortcut(shortcut_add_folder)
        shortcut_controller.add_shortcut(shortcut_add_url)

        self.add_controller(shortcut_controller)

        self.search_btn.connect("clicked", self._set_search_mode_enabled)
        self.search_bar.connect("notify::search-mode-enabled", self._set_search_btn)

        self.playlist_list_view.set_model(model)
        self.playlist_list_view.remove_css_class("view")

        self.factory.connect("setup", self._on_factory_setup)
        self.factory.connect("bind", self._on_factory_bind)
        self.factory.connect("unbind", self._on_factory_unbind)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.set_gtypes([Gdk.FileList, GObject.TYPE_STRING])
        drop_target.connect("enter", self._on_drop_enter)
        drop_target.connect("leave", self._on_drop_leave)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

        self._set_save_btn_playlist()
        self._update_playing_item()
        GLib.idle_add(
            self.playlist_list_view.scroll_to,
            self.mpv.playlist_pos,
            Gtk.ListScrollFlags.FOCUS,
        )

    @Gtk.Template.Callback()
    def _on_list_item_activate(self, list_view, pos):
        self.mpv.pause = False
        obj = list_view.get_model().get_item(pos)
        self.mpv.playlist_pos = obj.position
        self._update_playing_item()
        self.close()

    def _set_save_btn_playlist(self):
        btn = self.save_playlist_btn
        if self.win.has_some_doc_path:
            btn.set_tooltip_text(
                _("Save Playlist")
                + " - "
                + _(
                    "Requires flatpak permission to read the folder where the video is stored"
                )
            )
            btn.set_sensitive(False)
        else:
            btn.set_tooltip_text(_("Save Playlist"))
            btn.set_sensitive(True)

    def _update_playing_item(self):
        for i in range(self.win.playlist_ls.get_n_items()):
            obj = self.win.playlist_ls.get_item(i)
            is_playing = i == self.mpv.playlist_pos
            if obj.playing != is_playing:
                obj.playing = is_playing

    def _on_factory_setup(self, _factory, list_item):
        row = Gtk.Box(height_request=46)
        list_item.icon = Gtk.Image(margin_start=14)
        list_item.title = Gtk.Label(
            halign=Gtk.Align.START,
            margin_top=5,
            margin_bottom=5,
            margin_start=12,
            margin_end=12,
            hexpand=True,
            valign=Gtk.Align.CENTER,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=0,
            css_classes=["title"],
        )
        list_item.playing_icon = Gtk.Image(
            margin_end=14, icon_name="cine-playback-start-symbolic", visible=False
        )
        row.append(list_item.icon)
        row.append(list_item.title)
        row.append(list_item.playing_icon)

        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect("pressed", self._on_row_right_click, list_item, row)
        row.add_controller(gesture)

        row_drag_source = Gtk.DragSource.new()
        row_drag_source.set_actions(Gdk.DragAction.MOVE)
        row_drag_source.connect("prepare", self._on_row_drag_prepare, list_item)
        row_drag_source.connect("drag-begin", self._on_row_drag_begin)
        row.add_controller(row_drag_source)

        row_drop_target = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
        row_drop_target.connect("drop", self._on_row_drop, list_item)
        row.add_controller(row_drop_target)

        list_item.set_child(row)

    def _on_factory_bind(self, _factory, list_item):
        obj = list_item.get_item()
        item = obj.item
        row = list_item.get_child()

        path = item.get("filename")
        name_with_ext = os.path.basename(path)
        parent_dir = os.path.basename(os.path.dirname(path))
        dir = parent_dir if parent_dir else path

        icon_name = "cine-applications-multimedia-symbolic"
        file_title = os.path.splitext(name_with_ext)[0]

        if not is_local_path(path):
            content_type = "mpv-url"
            file_title = item.get("title") or obj.url_title or file_title
        else:
            try:
                info = Gio.File.new_for_path(path).query_info(
                    "standard::content-type", Gio.FileQueryInfoFlags.NONE, None
                )
                content_type = info.get_content_type()
            except Exception:
                content_type = "error"

        if content_type == "inode/directory":
            icon_name = "cine-folder-symbolic"
            file_title = name_with_ext
            if not os.listdir(path):
                list_item.icon.set_opacity(0.5)
                list_item.title.set_opacity(0.5)
        elif content_type:
            if "video" in content_type:
                icon_name = "cine-video-x-generic-symbolic"
            elif "mpegurl" in content_type:
                icon_name = "cine-playlist-m3u-symbolic"
            elif "audio" in content_type:
                icon_name = "cine-audio-x-generic-symbolic"
            elif "image" in content_type:
                icon_name = "cine-image-x-generic-symbolic"
            elif content_type == "mpv-url":
                icon_name = "cine-globe-symbolic"
            elif content_type == "error":
                icon_name = "cine-warning-symbolic"

        list_item.title.set_text(file_title)
        dir = GLib.markup_escape_text(dir)
        file_title = GLib.markup_escape_text(file_title)
        list_item.title.set_tooltip_markup(f"<b>{dir}</b>\n{file_title}")
        list_item.icon.set_from_icon_name(icon_name)

        def set_playing_item(obj, pspec):
            list_item.playing_icon.props.visible = obj.playing
            if obj.playing:
                row.add_css_class("playing-item-playlist")
            else:
                row.remove_css_class("playing-item-playlist")

        set_playing_item(obj, None)

        list_item.handler_id = obj.connect("notify::playing", set_playing_item)

    def _on_factory_unbind(self, _factory, list_item):
        obj = list_item.get_item()
        obj.disconnect(list_item.handler_id)

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
        items: list[Gio.File] | list[str] = []

        if isinstance(value, Gdk.FileList):
            items = value.get_files()
        elif isinstance(value, str):
            items = [value]

        for item in items:
            if isinstance(item, Gio.File):
                path = item.get_path() or item.get_uri()

                is_url = not is_local_path(path)  # URL Thumbnail

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
                    lambda *a: self.win._on_shuffle_toggled(self.win.shuffle_toggle_btn)
                )

            elif isinstance(item, str):  # URL string
                self.mpv.loadfile(item, "append-play")

        self.spinner.set_visible(False)

    def _on_row_drag_prepare(self, _source, _x, _y, list_item):
        index = list_item.get_item().position
        return Gdk.ContentProvider.new_for_value(index)

    def _on_row_drag_begin(self, source, _drag):
        source.set_icon(Gtk.WidgetPaintable.new(source.get_widget()), 0, 0)

    def _on_row_drop(self, _target, source_index, _x, _y, list_item):
        dest_index = list_item.get_item().position
        if source_index == dest_index:
            return

        if source_index < dest_index:
            self.mpv.command("playlist-move", source_index, dest_index + 1)
        else:
            self.mpv.command("playlist-move", source_index, dest_index)

        self.win._splice_playlist()

    def _on_row_right_click(self, gesture, _n_press, x, y, list_item, row):
        idx = list_item.get_item().position
        path = list_item.get_item().item["filename"]

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
            if index > 0 and index == self.mpv.playlist_count - 1:
                self.mpv.playlist_pos = index - 1
            self.mpv.command("playlist-remove", index)

            GLib.timeout_add(
                100,
                self.playlist_list_view.scroll_to,
                abs(index - 1),
                Gtk.ListScrollFlags.FOCUS,
            )

        menu = Gio.Menu.new()
        menu.append(_("Open Item Location"), "row.open_location")
        menu.append(_("Remove from Playlist"), "row.remove_item")

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(row)
        popover.set_has_arrow(False)
        popover.set_autohide(True)
        row.connect("unrealize", lambda *_: (popover.unrealize(), popover.unparent()))

        action_group = Gio.SimpleActionGroup.new()

        if is_local_path(path):
            open_location = Gio.SimpleAction.new("open_location", None)
            open_location.connect("activate", lambda *_: show_in_folder())
            action_group.add_action(open_location)

        remove_item = Gio.SimpleAction.new("remove_item", None)
        remove_item.connect("activate", lambda *_: remove_from_playlist(idx))
        action_group.add_action(remove_item)

        row.insert_action_group("row", action_group)

        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        popover.set_pointing_to(rect)
        popover.popup()

    def _set_search_mode_enabled(self, *args):
        self.search_bar.props.search_mode_enabled = (
            not self.search_bar.props.search_mode_enabled
        )
        return True

    def _set_search_btn(self, *args):
        self.search_btn.props.active = self.search_bar.props.search_mode_enabled

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

    def _set_item_count(self, *args, list_amt=None):
        count = list_amt if list_amt is not None else self.mpv.playlist_count
        amt_label = ngettext("{n} item", "{n} items", count).format(n=count)
        self.title_widget.set_subtitle(f"{amt_label}")

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
