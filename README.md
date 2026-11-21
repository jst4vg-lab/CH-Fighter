# Clan Hub Crea Manager

## Fedora desktop app

Install dependencies with `npm install`, `python3 -m venv .venv`, and `.venv/bin/pip install -r requirements-build.txt`. Fedora builds also need `rpm-build` and `libxcrypt-compat`. Build the installable RPM with `PATH="$PWD/.venv/bin:$PATH" npm run package:rpm`; find it in `release/`. Launch **Clan Hub Crea Manager** from KDE. The app starts and stops its local backend automatically.

On first launch, existing database and generated images are copied to `$XDG_DATA_HOME/clan-hub-crea-manager` (normally `~/.local/share/clan-hub-crea-manager`). The old data remains in place. Original crea remain untouched. The app asks for the original folder if its saved path is missing. Stop the old `ch-fighter.service` before using the desktop app.

`npm run desktop` runs an unpackaged desktop build for development. The browser development workflow below also serves the mobile companion.

The Linux desktop launcher uses XWayland (`--ozone-platform=x11`). A minimal source test showed Electron's native Wayland drag produced an empty external payload, while both single-file API forms and a two-file package delivered readable JPEGs under XWayland. A direct Hot drag from the real app also delivered readable files to XWayland and Wayland inspectors. **Discord still rejects Electron's direct drop on this system.** The folder control and clipboard send remain available while this receiver-specific incompatibility is investigated. Staging and the local backend remain unchanged by the display choice.

Local-first crea inventory, formatting, and gallery. The source collection must be at `Crea/` under this repository. It is read only. Repost and Misc folders are skipped.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm install
npm run build
.venv/bin/python server.py
```

Open `http://127.0.0.1:8765`. Click **Scan collection**, then choose and save a color for each creator. Formatting starts automatically. During frontend development, run `npm run dev` separately and open `http://127.0.0.1:5173`.

To keep the app running after closing a terminal, start it as a user service:

```sh
systemd-run --user --unit=ch-fighter --working-directory="$PWD" "$PWD/.venv/bin/python" "$PWD/server.py"
systemctl --user status ch-fighter.service
```

This transient service runs until stopped or the user session ends. Stop it with `systemctl --user stop ch-fighter.service`; run the start command again after logging in if needed.

Use **Settings** to change saved creator colors. The app regenerates that creator's formatted images while keeping the gallery available. **Fit full image** preserves the entire source over a blurred background; **Crop to fill** remains available per asset.

Settings also has a Show toggle for each creator. Turning it off hides that creator's crea from the gallery and Used Crea and removes them from visible totals. It does not delete assets or change saved staging packages.

The Settings gear is at the far left of the header. Brand icons are generated from the cropped bird master in `public/icons/`; rerun `python3 scripts/build_brand_assets.py` to rebuild favicon and PWA sizes. The image formatter uses the bundled Noto Sans Bold font and places readable type and BP labels in the bottom information bar.

Click gallery cards to toggle crea in the centered Hot row (up to ten); selecting an already staged card again removes it. Type a submission in Hot. Move the package to the bottom Reserve deck shelf or use the icon-only Send outbox to copy the whole Hot package as files. Click a Reserve deck to preview it, then activate it when needed. Copy submission text separately using the button in the text box. Confirm only after posting in Discord; confirmation marks assets used and replenishes Reserve packages. The Used Crea view can restore assets. Browser clipboard and Discord paste behavior need a real desktop test before relying on a combined paste.

In the Electron desktop app, Hot automatically mirrors its formatted JPEG copies into `$XDG_DATA_HOME/clan-hub-crea-manager/hot-staging/` (normally `~/.local/share/clan-hub-crea-manager/hot-staging/`). The folder keeps the same location and updates while the app runs, including when Hot is cleared. The folder icon opens it in Dolphin; select its images and drag them into Discord using Dolphin's native file transfer. Original crea remain untouched. Dragging a Hot card to Reserve moves the package inside Clan Hub. The desktop Send button copies all Hot JPEGs as files to the Framework clipboard through the FileTransfer portal. The phone Send button requests the same operation on the Framework. Confirm only after posting. Use **Used Crea → Undo last deployment** to recover if a confirmed submission fails; Undo is disabled after other staging or usage changes. Resize the app beside Discord as needed; the gallery uses fewer columns when narrow, and the Hot row can scroll sideways. Automatic clearing after a drop is not enabled.

Generated files are under ignored `data/` directories. Import can be rerun safely. The first pass reads the collection and stores metadata; image generation starts only after creator colors are set. The source collection is never renamed, overwritten, or deleted.

## Checks

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
npm test
npm run build
```

Native file dragging is implemented in Electron but direct Discord drops remain unverified. Mobile synchronization is implemented; Safari and installed Home Screen gesture behavior still need device verification.

## iPhone companion

Keep the Framework desktop app open. The app listens on loopback port `8765`; if that port is occupied, stop the other service before launching it. Connect the Framework and iPhone to the same Tailscale tailnet. Enable MagicDNS and HTTPS certificates for the tailnet, and enable Tailscale Serve for the Framework in the Tailscale admin console. Then on the Framework configure the private HTTPS proxy with `tailscale serve --bg 8765` (do **not** use Funnel). In desktop Settings → Mobile companion, check the displayed `https://<framework>.<tailnet>.ts.net/mobile` address and generate a five-minute pairing code. Open that address in Safari on the iPhone, enter the code, then use Share → Add to Home Screen. The address stays the same across desktop restarts. The phone works while the desktop app is open; when it closes, the home-screen app displays a disconnected state. Settings can disconnect all paired phones.

The phone shows the three-column gallery and two staging areas. Swipe horizontally to move between branch panels; scroll vertically within a branch. Type headings collapse and keep their state when switching branches. Search, branch, type, and creator filters sit below Reserve. Phone add/remove, submission editing, Reserve transfer, activation, and Hot confirmation use the same SQLite backend as desktop; the persistent Hot folder follows within about one second. The phone cannot import, edit creator settings, browse Used Crea, or access original source images. The mobile shell is cached for offline display; asset data and staging mutations require a live connection. Tailscale Serve and HTTPS must be configured on the Framework before phone access works.

The package clipboard helper requires the host Python 3 installation to provide PySide6 and PyGObject/Gio, and uses XWayland for KDE/Flatpak file paste. On the phone, tap Send once to copy all Hot JPEGs to the Framework clipboard. After clipboard success, the button changes to a check; paste into Discord, then tap the same button again to mark that package used and clear Hot. A failed clipboard request or a changed Hot package leaves staging intact and requires another copy. If a confirmed submission fails, use **Used Crea → Undo last deployment** on desktop while no later staging changes have occurred. Hot thumbnails use two taps for removal; the first tap dims the card and shows a trash icon. Hold a Hot thumbnail for about a quarter second, then drag it onto Reserve to move the whole package. Hold a layered Reserve deck and drag it to Hot to activate it; an existing Hot package swaps into Reserve. Release elsewhere to cancel without changing staging. Tap a Reserve deck to preview it.
