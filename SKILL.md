---
name: cashew
description: Log expenses and income into the Cashew budgeting app (Android) from free text ("spent $12 on lunch yesterday", "paid rent", a bank statement). Use whenever the user mentions spending, purchases, income, bills, or Cashew.
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
2. Show them as a short table and get a yes before sending.
3. Send:
   ```sh
   python3 <skill dir>/cashew.py <<'EOF'
   [{"date": "2026-10-21", "amount": -12.5, "title": "Subway", "category": "Dining"}]
   EOF
   ```
4. Tell the user to open Cashew to process them.

If ssh fails, the phone may be off the network, its IP may have changed, or sshd isn't running (open Termux, run `sshd`). Use `--link` instead and give the user the link to tap on the phone.

## Reading data

There is no live read access. Ask for a backup: More → Settings & Customization → Import & Export Data → Export Cashew Data File, saved to Downloads. Copy it with `scp <host>:/storage/emulated/0/Download/<file> .` and open it with Python's `sqlite3`. It's the app's raw SQLite DB, with tables `categories`, `wallets` (accounts) and `transactions`. Use it to fill the profile, find where logging stopped, and avoid duplicates.

## Bank statements

1. Run `pdftotext -layout` on each PDF and parse the text, reusing any parser the profile names. Save a new parser next to the profile in `~/.config/cashew-skill/` and name it in the profile.
2. Check the parse: each statement's opening balance plus its rows equals its closing balance, and each closing balance equals the opening balance of that account's next statement.
3. Ask for a fresh backup (see Reading data). Match each statement row to a Cashew row with the same amount within a few days. If a statement shows both a transaction date and a posting date, use the transaction date for matching and for new rows.
4. Before calling a row missing, rule these out:
   - A subscription row at an outdated price covers its bank charge. Don't add the charge. Tell the user to fix the subscription's price and its rows since the change.
   - One Cashew row can be the sum of several statement rows, such as a night out logged once or two incoming payments logged together.
   - A failed payment and its reversal cancel out. Add both or neither.
5. Skip money the user moved between their own bank accounts if both belong to the same Cashew account. Otherwise log it as a transfer (see Logging).
6. Give each new row the title and category the user used before for the same merchant. Ask about merchants you can't place.
7. Balance corrections the user made while not logging count the same money twice once you add the missing rows. List them for the user to delete, along with any subscription prices to fix. The user makes edits and deletes by hand in the app.
8. Confirm, then send.
9. Once the user has opened Cashew and made those changes, ask for a fresh backup. On each statement's end date, compare the Cashew account's balance with the bank's, adding up bank accounts that share a Cashew account. Allow for purchases dated on or before that day that the bank posted later. Any other gap points to a missing or doubled row, or a batch that never arrived.

## Docs

The GitHub source stops at v5.3.4 (2024) and lacks the receiver. The current docs are `https://cashewapp.web.app/assets/docs/automation/{app-links,broadcast-receiver,notification-scan,mailbox}.md`.
