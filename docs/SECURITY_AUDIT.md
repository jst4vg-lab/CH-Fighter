# Security audit

Reviewed 2026-11-23 at commit 3d6f6e7. This review covers local source, Git objects, configuration permissions, packaged resources, request handling, Electron boundaries, and public dependency advisory databases. Application code and credentials were left unchanged.

## Secret exposure assessment

- Scanned 119 tracked files and all 167 local Git blobs, including four commits reachable through refs or reflogs. Used credential-format patterns and exact matching against the two distinct populated local Discord credential values. No live credential matches or private key blocks were found in those files or Git objects.
- The project-root .env and installed desktop data .env contain Discord credentials. Both are ignored by Git and have mode 0600. Keep them private. Their values were never included in this report or audit output.
- Inspected 189 files in the unpacked package resources. No known local credential matches or packaged .env, private-key, or SQLite filenames were found. The existing RPM payload contained no exact matches to the local credentials checked.
- The MagicDNS-looking strings found in Git are test fixtures in tests/test_mobile_auth.py. These are not authentication credentials.
- app.sqlite contains private drafts, deployment records, team memberships, and mobile session hashes. The databases have mode 0644 and application data directories have mode 0755. The current home directory is mode 0700, which protects them from other local users through that path. Use private directory and file modes when installing or backing up elsewhere.
- No credential rotation is indicated by a confirmed repository leak in this review. This scan cannot establish whether credentials were exposed previously through another system or an artifact unavailable locally.

## Findings

### 1. High — Standalone backend accepts cross-origin mutations

server.py:61-69 treats local requests as trusted when CH_DESKTOP_SECRET is absent. The documented standalone launch has that configuration. POST handlers accept JSON regardless of Content-Type and skip Origin validation for the local route.

An isolated loopback test sent a text/plain POST with Origin https://untrusted.example to /api/communications/test-mode. The backend returned HTTP 200 and changed the fixture preference. An untrusted website able to reach loopback could exploit this to change settings or invoke sends and asset operations. Actual browser access can also depend on the browser's local-network protections. No browser bypass was tested.

The Electron launch sets a per-launch secret, which prevents the demonstrated request without that header.

Recommended correction: require trusted Origin or an appropriate anti-CSRF token for state changes in every launch mode, validate JSON Content-Type, and reject ambiguous Host values. Preserve explicit support for the development frontend and paired mobile origin.

### 2. High — Dependency advisories affect the packaged runtime and build tools

The public npm audit returned eight affected dependency entries, two high and six moderate. These are package entries, not eight independently exploitable application bugs.

- Electron 39.8.10 is flagged high by the registry. Electron is declared as a development dependency but its executable is the shipped runtime. Review advisory prerequisites and upgrade to a maintained patched version.
- extract-zip is flagged high for symlink traversal and arbitrary writes when extracting a malicious archive. This primarily affects installation and packaging.
- minimatch is flagged moderate for denial of service. Its advisory propagates through electron-builder and related packaging packages.
- OSV checked 27 installed Python package/version combinations. It reported advisories for pip 26.0.1 in the normal build environment. pip is installation tooling. No advisories were returned for the other checked package/version combinations.

Sources checked:
- https://github.com/electron/electron/security/advisories/GHSA-j84w-jfhq-vhvj
- https://github.com/advisories/GHSA-jmr9-qjv8-65gv
- https://github.com/advisories/GHSA-58qw-9mgm-455v

Recommended correction: update and audit the runtime and toolchain, test packaging and native integration, and record patched versions. npm's suggested automatic fix includes incompatible version changes and should not be applied blindly.

### 3. Medium — Electron trusts a broader session than intended

desktop/main.cjs:290-308 enables sandboxing and context isolation and disables Node integration. However, it lacks a navigation allowlist for the main window and injects X-CH-Desktop into all matching local requests in the window's session without checking the initiating WebContents or frame.

index.html and server responses do not set a Content Security Policy. The main session also lacks explicit permission-check and permission-request handlers. The removed Discord web view remains callable through preload IPC, increasing the code surface.

These weaknesses increase the impact of a future renderer injection or an unintended navigation. No working renderer injection or secret theft was found. Current React rendering escapes message text, and IPC methods validate sender origin.

Recommended correction: restrict main-frame navigation and redirects to the app origin, scope privileged header injection to the trusted renderer, add a production CSP and permission deny rules, and remove the obsolete embedded-view bridge.

Electron guidance: https://www.electronjs.org/docs/latest/tutorial/security

