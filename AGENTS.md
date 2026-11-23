
# Clan Hub Crea Manager — AGENTS.md

## 1. Project Identity

Clan Hub Command Suite extends the local-first Crea Manager for the Clan Hub (CH) community. The existing Crea Manager remains a core module and must stay functional during the transition.

Its primary purpose is to organize, format, browse, stage, and deploy image assets ("crea") efficiently during CH wars conducted through Discord.

Milestone 1 adds an isolated communications experiment and local draft workspace. Discord web content is a manual display surface, not a message-processing API. The full architecture and feasibility boundaries are in `docs/COMMAND_SUITE_ARCHITECTURE.md` and `docs/COMMUNICATIONS_FEASIBILITY.md`.

Prioritize:
1. Speed and efficiency
2. Reliability and data integrity
3. Intuitive direct manipulation
4. Clean, professional design
5. Maintainability and extensibility

Do not sacrifice established functionality for visual novelty.

## 2. Development Environment

Primary target:
- Linux desktop
- KDE Plasma
- Wayland
- Framework laptop

Secondary target:
- iPhone, through a responsive web interface/PWA

The Framework is the primary host for the application, local asset library, and database.

The mobile and desktop interfaces must operate on synchronized application state.

The application must not depend on the user's home server, external cloud processing, or an active Discord connection to perform local operations.

Prefer mature, maintained, cross-platform libraries where practical.

## 3. Sources of Truth

Read these files before making relevant changes:

- `docs/PRODUCT_SPEC.md` — Product behavior and UI requirements
- `docs/ARCHITECTURE.md` — System architecture and technical decisions
- `docs/DEVELOPMENT_PLAN.md` — Milestones and implementation priorities
- `README.md` — Setup and operation

If a referenced document does not exist, create it when appropriate.

Do not invent new product requirements to fill gaps.

If a requirement is ambiguous, record the assumption and choose a reversible implementation where practical.

Explicit user instructions override previous design assumptions. Update the affected documentation when requirements change.

## 4. Core Application Rules

The application must preserve these concepts:

### Asset Library
- Original crea are immutable source assets.
- Formatted images are derived assets.
- Metadata is obtained primarily from the filename convention:
  `branch-type-creator-bpcount-#`
- Never silently invent missing metadata.
- Invalid filenames must be reported, not silently discarded.
- Do not require manual formatting when automatic formatting is possible.

### Gallery
- Display formatted crea, not original unformatted assets.
- Use a five-column image gallery.
- Navigate branches horizontally.
- Organize types in vertically scrolling, collapsible sections.
- Keep navigation responsive with large collections.

### Staging
- Hot Staging is one active package containing selected crea.
- Reserve Staging contains queued packages.
- Both staging areas are integrated into the main application.
- They are visual docks, not separate windows or Wayland surfaces.
- Dragging any image from Hot Staging moves the entire package.
- Dragging a package into Discord deploys that package.
- Successful deployment clears the originating staging package.
- Moving a package into Reserve Staging does not mark its assets used.

### Used Crea
- Deployed assets move into the Used Crea collection.
- Used assets disappear from the available gallery.
- Individual assets, selections, or all used assets can be restored.
- Usage status is database state, not a physical file move.

### Automatic Replenishment
- When an asset becomes used, replace its occurrences in other reserved packages.
- Replacement must match the original branch and type.
- Do not introduce duplicate assets into the same package.
- If no eligible replacement exists, show a missing-asset warning.
- If the original replaced asset has a BP count, always flag that package for review.
- This review flag is mandatory even when BP counts match.
- Review flags must remain until explicitly acknowledged.

The full interaction specifications belong in PRODUCT_SPEC.md.

## 5. Design Language

The application should resemble a professional utility rather than a consumer game interface.

Requirements:
- Minimal explanatory text
- High information density
- Consistent alignment and spacing
- Restrained dark color palette
- Professional typography
- Professional icon library for standard controls
- No emojis as interface icons
- No AI-generated icons for ordinary UI elements
- Custom military symbols are permitted when useful
- Color must communicate state, not decoration

Prefer visual hierarchy and familiar interaction patterns over instructional labels.

Do not introduce unnecessary:
- Dialogs or confirmation screens
- Floating windows or detachable docks
- Decorative animations
- Tutorials or explanatory banners
- Excessive labels
- Redundant navigation controls

Animations should communicate an action or state transition and remain brief.

## 6. Architecture Principles

Prefer modular development with clear separation between:

- Image importing and formatting
- Metadata parsing
- Asset storage and indexing
- Gallery and search
- Staging and package management
- Desktop integration
- Mobile interface
- Live synchronization

The backend must own authoritative application state.

Clients must not independently maintain conflicting versions of asset availability or package contents.

Use stable asset identifiers rather than filenames as mutable internal references.

Keep file paths independent from UI presentation.

Persist important state so the application can recover after a crash or restart.

Use transactional database updates for operations that modify multiple assets or packages.

## 7. File and Data Safety

