# Command Suite architecture — Milestone 1

## Milestone 2 additions

The Python backend now owns a read-only `discord.py` provider in `communications/incoming/discord_bot.py`. It normalizes messages, members, roles, attachments, embeds, reactions, and reply IDs; caches Gateway events; and exposes paginated channel history plus sequence-based event polling. Only channels in the configured guild are offered. A disabled outgoing provider explicitly returns `provider_unavailable`; production sending remains unavailable by default. `member_colors` stores local user-ID color overrides separately from provider configuration. The custom React feed is the default, and the isolated web view remains a manual fallback. Live bot access and KDE display behavior are unverified without user credentials and device testing.

The outgoing test provider is separate from the read bot. `communications/outgoing/discord_bot.py` connects only an authorized bot account and validates the configured test channel and permissions. `test_submissions.py` resolves formatted files and persists pending, confirmed, failed, or unverified outcomes in `workspace_test_sends`. Confirmed test sends store the actual Discord message and sender IDs without invoking the Crea Used transaction. Unknown outcomes cannot be retried automatically. The desktop composer shows the test destination and capability state; the provider is disabled by default. No live send was performed without a configured test bot.

`app_settings.library_source` holds the host's single active source path. Existing Electron source JSON or `CH_CREA_SOURCE` seeds that value when the database first opens. Import and formatting read the persisted path. A unique content-hash match can relink a moved asset while keeping its ID and usage state; ambiguous duplicates enter review. Missing storage skips scan/format and preserves records. Mobile continues to use backend asset endpoints.

## Current system audit

The installed desktop is Electron 39.8.10 on Fedora KDE. Its `BrowserWindow` loads a React 19/Vite 7 UI from the Python loopback server. The launcher forces XWayland (`--ozone-platform=x11`) because native Wayland file drags failed in the earlier receiver experiment. The renderer uses a sandboxed preload bridge. The standard-library Python HTTP server owns SQLite under `$XDG_DATA_HOME/clan-hub-crea-manager`; Pillow handles image formatting. Source crea remain read only. The iPhone PWA uses the same backend through paired private Tailscale HTTPS.

| Existing responsibility | Implementation | Milestone 1 treatment |
| --- | --- | --- |
| Import, metadata, formatting | `crea_core.py`, SQLite `assets`/`creators`, derived JPEGs | Preserve |
| Five-column desktop gallery and details | `src/main.jsx`, `src/style.css` | Preserve inside the left region |
| Hot, Reserve, Used and recovery | `staging.py`, `src/Staging.jsx`, `packages`, `package_items`, `deployments` | Preserve existing transactions and manual confirmation |
| Mobile carousel, staging, clipboard | `src/Mobile.jsx`, pairing and mobile API allowlist | Preserve; no Command Suite controls on phone yet |
| Discord handoff | Native drag experiment, persistent Hot folder, FileTransfer clipboard | Preserve; external Discord remains the reliable fallback |
| Tests and builds | Python unittest, Node test runner, Vite, PyInstaller, electron-builder RPM | Extend |

## Module boundaries

The shared backend remains authoritative. New bounded modules are Communications, Crea Manager, Engagement Tracking, Planning, Operations, Intelligence, and Shared Persistence and Events. Only Communications and a small local workspace are implemented now. Future modules consume stable asset IDs and backend events or API snapshots; they do not read the Discord page or keep independent authoritative package state. The existing Crea tables and file layout remain in place.

`desktop/communications.cjs` is the replaceable communications adapter boundary. It reports support separately for channel navigation, message retrieval, real-time subscriptions, composition, file attachment, sending, and delivery confirmation. The current manual adapter supports only validated Discord channel navigation. Every other call returns `{ok:false,code:'unsupported'}`. A future authorized bot adapter may implement more capabilities without changing consumers. `WebContentsView` is a display surface, not a message API.

The desktop shell puts Crea on the left and Communications on the right. It keeps the existing gallery component mounted. A narrow window switches between regions for usability. The local draft editor stores text, selected asset IDs, a validated channel URL, and a status in SQLite independently of Discord connectivity. New drafts retain previous records in `workspace_drafts`; `GET /api/workspace/drafts` exposes recent history. The new desktop-only endpoints are `GET/POST /api/workspace/draft`, `GET /api/workspace/drafts`, `POST /api/workspace/draft/transition`, and `POST /api/workspace/draft/new`. Mobile's remote allowlist excludes them.

## Handoff states and safety

The local sequence is `draft → prepared → handoff_pending → sent_confirmed` or `failed_unverified`. A failed handoff can return to editing or retry. `sent_confirmed` requires an explicit user action; an embedded page loading or a file being copied never implies publication. This local record does not yet change Used Crea. The existing Hot confirmation remains the only path that marks assets used and triggers Reserve replenishment. This separation avoids a second, unsynchronized deployment transaction during the transition. A later milestone can unify handoff records and staging confirmation transactionally.

The Discord view runs in `persist:ch-command-discord`, separate from the local app session. It has no preload, Node integration, or privileged IPC; sandbox, context isolation, and web security remain enabled. Main-frame navigation is limited to `discord.com`; other HTTPS links open externally. Local loopback and file requests from the Discord session are blocked. The desktop secret header is registered only on the local app session. No Discord DOM inspection, script injection, token access, or user-account API calls are used.

## Provider package layout

`communications/core/` owns normalized messages, users, channels, and conversion from Discord objects. `communications/incoming/` owns read-provider contracts and the read bot. `communications/outgoing/` owns write-provider contracts, the disabled provider, and the authorized test-channel bot. `test_submissions.py` remains the application-level transaction and acknowledgment record. `server.py` selects each provider independently; the frontend API shape is unchanged.

### Connection management

The backend now starts `ConnectionManager` after SQLite initialization. The manager loads TOML profiles and saved direction selections, resolves credential references from the backend environment, and owns one worker per selected profile. The Discord connection owns client initialization, authentication, and shutdown. Incoming normalization and outgoing delivery use that client. Inactive connections are stopped and their events are excluded from snapshots. The feed uses a read generation to discard responses from a previous connection.

Add a provider by extending profile validation and the manager's connection factory, then supplying the corresponding incoming and outgoing adapters. The renderer consumes normalized records and status only. The current implementation uses one Python dependency for authorized bots. A provider that requires incompatible dependencies would need an adapter across a process boundary.
