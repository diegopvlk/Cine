# history.py
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
import json
import datetime
from gettext import gettext as _
from .utils import logger, is_local_path, idle_add_once

gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, Gdk, GLib, Gtk


@Gtk.Template(resource_path="/io/github/diegopvlk/Cine/history.ui")
class HistoryDialog(Adw.Dialog):
    __gtype_name__ = "HistoryDialog"

    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    clear_btn: Gtk.Button = Gtk.Template.Child()
    hist_box: Gtk.Box = Gtk.Template.Child()
    spinner: Adw.Spinner = Gtk.Template.Child()
    history_prefs_page: Adw.PreferencesPage = Gtk.Template.Child()
    placeholder_img: Gtk.Image = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self._win = window
        self._hist_path = window.mpv["watch-history-path"]
        self._groups = {}

        self._load_all_group = Adw.PreferencesGroup()
        self._load_btn = Gtk.Button(
            label=_("Load All"),
            css_classes=["pill"],
            halign=Gtk.Align.CENTER,
        )
        self._load_btn.props.label = _("Load All")
        self._load_all_group.add(self._load_btn)

        self._load_btn.connect(
            "clicked", lambda *_b: self._populate_history(load_all=True)
        )

        self._populate_history()

    def _populate_history(self, load_all=False):
        self.spinner.set_visible(True)

        for group in list(self._groups.values()):
            self.history_prefs_page.remove(group)
        self._groups.clear()

        if os.path.exists(self._hist_path) and os.path.getsize(self._hist_path) > 0:
            self.clear_btn.set_sensitive(True)
            self.placeholder_img.set_visible(False)
            self.history_prefs_page.set_visible(True)

            unique_entries = {}

            with open(self._hist_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        file_path = entry.get("path")
                        timestamp = entry.get("time")

                        dt_object = datetime.datetime.fromtimestamp(timestamp)
                        day_key = dt_object.strftime("%Y-%m-%d")

                        dedup_key = (day_key, file_path)
                        unique_entries.pop(dedup_key, None)
                        unique_entries[dedup_key] = entry
                    except json.JSONDecodeError:
                        pass

            ordered_entries = list(unique_entries.values())
            ordered_entries.reverse()

            if load_all:
                max_entries = ordered_entries
            else:
                max_entries = ordered_entries[:100]

            created_groups = {}

            for item in max_entries:
                path = item.get("path")
                timestamp = item.get("time")

                dt_object = datetime.datetime.fromtimestamp(timestamp)
                day_key = dt_object.strftime("%Y-%m-%d")

                if is_local_path(path):
                    name_with_ext = os.path.basename(path)
                    file_title = os.path.splitext(name_with_ext)[0]
                else:
                    file_title = item.get("title") or path

                if day_key not in created_groups:
                    dt_title = dt_object.strftime("%x")
                    group = Adw.PreferencesGroup(title=dt_title)
                    created_groups[day_key] = group
                else:
                    group = created_groups[day_key]

                row = Adw.ActionRow(
                    title=GLib.markup_escape_text(file_title),
                    title_lines=1,
                    tooltip_text=file_title,
                    activatable=True,
                    css_classes=["row-history"],
                )

                rm_btn = Gtk.Button(
                    tooltip_text=_("Remove from History"),
                    icon_name="edit-delete-symbolic",
                    css_classes=["flat", "circular"],
                    valign=Gtk.Align.CENTER,
                )

                rm_btn.connect(
                    "clicked",
                    lambda _btn, r=row, p=path, dk=day_key, t=timestamp: (
                        self._rm_entry_from_hist(r, p, dk, t)
                    ),
                )

                row.add_suffix(rm_btn)

                gesture = Gtk.GestureClick.new()
                gesture.set_button(3)
                gesture.connect("pressed", self._on_row_right_click, row, path)
                row.add_controller(gesture)

                row.connect("activated", lambda _r, p=path: self._on_row_activated(p))
                group.add(row)

            if load_all:
                self._load_all_group.set_visible(False)
            else:
                try:
                    with open(self._hist_path, "w", encoding="utf-8") as f:
                        for item in reversed(ordered_entries):
                            f.write(json.dumps(item, ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.error(f"Failed to save history file: {e}")
                    idle_add_once(self._show_toast, f"{repr(e)}")

            for day_key in sorted(created_groups.keys(), reverse=True):
                group = created_groups[day_key]
                self._groups[day_key] = group

                if load_all:
                    idle_add_once(self.history_prefs_page.add, group)
                else:
                    self.history_prefs_page.add(group)

            if not load_all and len(ordered_entries) > 100:
                self.history_prefs_page.add(self._load_all_group)
                self._load_btn.props.label += f" (+{len(ordered_entries) - 100})"  # type: ignore

        else:
            self.clear_btn.set_sensitive(False)
            self.placeholder_img.set_visible(True)
            self.history_prefs_page.set_visible(False)
            if self.history_prefs_page.get_group(0):  # type: ignore
                self.history_prefs_page.remove(self._load_all_group)

        idle_add_once(self.spinner.set_visible, False)

    def _on_row_right_click(self, _gesture, _n_press, x, y, row, path):
        def on_launch_finished(launcher, result):
            try:
                launcher.open_containing_folder_finish(result)
            except Exception as e:
                logger.error(f"Error opening location: {e}")
                idle_add_once(self._show_toast, f"{repr(e)}")

        def show_in_folder():
            gfile = Gio.File.new_for_path(path)
            launcher = Gtk.FileLauncher.new(gfile)
            launcher.open_containing_folder(self._win, None, on_launch_finished)

        menu = Gio.Menu.new()
        menu.append(_("Open Item Location"), "row.open_location")
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

        row.insert_action_group("row", action_group)

        rect = Gdk.Rectangle()
        rect.x = x
        rect.y = y
        popover.set_pointing_to(rect)
        popover.popup()

    def _on_row_activated(self, file_path):
        try:
            self._win.mpv.loadfile(file_path, "replace")
            self._win.mpv.pause = False
            self.close()
        except Exception as e:
            logger.error(f"Error playing {file_path}: {e}")
            idle_add_once(self._show_toast, f"{repr(e)}")

    def _rm_entry_from_hist(self, row, file_path, day_key, timestamp):
        try:
            updated_lines = []
            with open(self._hist_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if (
                            entry.get("path") == file_path
                            and entry.get("time") == timestamp
                        ):
                            continue
                        updated_lines.append(line)
                    except json.JSONDecodeError:
                        pass

            with open(self._hist_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

            idx = row.get_index()

            if group := self._groups.get(day_key):
                group.remove(row)

                if row_to_scroll := group.get_row(max(0, idx - 1)):
                    row_to_scroll.grab_focus()

                if not group.get_row(0):
                    if prev_group := group.get_prev_sibling():
                        if isinstance(prev_group, Adw.PreferencesGroup):
                            last_row = None
                            i = 0
                            while curr_row := prev_group.get_row(i):  # type: ignore
                                last_row = curr_row
                                i += 1

                            if isinstance(last_row, Adw.ActionRow):
                                last_row.grab_focus()

                    if group != self._load_all_group:
                        self.history_prefs_page.remove(group)
                        self._groups.pop(day_key)

                    if os.path.getsize(self._hist_path) == 0:
                        self._groups.clear()
                        self._populate_history()

        except Exception as e:
            logger.error(f"Failed to remove item from history: {e}", exc_info=True)
            idle_add_once(self._show_toast, f"{repr(e)}")

    def _show_toast(self, label: str):
        toast = Adw.Toast(title=label)
        self.toast_overlay.dismiss_all()
        self.toast_overlay.add_toast(toast)

    @Gtk.Template.Callback()
    def _on_clear_history(self, *args):
        dialog = Adw.AlertDialog.new(heading=_("Clear Watch History?"))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("clear", _("Clear All"))
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_dialog, response):
            if response == "clear":
                if os.path.exists(self._hist_path):
                    try:
                        with open(self._hist_path, "w"):
                            pass
                    except Exception as e:
                        logger.error(
                            f"Failed to clear history file: {e}", exc_info=True
                        )
                        self._show_toast(f"{repr(e)}")
                    self._populate_history()

        dialog.connect("response", on_response)
        dialog.present(self)
