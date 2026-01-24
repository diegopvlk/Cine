# mpris.py
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

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk
from gettext import gettext as _

APP_ID = "io.github.diegopvlk.Cine"

# This is a mess, but it (kinda) works :D
# Keep PlaybackStatus, Metadata and CanSeek commented, it causes stutters
# those will come from _sync_player_state and _update_props
INTERFACE = """
<!DOCTYPE node PUBLIC
'-//freedesktop//DTD D-BUS Object Introspection 1.0//EN'
'http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd'>
<node>
    <interface name='org.mpris.MediaPlayer2'>
        <method name='Raise'/>
        <method name='Quit'/>
        <property name='Identity' type='s' access='read'/>
        <property name='DesktopEntry' type='s' access='read'/>
        <property name='CanQuit' type='b' access='read'/>
        <property name='CanRaise' type='b' access='read'/>
        <property name='HasTrackList' type='b' access='read'/>
        <property name='SupportedUriSchemes' type='as' access='read'/>
        <property name='SupportedMimeTypes' type='as' access='read'/>
    </interface>
    <interface name='org.mpris.MediaPlayer2.Player'>
        <method name='Next'/>
        <method name='Previous'/>
        <method name='Pause'/>
        <method name='PlayPause'/>
        <method name='Stop'/>
        <method name='Play'/>
        <method name='Seek'>
            <arg direction='in' name='Offset' type='x'/>
        </method>
        <method name='SetPosition'>
            <arg direction='in' name='TrackId' type='o'/>
            <arg direction='in' name='Position' type='x'/>
        </method>
        <signal name='Seeked'>
            <arg name='Position' type='x'/>
        </signal>
        <!--
        <property name='PlaybackStatus' type='s' access='read'/>
        <property name='Metadata' type='a{sv}' access='read'/>
        <property name='CanSeek' type='b' access='read'/>
        -->
        <property name='LoopStatus' type='s' access='readwrite'/>
        <property name='Volume' type='d' access='readwrite'/>
        <property name='Position' type='x' access='read'/>
        <property name='CanGoNext' type='b' access='read'/>
        <property name='CanGoPrevious' type='b' access='read'/>
        <property name='CanPlay' type='b' access='read'/>
        <property name='CanPause' type='b' access='read'/>
        <property name='CanControl' type='b' access='read'/>
        <property name='Shuffle' type='b' access='readwrite'/>
    </interface>
</node>
"""


