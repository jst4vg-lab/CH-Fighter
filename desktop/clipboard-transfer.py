"""Own a native XWayland file clipboard and its FileTransfer portal session."""
import os
import sys

from gi.repository import Gio, GLib
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

PORTAL = 'org.freedesktop.portal.Documents'
OBJECT = '/org/freedesktop/portal/documents'
INTERFACE = 'org.freedesktop.portal.FileTransfer'


def main(paths):
    if not paths or len(paths) > 10 or any(not os.path.isfile(path) for path in paths):
        raise ValueError('The Hot package contains an unavailable file')
    app = QApplication(['Clan Hub clipboard'])
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    reply = bus.call_sync(PORTAL, OBJECT, INTERFACE, 'StartTransfer',
                          GLib.Variant('(a{sv})', ({'autostop': GLib.Variant('b', False)},)),
                          GLib.VariantType('(s)'), Gio.DBusCallFlags.NONE, 5000, None)
    key = reply.unpack()[0]
    fds = []
    fd_list = Gio.UnixFDList.new()
    try:
        for path in paths:
            fd = os.open(path, os.O_RDONLY)
            fds.append(fd)
            fd_list.append(fd)
        bus.call_with_unix_fd_list_sync(
            PORTAL, OBJECT, INTERFACE, 'AddFiles',
            GLib.Variant('(saha{sv})', (key, list(range(len(fds))), {})),
            None, Gio.DBusCallFlags.NONE, 5000, fd_list, None)
    finally:
        for fd in fds:
            os.close(fd)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path) for path in paths])
    mime.setData('application/vnd.portal.filetransfer', key.encode())
    app.clipboard().setMimeData(mime)
    print('READY', len(paths), flush=True)
    app.exec()


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print('ERROR', str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
