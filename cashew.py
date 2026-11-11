#!/usr/bin/env python3
"""Queue transactions in Cashew on an Android phone, through its app-link
broadcast receiver over SSH (Termux). Cashew adds them when next opened.

stdin: a JSON list, amount < 0 for expenses and > 0 for income, e.g.
  [{"date": "2026-10-21", "amount": -12.5, "title": "Subway",
    "category": "Dining"}]
A row with "to" is a transfer from "account" (amount > 0, no category), e.g.
  {"date": "2026-10-21", "amount": 200, "account": "Everyday", "to": "Savings"}

  cashew.py          send to the phone (ssh host $CASHEW_SSH_HOST or "phone"),
                     then post a notification there that opens Cashew
  cashew.py --link   print app links to tap on the phone instead (no ssh)
  cashew.py --test   self-check
"""

import json
import math
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from urllib.parse import quote, unquote, urlencode

BASE = "https://cashewapp.web.app/addTransaction?JSON="
TRANSFER = "https://cashewapp.web.app/addTransferRoute?"
RECEIVER = "com.budget.tracker_app/com.budget.tracker_app.UriReceiver"
ACTIVITY = "com.budget.tracker_app/.MainActivity"
HOST = os.environ.get("CASHEW_SSH_HOST", "phone")
# ~20KB/link, far below Linux's 128KB per-argument cap, lower iff notes run long
BATCH = 50


@dataclass(frozen=True)
class Transaction:
    """One Cashew transaction: amount < 0 is an expense, > 0 income."""

    date: datetime
    amount: float
    category: str = ""
    title: str = ""
    notes: str = ""
    subcategory: str = ""
    account: str = ""
    to: str = ""

    def __post_init__(self) -> None:
        if not (math.isfinite(self.amount) and self.amount):
            raise ValueError("amount must be a nonzero number")
        if self.date.tzinfo:  # Cashew reads it as local time; shifting the day
            raise ValueError("date must be local time, without an offset")
        if self.to:
            if not (self.account and self.amount > 0):
                raise ValueError("a transfer needs an account and amount > 0")
            if self.category or self.subcategory or self.notes:
                raise ValueError(
                    "a transfer takes no category, subcategory or notes"
                )
        elif not self.category:  # Cashew drops or prompts without one
            raise ValueError("category is required")

    @classmethod
    def parse(cls, raw: dict) -> "Transaction":
        """Build one from its JSON form; unknown or missing fields raise."""
        try:
            date = datetime.fromisoformat(raw["date"])
            return cls(**{**raw, "date": date, "amount": float(raw["amount"])})
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{raw}: {e!r}") from None

    def to_params(self) -> dict:
        """The app-link parameters Cashew parses, leaving out empty ones."""
        if self.to:
            return {
                "amountFrom": self.amount,
                "accountFrom": self.account,
                "accountTo": self.to,
                "date": self.date.isoformat(),
            } | ({"title": self.title} if self.title else {})
        given = {k: v for k, v in asdict(self).items() if v != ""}
        # categoryPolarity off: the amount's sign decides expense/income
        return {
            **given,
            "date": self.date.isoformat(),
            "categoryPolarity": "false",
        }


def app_links(txns: list[Transaction]) -> list[str]:
    """Cashew app links: BATCH transactions per link, then one per transfer."""
    params = [t.to_params() for t in txns if not t.to]
    batches = [params[i : i + BATCH] for i in range(0, len(params), BATCH)]
    transfers = [t.to_params() for t in txns if t.to]
    return [
        BASE + quote(json.dumps({"transactions": b}), safe="") for b in batches
    ] + [TRANSFER + urlencode(p, quote_via=quote) for p in transfers]


