---
name: cashew
description: Log expenses and income into the Cashew budgeting app (Android) from free text ("spent $12 on lunch yesterday", "paid rent", a bank statement). Use whenever the user mentions spending, purchases, income, bills, transfers, or Cashew.
---

# Cashew

[Cashew](https://github.com/jameskokoska/Cashew) has no API. `cashew.py` (in this skill's directory) queues transactions through its app-link broadcast receiver over SSH to Termux on the phone. The SSH host is `$CASHEW_SSH_HOST`, default `phone`. Cashew adds the queued transactions the next time it's opened.

## Before logging

Read `~/.config/cashew-skill/profile.md`. It holds the user's exact category and account names, currency, bank, and habits. If it's missing, build it from a backup (see Reading data) or ask the user, then save it there. It lives outside the skill folder so updates don't wipe it.

## Logging

1. Turn the text into transactions. Resolve "yesterday"/"monday" against today. Fields:
   - `date`: ISO, optionally with time (`2026-10-21` or `2026-10-21T12:30`)
   - `amount`: in the account's currency, negative = expense, positive = income/refund
   - `title`: merchant or short label
   - `category`: an exact name from the profile. A miss makes Cashew prompt on open (older versions drop the transaction).
   - optional `subcategory`, `notes`, `account` (exact names)
   - Money moved between two of the user's Cashew accounts is a transfer. Give it `account` (from), `to`, a positive `amount` and an optional `title`, but no category. Don't log it as an expense plus an income.
2. Show them as a short table and get a yes before sending.
3. Send:
   ```sh
   python3 <skill dir>/cashew.py <<'EOF'
   [{"date": "2026-10-21", "amount": -12.5, "title": "Subway", "category": "Dining"}]
   EOF
   ```
4. Tell the user to open Cashew to process them. Cashew opens each transfer on a pre-filled screen, and they save it with a tap.

If ssh fails, the phone may be off the network, its IP may have changed, or sshd isn't running (open Termux, run `sshd`). Use `--link` instead and give the user the link to tap on the phone.

## Reading data

There is no live read access. Ask for a backup: More → Settings & Customization → Import & Export Data → Export Cashew Data File, saved to Downloads. Copy it with `scp <host>:/storage/emulated/0/Download/<file> .` and open it with Python's `sqlite3`. It's the app's raw SQLite DB, with tables `categories`, `wallets` (accounts) and `transactions`. Use it to fill the profile, find where logging stopped, and avoid duplicates.

## Bank statements

For a PDF statement, run `pdftotext -layout` and turn the rows into transactions. Skip transfers between the user's own accounts. Confirm, then send in one batch.

## Docs

The GitHub source stops at v5.3.4 (2024) and lacks the receiver. The current docs are `https://cashewapp.web.app/assets/docs/automation/{app-links,broadcast-receiver,notification-scan,mailbox}.md`.