### 4. Medium — Mobile pairing has unlimited guesses

mobile_auth.py:21-32 uses a six-digit code valid for five minutes without a failed-attempt limit or rate limiting. A fixture test made 1,000 incorrect guesses and confirmed the code remained active.

The service is loopback-only and intended to be reached privately through Tailscale. An attacker would need access through that route or another local path. This reduces exposure but does not limit guesses once the endpoint is reachable.

Recommended correction: cap guesses, rate-limit pairing, invalidate exhausted codes, and synchronize code consumption across concurrent requests.

### 5. Medium — Request parsing permits avoidable resource exhaustion

server.py:92-95 checks only whether Content-Length exceeds one million. Negative values pass validation. Reading a negative length consumes the stream until EOF and can hold a handler open. Request bodies are read before authorization, and ThreadingHTTPServer has no configured body-read timeout or concurrency limit.

A client that can reach the service can occupy threads with incomplete bodies. This was established by code inspection; no load test was performed.

Recommended correction: reject invalid and negative lengths, authorize before reading the body, require supported media types, set socket timeouts, and bound concurrent operations.

### 6. Low — Ignore rules omit common secret backup names

.gitignore excludes .env but not .env.local, .env.backup, credentials.json, or private key filenames. git check-ignore confirmed those example names would be eligible for staging.

There is no confirmed leak from this omission. It makes a future accidental commit more likely.

Recommended correction: ignore local credential variants while retaining .env.example, add a standard secret scanner to commits or CI, and scan release staging directories before packaging.

### 7. Low — Remote media can contact arbitrary HTTPS origins

src/DiscordMessages.jsx:38-47 accepts any HTTPS image URL as a fallback when no Discord proxy URL is present. Loading that media reveals the viewer's network address to its host. Referrer suppression helps avoid disclosing the app URL but does not hide the connection.

Recommended correction: prefer Discord's proxied media, restrict automatic loads to approved CDN hosts, and make other remote media an explicit user action. Apply the same URL policy to avatars and attachments.

## Verification and limitations

No live Discord sends, reactions, or credential-validation requests were made. The request tests used an isolated database. Dependency queries sent package names and versions to the public npm and OSV services.

This is a source and local-artifact audit, not a penetration test or a guarantee that every secret format can be detected. It did not inspect remote-only Git refs, GitHub Actions secrets, issue comments, release attachments absent locally, other machines, or memory and crash dumps. Source collections, virtual environments, and dependency caches were excluded from exhaustive generic scanning. The packaged resources and RPM were checked as described above.

Suggested remediation order is standalone API request validation, runtime dependency upgrades, Electron hardening, pairing and request limits, then secret-scanning and release hygiene.

## Remediation implemented

The remediation adds CSRF protection, exact origin/authority checks, strict JSON framing, read timeouts, a 32-handler bound, synchronized pairing limits, app-owned private file modes, main-window navigation and permission restrictions, production CSP, main-frame-only desktop headers, and authenticated remote-media retrieval with DNS-pinned public HTTPS connections. The obsolete embedded view and bridge were removed.

Electron is updated to 45.4.1. electron-builder remains pinned to 26.18.0. Targeted minimatch 11.0.9 overrides address its two vulnerable dependency paths. Updating Electron also removed extract-zip from the dependency tree. npm now reports zero advisories. Both pinned Python requirement sets pass pip-audit. The normal pip installation is updated to 26.3.

Local and GitHub security gates use redacted Gitleaks scanning and advisory checks. Release scans reject private files and exact local credential matches. There are no advisory exceptions or secret suppressions for source fixtures.

Verification includes HTTP fixtures for the previously accepted cross-origin mutation, malformed framing, overload, request timeout, pairing limits and concurrency, private file modes, and DNS/redirect blocking. An Electron 45 fixture verifies production CSP, renderer initialization, CSRF calls, and scoped desktop-header injection.

Live Discord operations and real iPhone/Tailscale behavior require user verification. GitHub workflow execution requires pushing the workflow. Public release publishing remains a separate action.

Final verification passed 70 Python tests, six Node tests, the production frontend build, Electron runtime fixtures, packaged backend startup, and the release privacy gate. The rebuilt local desktop package and RPM contain no matches to the local credentials checked. Gitleaks found no source or history secrets. npm and both pinned Python dependency audits returned no known vulnerabilities. The RPM build used signature-verified Fedora compatibility tools extracted to a temporary directory.
