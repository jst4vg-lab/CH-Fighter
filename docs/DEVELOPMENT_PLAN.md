# Development plan

## Milestone 2 status

The read-only provider, normalized event cache, custom desktop feed, local name-color preference, and host Crea Library setting are implemented. Live Discord permissions, message-content intent, role/member completeness, attachment rendering, and KDE behavior still require a configured bot and user testing. The outgoing provider remains disabled by default; a production write provider with transactional Used Crea transition is a later milestone. Focused Mode currently filters exact author IDs and direct reply references. Enhanced role gradients, richer reply previews, and complete event recovery after a long offline period remain future work.

An authorized write-bot provider now supports explicit, test-channel-only text, formatted files, and reply sends when separately configured. It records acknowledgment IDs but deliberately does not change Used Crea. Live test-channel behavior remains unverified until a write bot and channel are configured. The next milestone should connect an authorized production send to the existing deployment transaction only after its identity, permission, and recovery behavior are field-tested.

## Command Suite transition

Milestone 1 adds the capability-aware communications adapter, isolated manual Discord `WebContentsView` experiment with external fallback, resizable desktop workspace, and persistent local drafts and handoff states. Keep the Crea Manager and mobile companion operational. Live Discord login, attachment, send, session persistence, and KDE display checks require user testing; the view is not a message API. Milestone 2 should evaluate those results, then connect local handoff records to legacy staging confirmation in one transaction and introduce only authorized messaging capabilities where available. Do not add message parsing, AI agents, maps, or intelligence automation in Milestone 1.

The desktop packaging milestone wraps the existing React UI in Electron, bundles the Python backend, and installs a Fedora RPM. Verify KDE Wayland startup and data migration before the native Discord drag milestone.

1. Current: inventory, safe import, image formatting, creator colors, and responsive gallery.
2. Current: Hot and Reserve staging, manual clipboard send outbox, Used Crea, and replenishment.
3. Native Electron file dragging is implemented behind a package-ID bridge with read-only Flatpak document portal export, manual confirmation, and transactional Undo. A persistent Hot folder mirrors formatted copies for Dolphin's working native file transfer. The Linux launcher forces XWayland after diagnostics found an empty native-Wayland payload; single-file and multi-file XWayland transfers reached diagnostic receivers. Discord still rejects direct Electron drops, including a minimal host-path drag. Investigate Electron's `copyLink` action and Flatpak FileTransfer compatibility before claiming direct Discord deployment or enabling automatic clearing.
4. Add authenticated mobile synchronization against the existing authoritative package state.
5. Profile large-library behavior and optimize measured bottlenecks.

Mobile companion implemented as an authenticated private Tailscale web app while desktop is open. Complete live iPhone Safari, Tailscale Serve, and Dolphin mirror verification before claiming end-to-end mobile operation.

Mobile touch interaction overhaul implemented in the React build: Embla branch slides, three-column collapsible type sections, layered Reserve decks, and hold-to-drag package moves. The Hot-to-Reserve backend action now accepts an expected package ID to reject a stale phone gesture. Verify finger tracking, vertical and diagonal scrolling, cancellation, disconnection, and Home Screen behavior on an iPhone before calling this milestone field-tested.

Mobile Send now follows desktop's two-step clipboard and confirmation flow. The phone arms Confirm sent only after the Framework reports clipboard success; Hot changes or disconnection reset it. Backend confirmation checks the copied package and asset IDs in the same transaction that marks crea used and replenishes Reserve. Verify the full copy, paste, confirm, and undo sequence on the paired phone and desktop.

The connection profile milestone adds independent saved read and write selections, shared bot clients, and Discord status in desktop Settings. Validate each real bot's intents and channel permissions before enabling test delivery. Production delivery remains a separate milestone.

## Discord reply workflow

- Add a keyboard-accessible Reply action to each message. It should set the composer target and focus the text field. Show the target author's name and a short preview above the composer, with a clear action to cancel the reply.
- Persist a reply target as guild, channel, and message IDs alongside the draft. Keep the target on a failed or unverified send. Clear it after a confirmed send or explicit cancellation. Never reuse it in another destination.
- Render references in the feed using the loaded parent message when available. Add an authorized history lookup for unloaded parents, scoped to the active channel. Show a neutral unavailable state for deleted or inaccessible parents. Clicking the preview jumps to a loaded parent or opens its Discord link.
- At dispatch, validate the reply against the active bot destination and use the existing Discord message reference. Suppress author mentions by default. Reject deleted or cross-channel targets without sending a standalone message or changing Crea state.
- Test selection, cancellation, profile and channel switches, deleted parents, mention behavior, failed sends, and successful attachment replies using fixtures. Verify keyboard focus and viewport behavior in the desktop build.

Security remediation adds release gates for redacted secret scanning, dependency advisories, tests, and packaged artifact privacy. The local KDE and RPM builds use the patched Electron runtime. Live Discord, native clipboard transfer under the new runtime, and real iPhone/Tailscale flows require field verification before publication.
