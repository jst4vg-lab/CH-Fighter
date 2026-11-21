# External drag investigation

## Verified from code and local checks

- The Hot card's `dragstart` handler calls `preventDefault()` and sends a token through the preload bridge. The main process verifies current package membership, resolves absolute paths under the formatted-image directory, checks that each is a file, and calls Electron `webContents.startDrag()` with `file` for one item or `files` for multiple. Submission text and the internal package ID are not put into that native file offer. Shift-drag uses an HTML5 custom package ID for movement inside Clan Hub.
- A drag may begin before asynchronous preparation finishes. In that case the renderer cancels the browser drag and displays a retry message; `startDrag()` is not called. The nested image element also has browser-default draggable behavior, but a bubbling `dragstart` on the Hot card is canceled when the native branch runs. Whether these events explain the reported green-plus cursor requires a real drag capture.
- Two actual formatted JPEGs were read through both host and Flatpak document-portal paths. Corresponding byte counts were 192608 and 273945, both paths contained identical bytes, and both had JPEG signatures. A previous check inside the Discord Flatpak also read an exported file. This verifies path readability, not an accepted drag payload.
- Electron's documented method calls `startDrag()` in response to `dragstart` through IPC. This implementation follows that shape. The source-level implementation inside the packaged Electron binary and its Wayland MIME offer have not been observed.
- The diagnostic target launches on both native Wayland and XWayland. No physical drop into it has been performed in this investigation.

## Unverified comparison matrix

For each display backend (Wayland, XWayland), compare one and two JPEGs from Dolphin against Hot Staging using host and portal mode. Record receiver `dragoverTypes`, `dropTypes`, `fileCount`, names, sizes, `readable`, and `jpegSignature`, then repeat the actual drop into Discord. This requires a physical pointer drag or a trusted desktop input harness. A green-plus cursor is not evidence of transferred files.

## Minimal source comparison, 2026-11-21

The user dragged from a minimal standalone Electron source into the same inspector. Its drag handler directly calls `preventDefault()` and sends synchronous IPC to `startDrag()`; it uses no React, staging, asynchronous preparation, or portal logic.

| Source backend and path | API form | Inspector result |
| --- | --- | --- |
| Native Wayland, host JPEG | `file` | No file received |
| Native Wayland, host JPEG | `files: [file]` | No file received |
| XWayland, host JPEG | `file` | `Files`, one readable 223324-byte JPEG, `ff d8 ff` |
| XWayland, host JPEG | `files: [file]` | `Files`, one readable 223324-byte JPEG, `ff d8 ff` |
| XWayland, portal path to same JPEG | `file` | `Files`, one readable 223324-byte JPEG, `ff d8 ff` |
| XWayland, portal path to same JPEG | `files: [file]` | `Files`, one readable 223324-byte JPEG, `ff d8 ff` |
| XWayland, two portal-path JPEGs | `files: [file1, file2]` | `Files`, two readable JPEGs of 223324 and 263492 bytes, both `ff d8 ff` |

The main-process log confirms both API forms entered `startDrag()` and returned without throwing on both backends. The same JPEG had already arrived from Dolphin. This isolates the observed empty payload to Electron's native Wayland drag transfer on this KDE system, rather than React, asynchronous staging preparation, an unreadable JPEG, or Flatpak portal substitution. The XWayland receiver succeeded with both host and portal paths. This does not establish which internal Electron, Chromium, or Wayland component loses the offer; no protocol trace was captured.

The smallest production correction is to launch Electron with `--ozone-platform=x11` on Linux. The real Clan Hub window was restarted under XWayland without changing staging. Its direct Hot drag delivered readable JPEGs to the XWayland inspector; a two-file observation contained both `Files` items, with valid JPEG signatures. The KDE launcher and rebuilt RPM desktop entry both contain `--ozone-platform=x11`. A cross-backend drop into a native Wayland receiver and an actual Discord drop remain separate checks. The diagnostic path override works only with `CH_DRAG_DIAGNOSTIC=1` and leaves normal path selection unchanged.

## Discord comparison

- The user confirmed the XWayland Clan Hub drag delivered two readable JPEGs to a native Wayland inspector. Discord nonetheless rejected both a one-file and two-file direct drag from Clan Hub.
- Dolphin could submit the formatted JPEG from its normal folder to Discord, but a drag from its manually exported portal-path copy was rejected. Discord can read that portal path through its sandbox in a direct file-read check. The static document export therefore does not reproduce Dolphin's working transfer.
- A minimal XWayland Electron drag from the *host* path, with no staging or portal substitution, was also rejected by Discord. This eliminates React, the package token, and static portal substitution as sufficient explanations for Discord's rejection.
- Electron 39.8.10's `drag_util_views.cc` offers `DRAG_COPY | DRAG_LINK` for `startDrag()`. The XWayland inspector observed `effectAllowed: "copyLink"` from the minimal Electron source and `"copy"` from a Dolphin drag. Electron's issue #15361 reports Discord rejecting that action set. This is evidence of an action compatibility problem, although the exact decision inside proprietary Discord has not been observed.
- The Flatpak FileTransfer portal uses the `application/vnd.portal.filetransfer` MIME type to transfer permissions during drag and drop. Electron's `startDrag()` API exposes no custom MIME or action parameter. The static document export and FileTransfer protocol are distinct mechanisms.

No additional Flatpak filesystem permission or staging change was made. The XWayland launcher corrects the empty inspector payload; it does not by itself make Discord accept the drop. The existing Files button was corrected to open its ordinary temporary host folder instead of a manually exported portal folder. The user then opened that folder from Hot, dragged its JPEGs into Discord, and observed attachment previews. A read-only backend check afterward showed the Hot item still staged. The manually exported portal folder had failed in the prior comparison. Further work must establish whether the action set, FileTransfer MIME, or both are required by Discord for a direct Electron drag on this system.

Primary references: [Electron 39.8.10 drag implementation](https://raw.githubusercontent.com/electron/electron/v39.8.10/shell/browser/ui/drag_util_views.cc), [Electron issue describing Discord and `copyLink`](https://github.com/electron/electron/issues/15361), [Flatpak FileTransfer protocol](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.FileTransfer.html).