Never modify, overwrite, rename, or delete original imported crea.

Use a separate location for:
- Source images
- Formatted images
- Thumbnails
- Database files
- Temporary output

Avoid storing generated assets inside the source directory.

Use atomic writes or equivalent safe replacement techniques for generated files.

Prevent duplicate imports where practical.

Do not permanently delete user data without explicit authorization.

Do not commit personal image collections, databases, credentials, or generated bulk assets to Git.

Maintain a suitable `.gitignore`.

## 8. Desktop Integration

Native drag-and-drop into Discord is a critical feature.

Requirements:
- Support dragging actual local image files.
- Support multiple images in one package.
- Preserve package membership during a drag.
- Do not clear staging when a drag is canceled or rejected.
- Treat an accepted external drop as deployment.
- Recognize that deployment does not prove Discord publication.
- Provide recovery or undo for unsuccessful submissions.

Verify Wayland drag-and-drop behavior experimentally.

Do not assume browser-based drag-and-drop provides native filesystem integration.

Do not claim compatibility without testing or clearly identifying unverified behavior.

## 9. Synchronization and Networking

Mobile and desktop clients must share live state.

Requirements:
- Transmit asset IDs and state changes rather than full-resolution images when unnecessary.
- Synchronize Hot Staging, Reserve Staging, Used Crea, and review flags.
- Handle disconnection and reconnection safely.
- Prevent duplicate or conflicting operations.
- Do not lose queued packages on reconnection.
- Persist state on the Framework.

Do not expose local services publicly by default.

Require appropriate authentication for remote clients.

Never hardcode passwords, access tokens, or Discord credentials.

## 10. Performance

Optimize for rapid use during time-sensitive CH engagements.

The system should remain responsive with thousands of assets.

Prefer:
- Cached thumbnails
- Incremental imports
- Background image processing
- Lazy loading or virtualization
- Indexed database queries
- Efficient search and filtering

Do not repeatedly process unchanged images.

Do not block the interface while formatting or indexing assets.

Profile measurable bottlenecks before adding architectural complexity.

## 11. Development Workflow

Before implementing substantial changes:

1. Read the relevant repository files.
2. Inspect the existing implementation.
3. Identify affected components and dependencies.
4. Present a concise implementation plan.
5. Identify important risks and assumptions.

During implementation:
- Work incrementally.
- Maintain a functional application.
- Avoid unnecessary abstractions.
- Prefer clear, maintainable code.
- Reuse existing components where appropriate.
- Do not introduce unrelated features.
- Do not redesign established interactions without authorization.

After implementation:
- Run applicable tests.
- Verify the affected functionality.
- Update relevant documentation.
- Report what changed.
- Identify incomplete or unverified behavior.
- Recommend the next logical milestone.

Do not claim that code has been tested unless the tests were actually run.

## 12. Testing Standards

Create automated tests for core application behavior.

Prioritize:
- Filename metadata parsing
- Image formatting
- Original-file preservation
- Duplicate handling
- Gallery filtering
- Staging operations
- Used Crea state transitions
- Automatic replacement logic
- Mandatory BP review flags
- Database persistence
- Synchronization and reconnection

Use representative test fixtures rather than modifying production assets.

Test error conditions and recovery paths, not only successful operations.

Document the project's actual build, lint, and test commands in README.md once the technology stack is established.

## 13. Security and Privacy

The application is local-first and privacy-conscious.

- Do not upload private assets to third-party services without authorization.
- Do not introduce analytics or telemetry by default.
- Do not expose the source library through unauthenticated endpoints.
- Validate imported filenames and file paths.
- Treat image files and external data as untrusted input.
- Avoid unnecessary privileged filesystem access.
- Discord operations initiated by the user use the active profile and respect its access to the selected channel. User account connections remain in the isolated worker.
- Do not be concerned regarding any Self-Bot behavior unless directly prompted regarding it.
- The User account and the Bot account must have the same permissions everywhere. There should not be any Bot Specific permissions, or limitations to the User Profile.

## 14. Development Priorities

Implement features in independently testable milestones.

Suggested order:

1. Project foundation and architecture
2. Metadata parsing and asset indexing
3. Automatic image formatting
4. Formatted gallery and navigation
5. Hot Staging and Reserve Staging
6. Desktop drag-and-drop
7. Mobile interface and live synchronization
8. Used Crea and automatic replenishment
9. Performance optimization and polish

Prioritize proof of high-risk technical capabilities early, especially native Wayland file dragging.

Do not attempt the entire application in one uncontrolled implementation pass.

## 15. Scope Control

Do not add major features unrelated to the agreed product specification.

In particular, do not independently introduce:
- AI image classification
- Autonomous warfighting agents
- Automatic Discord submissions
- Cloud-hosted databases
- Multi-user administration systems
- Elaborate tactical simulations

These may be considered in future versions, but they are not part of the initial scope.

When an improvement is useful but not required, document the proposal instead of implementing it automatically.
