# Architecture decisions

## 2026-11-23 — Read and write providers are independent

Use the existing authorized bot only for accessible incoming data. The outgoing interface remains disabled until a separately authorized sender exists. The renderer consumes normalized backend records, never Discord credentials or raw Gateway objects. Keep manual Discord handoff during migration.

## 2026-11-23 — Authorized test-channel write provider

Keep the provider disabled by default. When explicitly configured, a separate bot may send only to one test channel. Persist Discord acknowledgments separately from deployment records; test sends do not mark crea Used. Treat timeouts as unverified to avoid duplicate messages after an unknown outcome.

## 2026-11-23 — One active Crea Library source

Persist one absolute source path in SQLite. Validate candidates before applying them. Keep missing source records and staging references; relink moved files only when content matching is unambiguous. The Electron source JSON remains a first-run seed for older installations.

## 2026-11-22 — Incremental Command Suite

Preserve the Electron/React/Python/SQLite Crea Manager. Add bounded modules around it. Keep the backend authoritative for asset, staging, and draft state. The desktop starts with Crea left and Communications right; the existing mobile companion remains Crea focused.

## 2026-11-22 — Manual communications adapter

Use a capability-aware interface. The first adapter supports validated channel navigation only. Unsupported message retrieval, subscriptions, composition, attachments, sending, and delivery confirmation return explicit unsupported results. `WebContentsView` is an isolated display experiment; external Discord is the fallback. No self-bot or private user-token integration.

## 2026-11-22 — Local handoff records

Persist local drafts, asset IDs, channel links, and handoff status in SQLite. Require explicit user confirmation for `sent_confirmed`. Keep these records separate from legacy Hot deployment until a later milestone can link them in one transaction. Clipboard preparation and web-view load do not imply delivery.