class MPRIS:
    def __init__(self, app: Gtk.Application) -> None:
        self._app = app
        self._bus_name = f"org.mpris.MediaPlayer2.{APP_ID}"
        self._path = "/org/mpris/MediaPlayer2"
        self._con = None

        # Track previous states to avoid redundant signal emissions
        self._last_status = None
        self._last_title = None
        self._last_can_next = None
        self._last_can_prev = None
        self._last_vol = None
        self._last_loop = None
        self._last_shuffle = None

        Gio.bus_get(Gio.BusType.SESSION, None, self._on_bus_acquired)

        # Periodically check for player state changes to update the OS UI
        GLib.timeout_add(500, self._sync_player_state)
        self._app.connect("notify::active-window", self._update_props)

    def _on_bus_acquired(self, _source, res):
        try:
            self._con = Gio.bus_get_finish(res)
            Gio.bus_own_name_on_connection(
                self._con, self._bus_name, Gio.BusNameOwnerFlags.NONE, None, None
            )

            node_info = Gio.DBusNodeInfo.new_for_xml(INTERFACE)
            for interface in node_info.interfaces:
                self._con.register_object(
                    object_path=self._path,
                    interface_info=interface,
                    method_call_closure=self._on_method_call,
                    get_property_closure=self._on_get_property,
                    set_property_closure=self._on_set_property,
                )
        except Exception as e:
            print(f"MPRIS Bus Error: {e}")

    def emit_properties_changed(self, interface, changed_properties):
        if not self._con:
            return

        self._con.emit_signal(
            None,
            self._path,
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (interface, changed_properties, [])),
        )

    def _update_props(self, *args):
        """Notifies D-Bus that properties have changed when the window switches."""
        if not self._con:
            return

        self.emit_properties_changed(
            "org.mpris.MediaPlayer2",
            {
                "Identity": GLib.Variant("s", "Cine"),
                "DesktopEntry": GLib.Variant("s", APP_ID),
            },
        )

        if self.player:
            status = "Paused" if self.player.pause else "Playing"
            title = getattr(self.player, "media_title") or _("Unknown title")
            loop = self._get_loop_status()

            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {
                    "PlaybackStatus": GLib.Variant("s", status),
                    "LoopStatus": GLib.Variant("s", loop),
                    "Metadata": self._get_metadata_variant(title),
                    "CanPlay": GLib.Variant("b", True),
                    "CanPause": GLib.Variant("b", True),
                    "CanSeek": GLib.Variant("b", True),
                    "CanControl": GLib.Variant("b", True),
                },
            )

    @property
    def player(self):
        win = self._app.get_active_window()
        return getattr(win, "mpv", None) if win else None

    @property
    def can_go_prev(self):
        win = self._app.get_active_window()
        return getattr(win, "can_go_prev", False) if win else False

    @property
    def can_go_next(self):
        win = self._app.get_active_window()
        return getattr(win, "can_go_next", False) if win else False

    def _get_loop_status(self):
        p = self.player
        if not p:
            return "None"

        # mpv loop-playlist can be 'inf', 'no', or a number
        loop_playlist = getattr(p, "loop_playlist", "inf")
        loop_file = getattr(p, "loop_file", "inf")

        if loop_file == "inf":
            return "Track"
        if loop_playlist == "inf":
            return "Playlist"
        return "None"

    def _sync_player_state(self):
        """Checks if mpv state changed and notifies D-Bus."""
        p = self.player
        if not p or not self._con:
            return True

        current_status = "Paused" if p.pause else "Playing"
        if current_status != self._last_status:
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {"PlaybackStatus": GLib.Variant("s", current_status)},
            )
            self._last_status = current_status

        current_vol = getattr(p, "volume", 0) / 100.0
        if self._last_vol is None or abs(current_vol - self._last_vol) > 0.01:
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {"Volume": GLib.Variant("d", float(current_vol))},
            )
            self._last_vol = current_vol

        current_title = getattr(p, "media_title") or _("Unknown title")
        if current_title != self._last_title:
            metadata = self._get_metadata_variant(current_title)
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player", {"Metadata": metadata}
            )
            self._last_title = current_title

        current_loop = self._get_loop_status()
        if current_loop != self._last_loop:
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {"LoopStatus": GLib.Variant("s", current_loop)},
            )
            self._last_loop = current_loop

        can_next = self.can_go_next
        if can_next != self._last_can_next:
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {"CanGoNext": GLib.Variant("b", can_next)},
            )
            self._last_can_next = can_next

        can_prev = self.can_go_prev
        if can_prev != self._last_can_prev:
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {"CanGoPrevious": GLib.Variant("b", can_prev)},
            )
            self._last_can_prev = can_prev

        current_shuffle = getattr(p, "_shuffle", False)
        if current_shuffle != self._last_shuffle:
            self.emit_properties_changed(
                "org.mpris.MediaPlayer2.Player",
                {"Shuffle": GLib.Variant("b", current_shuffle)},
            )
            self._last_shuffle = current_shuffle

        return True

    def _get_metadata_variant(self, title):
        """Constructs the MPRIS Metadata dictionary."""
        p = self.player
        raw_duration = getattr(p, "duration", 0) or 0
        duration = int(raw_duration * 1_000_000)

        metadata = {
            "mpris:trackid": GLib.Variant("o", "/org/mpris/MediaPlayer2/Track/0"),
            "xesam:title": GLib.Variant("s", str(title)),
            "mpris:length": GLib.Variant("x", duration),
        }

        return GLib.Variant("a{sv}", metadata)

    def _on_method_call(
        self, _con, _sender, _path, interface, method, params, invocation
    ):
        GLib.idle_add(self._handle_method, method, params)
        invocation.return_value(None)

    def _handle_method(self, method, params):
        p = self.player
        if not p:
            return

        if method == "PlayPause":
            p.pause = not p.pause
        elif method == "Pause":
            p.pause = True
        elif method == "Play":
            p.pause = False
        elif method == "Previous":
            win = self._app.get_active_window()
            if win:
                win._on_previous_clicked(win)  # type: ignore
        elif method == "Next":
            win = self._app.get_active_window()
            if win:
                win._on_next_clicked(win)  # type: ignore
        elif method == "Stop":
            p.stop()
        elif method == "Seek":
            offset_usec = params.get_child_value(0).get_int64()
            current_pos = getattr(p, "time_pos", 0) or 0
            p.time_pos = current_pos + (offset_usec / 1_000_000.0)
            self._emit_seeked()
        elif method == "SetPosition":
            pos_usec = params.get_child_value(1).get_int64()
            p.time_pos = pos_usec / 1_000_000.0
            self._emit_seeked()
        elif method == "Raise":
            win = self._app.get_active_window()
            if win:
                win.present()
        elif method == "Quit":
            self._app.quit()

    def _emit_seeked(self):
        if not self._con or not self.player:
            return
        raw_pos = getattr(self.player, "time_pos", 0) or 0
        pos_usec = int(raw_pos * 1_000_000)
        self._con.emit_signal(
            None,
            self._path,
            "org.mpris.MediaPlayer2.Player",
            "Seeked",
            GLib.Variant("(x)", (pos_usec,)),
        )

    def _on_get_property(self, _con, _sender, _path, interface, prop):
        p = self.player

        if interface == "org.mpris.MediaPlayer2.Player":
            if prop == "CanGoPrevious":
                return GLib.Variant("b", self.can_go_prev)
            if prop == "CanGoNext":
                return GLib.Variant("b", self.can_go_next)
            if prop in ["CanPlay", "CanPause", "CanControl"]:
                return GLib.Variant("b", True)
            if prop == "Volume":
                vol = getattr(p, "volume", 0) / 100.0 if p else 0.0
                return GLib.Variant("d", float(vol))
            if prop == "PlaybackStatus":
                status = "Paused" if (p and p.pause) else "Playing"
                return GLib.Variant("s", status)
            if prop == "LoopStatus":
                return GLib.Variant("s", self._get_loop_status())
            if prop == "Position":
                raw_pos = getattr(p, "time_pos", 0) or 0
                pos = int(raw_pos * 1_000_000)
                return GLib.Variant("x", pos)
            if prop == "Metadata":
                title = getattr(p, "media_title") or _("Unknown title")
                return self._get_metadata_variant(title)
            if prop == "Shuffle":
                _shuffle = getattr(p, "_shuffle", False) if p else False
                return GLib.Variant("b", _shuffle)

        if interface == "org.mpris.MediaPlayer2":
            if prop == "Identity":
                return GLib.Variant("s", "Cine")
            if prop == "DesktopEntry":
                return GLib.Variant("s", APP_ID)
            if prop in ["CanQuit", "CanRaise"]:
                return GLib.Variant("b", True)
            if prop == "HasTrackList":
                return GLib.Variant("b", False)
            if prop in ["SupportedUriSchemes", "SupportedMimeTypes"]:
                return GLib.Variant("as", [])

        return None

    def _on_set_property(self, _con, _sender, _path, interface, prop, value):
        p = self.player
        if not p:
            return False

        if interface == "org.mpris.MediaPlayer2.Player":
            if prop == "Volume":
                new_vol = value.get_double()
                p.volume = new_vol * 100.0
                self.emit_properties_changed(
                    "org.mpris.MediaPlayer2.Player",
                    {"Volume": GLib.Variant("d", float(new_vol))},
                )
                return True

            if prop == "LoopStatus":
                new_loop = value.get_string()

                if new_loop == "None":
                    p.loop_playlist = "no"
                    p.loop_file = "no"
                elif new_loop == "Track":
                    p.loop_file = "inf"
                    p.loop_playlist = "no"
                elif new_loop == "Playlist":
                    p.loop_file = "no"
                    p.loop_playlist = "inf"

                self.emit_properties_changed(
                    "org.mpris.MediaPlayer2.Player",
                    {"LoopStatus": GLib.Variant("s", new_loop)},
                )
                return True

            if prop == "Shuffle":
                new_shuffle = value.get_boolean()
                p._shuffle = new_shuffle
                win = self._app.get_active_window()
                if win:
                    btn = win.playlist_shuffle_toggle_button  # type: ignore
                    btn.props.active = new_shuffle
                self.emit_properties_changed(
                    "org.mpris.MediaPlayer2.Player",
                    {"Shuffle": GLib.Variant("b", new_shuffle)},
                )
                return True

        return False