def notification(text: str) -> str:
    """Termux command for one notification that opens Cashew when tapped.

    The fixed id makes a later send replace it instead of stacking another.
    termux-notification hangs when the Termux:API app is missing, hence the
    timeout, and its helper outlives that, holding ssh open ~50s unless its
    output goes to /dev/null.
    """
    tap = f"termux-notification-remove cashew; am start -n {ACTIVITY}"
    cmd = ["timeout", "10", "termux-notification", "--id", "cashew"]
    cmd += ["--title", "Cashew", "--content", text, "--action", tap]
    return shlex.join(cmd) + " >/dev/null 2>&1"


def ssh(remote: str) -> subprocess.CompletedProcess:
    cmd = ["ssh", "-o", "ConnectTimeout=8", HOST, remote]
    return subprocess.run(cmd, capture_output=True, text=True)


def test() -> None:
    raw = {
        "date": "2026-10-21T12:30",
        "amount": "-12.5",
        "title": "Bob's & Co",
        "category": "Dining",
    }
    move = {
        "date": "2026-10-21",
        "amount": 200,
        "account": "Everyday",
        "to": "Rainy Day",
    }
    rows = [raw] * 51 + [move, {**move, "title": "Top up"}]
    urls = app_links([Transaction.parse(r) for r in rows])
    sent = json.loads(unquote(urls[0].removeprefix(BASE)))["transactions"]
    assert len(urls) == 4 and len(sent) == BATCH
    assert sent[0] == {
        **raw,
        "amount": -12.5,
        "date": "2026-10-21T12:30:00",
        "categoryPolarity": "false",
    }
    link = TRANSFER + (
        "amountFrom=200.0&accountFrom=Everyday&accountTo=Rainy%20Day"
        "&date=2026-10-21T00%3A00%3A00"
    )
    assert urls[2:] == [link, link + "&title=Top%20up"]
    bad = [
        {**raw, "date": "21/10/2026"},
        {**raw, "date": "2026-10-21T12:30+11:00"},
        {**raw, "amount": 0},
        {**raw, "amount": "$5"},
        {**raw, "amount": "nan"},
        {**raw, "category": ""},
        {**raw, "catgory": "typo"},
        {"title": "no amount or date"},
        {**move, "account": ""},
        {**move, "to": ""},
        {**move, "amount": 0},
        {**move, "amount": -200},
        {**move, "category": "Dining"},
    ]
    for b in bad:
        try:
            Transaction.parse(b)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {b}")
    text = "Queued 2 transaction(s). It's Bob's."
    note = shlex.split(notification(text))
    assert note[:3] == ["timeout", "10", "termux-notification"]
    assert note[-2:] == [">/dev/null", "2>&1"]
    flags = dict(zip(note[3:-2:2], note[4:-2:2]))
    assert flags["--id"] == "cashew" and flags["--content"] == text
    assert flags["--action"].endswith(f"am start -n {ACTIVITY}")
    print("ok")


def main() -> None:
    args = sys.argv[1:]
    if args == ["--test"]:
        test()
        return
    if args not in ([], ["--link"]):
        sys.exit(__doc__)
    try:
        txns = [Transaction.parse(t) for t in json.load(sys.stdin)]
    except (TypeError, ValueError) as e:  # bad JSON or a bad transaction
        sys.exit(f"cashew.py: {e}")
    urls = app_links(txns)
    if args == ["--link"]:
        print(*urls, sep="\n")
        return
    for i, url in enumerate(urls, 1):
        result = ssh(shlex.join(["am", "broadcast", "-n", RECEIVER, "-d", url]))
        if result.returncode:
            error = result.stderr or result.stdout
            sys.exit(
                f"cashew.py: batch {i}/{len(urls)} failed, "
                f"earlier batches were queued:\n{error}"
            )
    save = ", and save each transfer screen" if any(t.to for t in txns) else ""
    done = f"Queued {len(txns)} transaction(s). Open Cashew to add them{save}."
    print(done)
    # after every batch, so one send posts one notification
    if code := ssh(notification(done)).returncode:
        why = "ssh dropped" if code == 255 else "is the Termux:API app missing?"
        print(
            f"No notification on the phone ({why}). It needs the Termux:API "
            "app from where you got Termux, and `pkg install termux-api`.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
