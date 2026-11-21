# External drag diagnostic

This receiver does not alter the app's staging state or upload images. From the repository root, launch it on each display backend:

```sh
node_modules/.bin/electron diagnostics/drop-target.cjs --ozone-platform=wayland
node_modules/.bin/electron diagnostics/drop-target.cjs --ozone-platform=x11
```

The window title identifies Wayland or XWayland. Drop a formatted JPEG from Dolphin into each receiver, then drop the same JPEG from Hot Staging. Repeat with two JPEGs. Compare `dragoverTypes`, `dropTypes`, `fileCount`, names, sizes, `readable`, and `jpegSignature`. `Files` should be offered, the count should match the package, and every JPEG should be readable. A `text/uri-list` alone is insufficient if the receiver cannot read the files.

For a minimal source that excludes React, staging, and portal export, set `CH_DRAG_TEST_FILE` to the absolute path of a known-good formatted JPEG. Drag the two boxes separately: one uses Electron's `file` API form, the other `files: [file]`. Initially use the same host path that worked from Dolphin; then repeat with its document-portal path. Run the source with `--ozone-platform=wayland` and `--ozone-platform=x11` against a receiver on the matching backend. The source terminal logs `dragstart` IPC, the `startDrag()` call, any exception, and its return. A return does not prove a file was offered.

```sh
CH_DRAG_TEST_FILE=/absolute/path/to/formatted.jpg node_modules/.bin/electron diagnostics/native-drag.cjs --ozone-platform=wayland
```

To isolate host versus Flatpak portal paths, close the running Clan Hub app and launch a diagnostic instance from the repository root with one of these commands. Repeat with both display backends:

```sh
CH_DRAG_DIAGNOSTIC=1 CH_DRAG_PATH_MODE=host node_modules/.bin/electron . --ozone-platform=wayland
CH_DRAG_DIAGNOSTIC=1 CH_DRAG_PATH_MODE=portal node_modules/.bin/electron . --ozone-platform=wayland
```

Replace `wayland` with `x11` for XWayland. The main-process terminal prints path mode, file count, and sizes before `startDrag`; it does not print file contents or paths. The host mode will generally be inaccessible to Flatpak Discord, so use the diagnostic receiver to test its drag payload. The portal mode tests the paths intended for Flatpak Discord. A receiver result with zero files, a missing drop event, or unreadable data distinguishes payload/lifecycle, receiver protocol, and permission failures. Test a real Discord drop separately; browser receiver success does not prove Discord accepts the same protocol.

The receiver records any text or URI payload displayed by the browser. Treat reports as private because filenames or paths may appear. It does not transmit the report anywhere.
