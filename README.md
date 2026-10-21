# LINE Scheduler

LINE has stickers for every possible mood. A “send later” button? Apparently that was asking too much.

So I built one: a private front end on **ChatGPT Sites**, with a small **AWS serverless sender** behind it. Pick a chat, write a message or drop in a file, choose a time, and close the laptop. It sends from your personal LINE account to your existing conversations.

## What it does

- Send now or schedule for later, with an explicit time zone.
- Drag and drop images, text files, or other documents: up to five files, 20 MiB each.
- Send text and each attachment as separate messages; cancel pending jobs and review receipts.
- Require LINE Letter Sealing. No silent downgrade and no automatic resend after an uncertain outcome.

Images arrive as **file attachments**, not native photo bubbles. Native image sending is disabled because of an encryption flaw in the inherited format. Message order within a batch is not guaranteed.

## Where everything lives

| Component | Job |
| --- | --- |
| **ChatGPT Sites** | Private interface, ChatGPT sign-in, and a server-side API relay |
| **AWS Lambda** | Scheduling API and the Go LINE sender, running only when invoked |
| **EventBridge Scheduler** | Wakes the sender at the chosen time |
| **DynamoDB** | Jobs, receipts, and a separately encrypted LINE session |
| **Private S3** | Temporary attachment storage, pinned to immutable versions |

**Login and reconnect happen in the private Site.** Choose Connect/Reconnect LINE, scan the QR using LINE on your phone, and approve. AWS securely saves the session; Sites never receives the LINE credentials. Your laptop can be off after setup.

The [architecture guide](docs/ARCHITECTURE.md) explains the three logins, temporary QR flow, session storage, timing, and recovery. GitHub contains the source and deployment instructions; the running copies live on Sites and AWS.

## Build your own

- [Frontend source and Sites setup](web/README.md)
- [AWS deployment, security boundaries, and operations](deploy/aws/README.md)
- [CLI build and usage](https://github.com/punnkrit/line-scheduler-client/blob/main/docs/CLI.md)
- [Security review and remaining risks](https://github.com/punnkrit/line-scheduler-client/blob/main/docs/FORK_SECURITY.md)
- [V2 compatibility evidence](https://github.com/punnkrit/line-scheduler-client/blob/main/docs/V2_COMPATIBILITY.md)

The sender comes from **[line-scheduler-client](https://github.com/punnkrit/line-scheduler-client)**, our hardened fork of [kongesque/line-cli](https://github.com/kongesque/line-cli). This app pins its exact commit in `client.lock.json`. Build it with **Go 1.27.3** using `python3 scripts/build_sender.py`; upstream installers do not contain its changes. This repository includes synthetic tests and sanitized frontend source, never live credentials, messages, contact lists, or deployment identifiers.

This is an unofficial personal project. LINE can revoke sessions or change its protocol. “Sent” means LINE accepted the message, not that someone read it. AWS scheduling has minute-level precision, and an uncertain send needs a manual check in LINE. Small usage is intended to be inexpensive; free credits and recurring service allowances are separate, and a zero bill is not guaranteed.

## Thanks

Built on [Kongesque’s LINE CLI](https://github.com/kongesque/line-cli) and its [Beeper LINE](https://github.com/beeper/line) origins. Their work made this possible. The client fork retains upstream history and copyright notices. This application is also released under the [MIT License](LICENSE).

Not affiliated with LINE, LY Corporation, or OpenAI.
