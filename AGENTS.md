# LINE Scheduler

This repository owns the private Sites frontend and AWS scheduling application.
The personal LINE client is a separate dependency pinned in `client.lock.json`.
Keep protocol/crypto changes in that client repository; do not vendor its source here.

- Preserve owner-only Site access and keep credentials server-side.
- Require Letter Sealing; never add plaintext fallbacks or automatic mutation retries.
- Preserve job claims, immutable attachment versions, integrity checks, and fenced session saves.
- Ordinary tests use synthetic credentials and fake services only.
- Live LINE tests require explicit recipient, content, and action authorization.
- Never commit credentials, deployment identifiers, messages, contacts, or `.local` contents.
- Keep interface copy functional. No promotional headers, taglines, or decorative footers.

Run `python3 -m unittest discover -s deploy/aws -p 'test_*.py'` and the probe tests
for backend changes. Check TypeScript and build through the Sites workflow for
frontend changes. Build the client through `scripts/build_sender.py` with the
exact toolchain and commit in the lock file.
