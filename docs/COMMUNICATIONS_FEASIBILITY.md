# Communications feasibility — Milestone 1

## Options

| Option | Feasibility and maintenance | Policy and security | Decision |
| --- | --- | --- | --- |
| Isolated, unmodified Discord web view | Electron `WebContentsView` can display a separate session; login, attachments, and live behavior still require user testing. Discord may change or block embedded use. | Manual interaction only; no message API or delivery acknowledgment. Keep the view sandboxed and without preload. | Experimental right-hand display. |
| Official Discord client or browser | Existing workflow already uses external Discord. Deep links can open a channel, while clipboard or Dolphin handles files. | Lowest integration privilege. User confirms sends. | Required fallback and recommended dependable path until the experiment passes. |
| Vesktop/Vencord | Open-source Linux client may improve user experience, but it modifies the Discord client and is independently maintained. | Do not embed or depend on its modifications, internals, or session data. | Evaluate as a user-selected external client only. |
| Authorized Discord application or bot API | Bot can access only granted channels and permissions; a bot identity is not the user's normal account. | Requires explicit server authorization and secure credentials. No personal-account automation. | Future adapter, outside Milestone 1. |
| Replaceable adapter | Capabilities can distinguish manual navigation from API operations. | Unsupported operations fail explicitly. | Implemented now. |

Discord explicitly forbids automating normal user accounts outside its bot/OAuth API. User permission to send a message does not change that boundary. [Discord self-bot policy](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots). Electron recommends a sandboxed `WebContentsView` with Node integration disabled and context isolation enabled for remote content. [Electron security guidance](https://www.electronjs.org/docs/latest/tutorial/security), [WebContentsView API](https://www.electronjs.org/docs/latest/api/web-contents-view). [Vesktop source](https://github.com/Vencord/Vesktop).

## Experiment and evidence

The implementation loads `https://discord.com/channels/@me` in the isolated view and reports `loading`, `loaded`, or a main-frame load failure. An isolated Electron 39.8.10 probe and the full workspace both reached `loaded` under KDE with the XWayland launcher on 2026-11-22. The full workspace ran against a disposable `/tmp` database and Electron profile for 20 seconds. `loaded` means a page finished loading; it does not establish login, channel access, attachment, sending, or session persistence. The external button and validated channel link provide a fallback. The view cannot read messages, compose or send through an application API, subscribe to events, or confirm delivery.

| Check | Current status | Required manual verification |
| --- | --- | --- |
| Web view construction and local-app isolation | Separate sandboxed session with no preload was inspected from the Electron main process; static and adapter tests pass | Inspect the running window and confirm Discord cannot invoke local controls |
| Ordinary Discord page loading | `did-finish-load` observed in both isolated probe and full workspace under XWayland | User checks visible page and manual interaction |
| Authentication and session persistence | Unverified | User logs in, restarts app, checks session |
| Channel navigation and text composition/send | Unverified | User navigates and sends a harmless test message in an authorized test channel |
| Image attachment and KDE Wayland/XWayland behavior | Unverified | User attaches a fixture image and checks Discord's preview and final post |
| External channel-link fallback | Implemented with URL validation | Confirm target opens in official client or browser |

Do not use the live war server for automated tests. If the embedded view is blocked or unreliable, use external Discord and retain the local draft and staging workspace. A successful page load must never be treated as proof of message publication.
