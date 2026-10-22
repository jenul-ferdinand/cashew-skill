#!/usr/bin/env python3
"""Queue transactions in Cashew on an Android phone, through its app-link
broadcast receiver over SSH (Termux). Cashew adds them when next opened.

stdin: a JSON list, amount < 0 for expenses and > 0 for income, e.g.
  [{"date": "2026-10-21", "amount": -12.5, "title": "Subway",
    "category": "Dining"}]

  cashew.py          send to the phone (ssh host $CASHEW_SSH_HOST or "phone")
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
from urllib.parse import quote, unquote

BASE = "https://cashewapp.web.app/addTransaction?JSON="
RECEIVER = "com.budget.tracker_app/com.budget.tracker_app.UriReceiver"
HOST = os.environ.get("CASHEW_SSH_HOST", "phone")
# ~20KB/link, far below Linux's 128KB per-argument cap, lower iff notes run long
BATCH = 50


@dataclass(frozen=True)
class Transaction:
    """One Cashew transaction: amount < 0 is an expense, > 0 income."""

    date: datetime
    amount: float
    category: str
    title: str = ""
    notes: str = ""
    subcategory: str = ""
    account: str = ""

    def __post_init__(self) -> None:
        if not (math.isfinite(self.amount) and self.amount):
            raise ValueError("amount must be a nonzero number")
        if self.date.tzinfo:  # Cashew reads it as local time; shifting the day
            raise ValueError("date must be local time, without an offset")
        if not self.category:  # Cashew drops or prompts without one
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
        given = {k: v for k, v in asdict(self).items() if v != ""}
        # categoryPolarity off: the amount's sign decides expense/income
        return {
            **given,
            "date": self.date.isoformat(),
            "categoryPolarity": "false",
        }


def app_links(txns: list[Transaction]) -> list[str]:
    """Cashew app links that add these transactions, BATCH per link."""
    params = [t.to_params() for t in txns]
    batches = [params[i : i + BATCH] for i in range(0, len(params), BATCH)]
    return [
        BASE + quote(json.dumps({"transactions": b}), safe="") for b in batches
    ]


def test() -> None:
    raw = {
        "date": "2026-10-21T12:30",
        "amount": "-12.5",
        "title": "Bob's & Co",
        "category": "Dining",
    }
    urls = app_links([Transaction.parse(raw)] * 51)
    sent = json.loads(unquote(urls[0].removeprefix(BASE)))["transactions"]
    assert len(urls) == 2 and len(sent) == BATCH
    assert sent[0] == {
        **raw,
        "amount": -12.5,
        "date": "2026-10-21T12:30:00",
        "categoryPolarity": "false",
    }
    bad = [
        {**raw, "date": "21/10/2026"},
        {**raw, "date": "2026-10-21T12:30+11:00"},
        {**raw, "amount": 0},
        {**raw, "amount": "$5"},
        {**raw, "amount": "nan"},
        {**raw, "category": ""},
        {**raw, "catgory": "typo"},
        {"title": "no amount or date"},
    ]
    for b in bad:
        try:
            Transaction.parse(b)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {b}")
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
        remote = shlex.join(["am", "broadcast", "-n", RECEIVER, "-d", url])
        ssh = ["ssh", "-o", "ConnectTimeout=8", HOST, remote]
        result = subprocess.run(ssh, capture_output=True, text=True)
        if result.returncode:
            error = result.stderr or result.stdout
            sys.exit(
                f"cashew.py: batch {i}/{len(urls)} failed, "
                f"earlier batches were queued:\n{error}"
            )
    print(f"Queued {len(txns)} transaction(s). Open Cashew to add them.")


if __name__ == "__main__":
    main()
