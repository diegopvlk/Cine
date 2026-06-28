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
import mpv
from gettext import gettext as _

gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, Gio, GLib


APP_ID = "io.github.diegopvlk.Cine"
MEDIAPLAYER2_PLAYER = "org.mpris.MediaPlayer2.Player"

# some gnome extensions can spam properties which can cause frame drops
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
        <property name='PlaybackStatus' type='s' access='read'/>
        <property name='Metadata' type='a{sv}' access='read'/>
        <property name='CanSeek' type='b' access='read'/>
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
    def __init__(self, app: Adw.Application) -> None:
        self._app = app
        self._bus_name = f"org.mpris.MediaPlayer2.{APP_ID}"
        self._path = "/org/mpris/MediaPlayer2"
        self._con = None

        Gio.bus_get(Gio.BusType.SESSION, None, self._on_bus_acquired)

        self._app.connect("notify::active-window", self._update_props)

    def _on_bus_acquired(self, _source, res):
        def register():
            try:
                self._con = Gio.bus_get_finish(res)
                Gio.bus_own_name_on_connection(
                    self._con, self._bus_name, Gio.BusNameOwnerFlags.NONE, None, None
                )

                node_info = Gio.DBusNodeInfo.new_for_xml(INTERFACE)
                for interface in node_info.interfaces:
                    self._con.register_object_with_closures2(
                        object_path=self._path,
                        interface_info=interface,
                        method_call_closure=self._on_method_call,
                        get_property_closure=self._on_get_property,
                        set_property_closure=self._on_set_property,
                    )
            except Exception as e:
                print(f"MPRIS Bus Error: {e}")

        # Without idle_add some gnome mpris extensions can freeze the
        # whole shell for about a minute. Not unique to cine, it can also
        # happen with other players that uses mpris.
        GLib.idle_add(register)

    def _emit_props_changed(self, changed_props):
        if not self._con:
            return

        self._con.emit_signal(
            None,
            self._path,
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (MEDIAPLAYER2_PLAYER, changed_props, [])),
        )

    def _update_props(self, *args):
        """Notifies D-Bus that properties have changed."""
        if not self._con:
            return

        self._emit_props_changed(
            {
                "Identity": GLib.Variant("s", _("Cine")),
                "DesktopEntry": GLib.Variant("s", APP_ID),
            },
        )

        if self._mpv:
            status = "Paused" if self._mpv.pause else "Playing"
            vol = self._mpv.volume
            loop = self._get_loop_status()

            self._emit_props_changed(
                {
                    "PlaybackStatus": GLib.Variant("s", status),
                    "LoopStatus": GLib.Variant("s", loop),
                    "Metadata": self._get_metadata_variant()
                    if not self._mpv.idle_active
                    else GLib.Variant("a{sv}", {}),
                    "CanPlay": GLib.Variant("b", True),
                    "CanPause": GLib.Variant("b", True),
                    "CanSeek": GLib.Variant("b", True),
                    "CanControl": GLib.Variant("b", True),
                    "Volume": GLib.Variant("d", float(vol / 100.0)),
                    "CanGoPrevious": GLib.Variant("b", self._can_go_prev),
                    "CanGoNext": GLib.Variant("b", self._can_go_next),
                    "Shuffle": GLib.Variant("b", self._shuffle),
                },
            )

    @property
    def _mpv(self):
        win = self._app.props.active_window
        return getattr(win, "mpv", None)

    @property
    def _can_go_prev(self):
        win = self._app.props.active_window
        return getattr(win, "can_go_prev", False)

    @property
    def _can_go_next(self):
        win = self._app.props.active_window
        return getattr(win, "can_go_next", False)

    @property
    def _shuffle(self):
        win = self._app.props.active_window
        return win.shuffle_toggle_btn.props.active if win else False  # type: ignore

    def _get_loop_status(self):
        try:
            p = self._mpv
            if not p:
                return "None"

            # mpv loop-playlist can be 'inf', 'no', or a number
            loop_playlist = getattr(p, "loop_playlist", "no")
            loop_file = getattr(p, "loop_file", "no")

            if loop_file == "inf":
                return "Track"
            if loop_playlist == "inf":
                return "Playlist"
        except mpv.ShutdownError:
            pass

        return "None"

    def _update_play_pause(self, paused):
        status = "Paused" if paused else "Playing"
        self._emit_props_changed({"PlaybackStatus": GLib.Variant("s", status)})

    def _update_volume(self, value):
        vol = value / 100.0
        self._emit_props_changed({"Volume": GLib.Variant("d", float(vol))})

    def _update_metadata(self):
        metadata = self._get_metadata_variant()
        self._emit_props_changed({"Metadata": metadata})

    def _update_loop(self):
        current_loop = self._get_loop_status()
        self._emit_props_changed({"LoopStatus": GLib.Variant("s", current_loop)})

    def _update_can_prev_next(self, can_prev, can_next):
        self._emit_props_changed({"CanGoPrevious": GLib.Variant("b", can_prev)})
        self._emit_props_changed({"CanGoNext": GLib.Variant("b", can_next)})

    def _update_shuffle(self, shuffle_active):
        self._emit_props_changed({"Shuffle": GLib.Variant("b", shuffle_active)})

    def _get_metadata_variant(self):
        """Constructs the MPRIS Metadata dictionary."""

        metadata = {}

        try:
            duration = getattr(self._mpv, "duration", 0)
            if duration is None:
                duration = 0

            metadata = {
                "mpris:trackid": GLib.Variant("o", "/org/mpris/MediaPlayer2/Track/0"),
                "mpris:length": GLib.Variant("x", int(duration * 1_000_000)),
            }

            win = self._app.props.active_window
            window_title = win.props.title if win else None
            title = window_title or getattr(self._mpv, "media_title", None)

            if title:
                metadata["xesam:title"] = GLib.Variant("s", str(title))

            md = self._mpv.metadata if self._mpv else {}

            if artist := (md or {}).get("artist"):
                metadata["xesam:artist"] = GLib.Variant("as", [str(artist)])
        except mpv.ShutdownError:
            pass

        return GLib.Variant("a{sv}", metadata)

    def _on_method_call(
        self, _con, _sender, _path, interface, method, params, invocation
    ):
        GLib.idle_add(self._handle_method, method, params)
        invocation.return_value(None)

    def _handle_method(self, method, params):
        try:
            p = self._mpv
            if not p:
                return

            if method == "PlayPause":
                p.pause = not p.pause
            elif method == "Pause":
                p.pause = True
            elif method == "Play":
                p.pause = False
            elif method == "Previous":
                win = self._app.props.active_window
                if win and win.can_go_prev:  # type: ignore
                    win._on_previous_clicked(win)  # type: ignore
            elif method == "Next":
                win = self._app.props.active_window
                if win and win.can_go_next:  # type: ignore
                    win._on_next_clicked(win)  # type: ignore
            elif method == "Stop":
                p.stop()
                self._update_props()
            elif method == "Seek":
                offset_usec = params.get_child_value(0).get_int64()
                current_pos = getattr(p, "time_pos", 0)
                p.time_pos = current_pos + (offset_usec / 1_000_000.0)
                self._emit_seeked()
            elif method == "SetPosition":
                pos_usec = params.get_child_value(1).get_int64()
                p.time_pos = pos_usec / 1_000_000.0
                self._emit_seeked()
            elif method == "Raise":
                win = self._app.props.active_window
                if win:
                    win.present()
            elif method == "Quit":
                self._app.quit()
        except mpv.ShutdownError:
            pass

    def _emit_seeked(self):
        try:
            if not self._con or not self._mpv:
                return
            raw_pos = getattr(self._mpv, "time_pos", 0)
            if raw_pos is None:
                raw_pos = 0
            pos_usec = int(raw_pos * 1_000_000)
            self._con.emit_signal(
                None,
                self._path,
                MEDIAPLAYER2_PLAYER,
                "Seeked",
                GLib.Variant("(x)", (pos_usec,)),
            )
        except mpv.ShutdownError:
            pass

    def _on_get_property(self, _con, _sender, _path, interface, prop):
        try:
            p = self._mpv

            if interface == MEDIAPLAYER2_PLAYER:
                if prop == "CanGoPrevious":
                    return GLib.Variant("b", self._can_go_prev)
                elif prop == "CanGoNext":
                    return GLib.Variant("b", self._can_go_next)
                elif prop in ["CanPlay", "CanPause", "CanControl", "CanSeek"]:
                    return GLib.Variant("b", True)
                elif prop == "Volume":
                    vol = getattr(p, "volume") / 100.0 if p else 0.0
                    return GLib.Variant("d", float(vol))
                elif prop == "PlaybackStatus":
                    status = "Paused" if (p and p.pause) else "Playing"
                    return GLib.Variant("s", status)
                elif prop == "LoopStatus":
                    return GLib.Variant("s", self._get_loop_status())
                elif prop == "Position":
                    raw_pos = getattr(p, "time_pos", 0)
                    if raw_pos is None:
                        raw_pos = 0
                    pos = int(raw_pos * 1_000_000)
                    return GLib.Variant("x", pos)
                elif prop == "Metadata":
                    return self._get_metadata_variant()
                elif prop == "Shuffle":
                    return GLib.Variant("b", self._shuffle)

            elif interface == "org.mpris.MediaPlayer2":
                if prop == "Identity":
                    return GLib.Variant("s", _("Cine"))
                elif prop == "DesktopEntry":
                    return GLib.Variant("s", APP_ID)
                elif prop in ["CanQuit", "CanRaise"]:
                    return GLib.Variant("b", True)
                elif prop == "HasTrackList":
                    return GLib.Variant("b", False)
                elif prop in ["SupportedUriSchemes", "SupportedMimeTypes"]:
                    return GLib.Variant("as", [])
        except mpv.ShutdownError:
            pass

        return None

    def _on_set_property(self, _con, _sender, _path, interface, prop, value):
        try:
            p = self._mpv
            if not p:
                return False

            if interface == MEDIAPLAYER2_PLAYER:
                if prop == "Volume":
                    new_vol = value.get_double()
                    p.volume = new_vol * 100.0
                    self._emit_props_changed(
                        {"Volume": GLib.Variant("d", float(new_vol))}
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

                    self._emit_props_changed(
                        {"LoopStatus": GLib.Variant("s", new_loop)}
                    )
                    return True

                if prop == "Shuffle":
                    new_shuffle = value.get_boolean()
                    p._shuffle = new_shuffle
                    win = self._app.props.active_window
                    if win:
                        btn = win.shuffle_toggle_btn  # type: ignore
                        btn.props.active = new_shuffle
                    self._emit_props_changed(
                        {"Shuffle": GLib.Variant("b", new_shuffle)}
                    )
                    return True
        except mpv.ShutdownError:
            pass

        return False
