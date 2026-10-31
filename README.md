![Cashew Agent Skill](.github/banner.png)

Tell your AI agent what you spent, and it lands in [Cashew](https://github.com/jameskokoska/Cashew), the open-source budgeting app.

> **You:** 14.50 subway yesterday, 62 groceries at woolies monday, got paid 450 today
>
> **Agent:**
>
> | Date       | Amount  | Title      | Category  |
> | ---------- | ------- | ---------- | --------- |
> | 2026-10-21 | -14.50  | Subway     | Dining    |
> | 2026-10-19 | -62.00  | Woolworths | Groceries |
> | 2026-10-22 | +450.00 | Pay        | Income    |
>
> Send these to Cashew?

It's an [Agent Skill](https://agentskills.io), so it works with Claude Code, Codex, and any other agent that loads skills.

## How it works

Cashew has no API. It does accept [app links](https://cashewapp.web.app/faq.html#app-links), and it has a [broadcast receiver](https://cashewapp.web.app/faq.html#broadcast-receiver) that queues them while the app is closed. The agent turns your text into transactions. `cashew.py` encodes them as a JSON app link and sends it to the phone with `am broadcast` over SSH to [Termux](https://termux.dev). Cashew adds them the next time you open it.

## Setup

You need an Android phone with Cashew and [Termux from F-Droid](https://f-droid.org/packages/com.termux/), plus Python 3 on the computer that runs the agent.

1. In Termux, start an SSH server (it listens on port 8022):
   ```sh
   pkg install openssh
   passwd   # or put your public key in ~/.ssh/authorized_keys
   sshd
   ```
2. On the computer, add the phone to `~/.ssh/config`. To use a different host name, set `CASHEW_SSH_HOST`.
   ```
   Host phone
     HostName 192.168.x.x   # the phone's Wi-Fi IP
     Port 8022
   ```
3. Install the skill:
   ```sh
   npx skills add jenul-ferdinand/cashew-skill -g
   ```
   Or, in Claude Code, as a plugin:
   ```
   /plugin install cashew-skill --marketplace jenul-ferdinand/skills
   ```
4. Tell the agent your Cashew category names. Or export a backup (More → Settings & Customization → Import & Export Data → Export Cashew Data File) and let it read them. It keeps them in `~/.config/cashew-skill/profile.md`.

Without SSH, `cashew.py --link` prints a link you can tap on the phone instead.

## Tips

- Cashew's Notification Scanning (Settings → Experimental Features) can log your bank's purchase notifications by itself. This skill covers cash, catching up, and statements.
- For a transfer between your accounts, Cashew opens a pre-filled transfer screen that you save with a tap.
- Self-check: `python3 cashew.py --test`.

Unofficial and not affiliated with Cashew. MIT licensed.
