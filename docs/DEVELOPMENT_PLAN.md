# Development plan

The desktop packaging milestone wraps the existing React UI in Electron, bundles the Python backend, and installs a Fedora RPM. Verify KDE Wayland startup and data migration before the native Discord drag milestone.

1. Current: inventory, safe import, image formatting, creator colors, and responsive gallery.
2. Current: Hot and Reserve staging, manual clipboard send outbox, Used Crea, and replenishment.
3. Native Electron file dragging is implemented behind a package-ID bridge with read-only Flatpak document portal export, manual confirmation, and transactional Undo. A persistent Hot folder mirrors formatted copies for Dolphin's working native file transfer. The Linux launcher forces XWayland after diagnostics found an empty native-Wayland payload; single-file and multi-file XWayland transfers reached diagnostic receivers. Discord still rejects direct Electron drops, including a minimal host-path drag. Investigate Electron's `copyLink` action and Flatpak FileTransfer compatibility before claiming direct Discord deployment or enabling automatic clearing.
4. Add authenticated mobile synchronization against the existing authoritative package state.
5. Profile large-library behavior and optimize measured bottlenecks.

Mobile companion implemented as an authenticated private Tailscale web app while desktop is open. Complete live iPhone Safari, Tailscale Serve, and Dolphin mirror verification before claiming end-to-end mobile operation.

Mobile touch interaction overhaul implemented in the React build: Embla branch slides, three-column collapsible type sections, layered Reserve decks, and hold-to-drag package moves. The Hot-to-Reserve backend action now accepts an expected package ID to reject a stale phone gesture. Verify finger tracking, vertical and diagonal scrolling, cancellation, disconnection, and Home Screen behavior on an iPhone before calling this milestone field-tested.

Mobile Send now follows desktop's two-step clipboard and confirmation flow. The phone arms Confirm sent only after the Framework reports clipboard success; Hot changes or disconnection reset it. Backend confirmation checks the copied package and asset IDs in the same transaction that marks crea used and replenishes Reserve. Verify the full copy, paste, confirm, and undo sequence on the paired phone and desktop.
