#!/usr/bin/env python3
"""
Claude Code weekly usage tracker.

Builds a PERSISTENT, append-only weekly archive of Claude Code token usage and
estimated (API-equivalent) cost, split by account.

Why this exists: Claude Code deletes transcripts after `cleanupPeriodDays`, and
ccusage / CodexBar can only read what is still on disk. This script snapshots the
data into its own archive that is never pruned, so history accumulates for as long
as you keep running it.

Account attribution: transcripts contain NO account identity. The only source is
~/.claude.json -> oauthAccount (the *currently* logged-in account). So each run
records the active account into a timeline, and usage is attributed to whichever
account was active at each message's timestamp. All history before the first run
is attributed to whatever account is active on that first run.

Usage:
  python3 track.py                  # sample account + scan logs + merge + report
  python3 track.py --report         # just print the archive (no scan)
  python3 track.py --record-account # only sample the active account (fast; for frequent timers)
  python3 track.py --csv out.csv    # also export the archive as CSV
  python3 track.py --by-model       # include per-model breakdown in the report
"""

import argparse
import csv
import datetime as dt
import glob
import json
import os
import sys
import tempfile

HOME = os.path.expanduser("~")
PROJECTS_DIR = os.path.join(HOME, ".claude", "projects")
CLAUDE_JSON = os.path.join(HOME, ".claude.json")
ARCHIVE_DIR = os.path.join(HOME, ".claude-usage-archive")
WEEKLY_PATH = os.path.join(ARCHIVE_DIR, "weekly.json")
TIMELINE_PATH = os.path.join(ARCHIVE_DIR, "account_timeline.json")

# Per-MILLION-token USD prices (API list prices; cache_5m=1.25x in, cache_1h=2x in, cache_read=0.1x in).
# Edit freely. Unknown models fall back to the "sonnet" tier and are flagged.
PRICING = {
    "opus":   {"in": 15.0, "out": 75.0, "cache_read": 1.50, "cache_5m": 18.75, "cache_1h": 30.0},
    "sonnet": {"in": 3.0,  "out": 15.0, "cache_read": 0.30, "cache_5m": 3.75,  "cache_1h": 6.0},
    "haiku":  {"in": 1.0,  "out": 5.0,  "cache_read": 0.10, "cache_5m": 1.25,  "cache_1h": 2.0},
}
DEFAULT_TIER = "sonnet"

METRICS = ["in", "out", "cache_read", "cache_5m", "cache_1h", "messages", "sessions"]


# ---------- small IO helpers ----------

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic_write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---------- account timeline ----------

def current_account():
    data = load_json(CLAUDE_JSON, {})
    acct = (data or {}).get("oauthAccount") or {}
    return acct.get("emailAddress"), acct.get("accountUuid")


def record_account(timeline):
    """Append an observation only if the active account changed (keeps it compact)."""
    email, uuid = current_account()
    if not email:
        return timeline, None
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    if not timeline or timeline[-1]["email"] != email:
        timeline.append({"observed_at": now, "email": email, "accountUuid": uuid})
    else:
        timeline[-1]["last_seen"] = now
    return timeline, email


def account_for(ts_epoch, timeline):
    """Account active at a given epoch. Before the first observation -> first account."""
    if not timeline:
        return "unknown"
    chosen = timeline[0]["email"]
    for entry in timeline:
        if entry["observed_at"] <= ts_epoch:
            chosen = entry["email"]
        else:
            break
    return chosen


# ---------- pricing ----------

def tier_for(model):
    m = (model or "").lower()
    for tier in ("opus", "sonnet", "haiku"):
        if tier in m:
            return tier, False
    return DEFAULT_TIER, True  # assumed


def cost_for(cell, model):
    tier, _ = tier_for(model)
    p = PRICING[tier]
    return (
        cell["in"] * p["in"]
        + cell["out"] * p["out"]
        + cell["cache_read"] * p["cache_read"]
        + cell["cache_5m"] * p["cache_5m"]
        + cell["cache_1h"] * p["cache_1h"]
    ) / 1_000_000


# ---------- scanning ----------

def iso_week(ts):
    iso = ts.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_monday(week_label):
    year, wk = week_label.split("-W")
    return dt.date.fromisocalendar(int(year), int(wk), 1).isoformat()


def empty_cell():
    return {k: 0 for k in METRICS}


def scan(timeline):
    """Return fresh aggregates: {week: {account: {model: cell}}} and unpriced model set."""
    fresh = {}
    seen_msg_ids = set()
    sessions_by_key = {}  # (week, account, model) -> set(session_id)
    unpriced = set()

    for path in glob.glob(os.path.join(PROJECTS_DIR, "**", "*.jsonl"), recursive=True):
        try:
            fh = open(path, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue
                msg_id = msg.get("id") or rec.get("requestId") or rec.get("uuid")
                if msg_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(msg_id)

                tstr = rec.get("timestamp")
                if not tstr:
                    continue
                try:
                    ts = dt.datetime.fromisoformat(tstr.replace("Z", "+00:00"))
                except ValueError:
                    continue

                model = msg.get("model") or "unknown"
                tier, assumed = tier_for(model)
                if assumed:
                    unpriced.add(model)

                week = iso_week(ts)
                account = account_for(ts.timestamp(), timeline)

                cc = usage.get("cache_creation") or {}
                cache_5m = cc.get("ephemeral_5m_input_tokens")
                cache_1h = cc.get("ephemeral_1h_input_tokens")
                if cache_5m is None and cache_1h is None:
                    cache_5m = usage.get("cache_creation_input_tokens", 0)
                    cache_1h = 0

                cell = (
                    fresh.setdefault(week, {})
                    .setdefault(account, {})
                    .setdefault(model, empty_cell())
                )
                cell["in"] += usage.get("input_tokens", 0)
                cell["out"] += usage.get("output_tokens", 0)
                cell["cache_read"] += usage.get("cache_read_input_tokens", 0)
                cell["cache_5m"] += cache_5m or 0
                cell["cache_1h"] += cache_1h or 0
                cell["messages"] += 1

                skey = (week, account, model)
                sid = rec.get("sessionId")
                if sid:
                    sessions_by_key.setdefault(skey, set()).add(sid)

    for (week, account, model), sids in sessions_by_key.items():
        fresh[week][account][model]["sessions"] = len(sids)

    return fresh, unpriced


def merge(archive, fresh):
    """Max-merge per cell so already-recorded weeks never shrink when logs age out."""
    for week, accts in fresh.items():
        for account, models in accts.items():
            for model, cell in models.items():
                dst = (
                    archive.setdefault(week, {})
                    .setdefault(account, {})
                    .setdefault(model, empty_cell())
                )
                for k in METRICS:
                    dst[k] = max(dst.get(k, 0), cell.get(k, 0))
    return archive


# ---------- reporting ----------

def human(n):
    n = float(n)
    for unit in ("", "K", "M", "B"):
        if abs(n) < 1000:
            return f"{n:.0f}{unit}" if unit == "" else f"{n:.1f}{unit}"
        n /= 1000
    return f"{n:.1f}T"


def report(archive, by_model=False):
    if not archive:
        print("No data yet.")
        return

    weeks = sorted(archive.keys(), reverse=True)
    account_totals = {}

    print(f"\nClaude Code weekly usage — {len(weeks)} week(s), "
          f"{weeks[-1]} → {weeks[0]}\n")
    hdr = f"{'Week (Mon)':<16}{'Account':<26}{'In':>8}{'Out':>8}{'CacheR':>9}{'CacheW':>9}{'Msgs':>7}{'Est $':>10}"
    print(hdr)
    print("-" * len(hdr))

    for week in weeks:
        first = True
        for account in sorted(archive[week].keys()):
            agg = empty_cell()
            cost = 0.0
            for model, cell in archive[week][account].items():
                for k in METRICS:
                    agg[k] += cell.get(k, 0)
                cost += cost_for(cell, model)
            at = account_totals.setdefault(account, {"cost": 0.0, **empty_cell()})
            at["cost"] += cost
            for k in METRICS:
                at[k] += agg[k]

            label = f"{week_monday(week)}" if first else ""
            first = False
            cachew = agg["cache_5m"] + agg["cache_1h"]
            print(f"{label:<16}{account:<26}"
                  f"{human(agg['in']):>8}{human(agg['out']):>8}"
                  f"{human(agg['cache_read']):>9}{human(cachew):>9}"
                  f"{agg['messages']:>7}{('$'+format(cost,',.2f')):>10}")
            if by_model:
                for model in sorted(archive[week][account].keys()):
                    cell = archive[week][account][model]
                    mc = cost_for(cell, model)
                    cw = cell["cache_5m"] + cell["cache_1h"]
                    print(f"{'':<16}  └ {model:<22}"
                          f"{human(cell['in']):>8}{human(cell['out']):>8}"
                          f"{human(cell['cache_read']):>9}{human(cw):>9}"
                          f"{cell['messages']:>7}{('$'+format(mc,',.2f')):>10}")

    print("\nGrand totals by account (whole archive):")
    print("-" * 60)
    for account in sorted(account_totals, key=lambda a: -account_totals[a]["cost"]):
        t = account_totals[account]
        cw = t["cache_5m"] + t["cache_1h"]
        print(f"  {account:<28} in {human(t['in']):>7}  out {human(t['out']):>7}  "
              f"cacheR {human(t['cache_read']):>7}  cacheW {human(cw):>7}  "
              f"msgs {t['messages']:>6}  est ${t['cost']:,.2f}")


def export_csv(archive, path):
    rows = []
    for week, accts in archive.items():
        for account, models in accts.items():
            for model, cell in models.items():
                rows.append({
                    "week": week,
                    "week_monday": week_monday(week),
                    "account": account,
                    "model": model,
                    "input_tokens": cell["in"],
                    "output_tokens": cell["out"],
                    "cache_read_tokens": cell["cache_read"],
                    "cache_write_5m_tokens": cell["cache_5m"],
                    "cache_write_1h_tokens": cell["cache_1h"],
                    "messages": cell["messages"],
                    "sessions": cell["sessions"],
                    "est_cost_usd": round(cost_for(cell, model), 4),
                })
    rows.sort(key=lambda r: (r["week"], r["account"], r["model"]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["week"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path}")


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Persistent weekly Claude Code usage tracker.")
    ap.add_argument("--report", action="store_true", help="print archive without scanning")
    ap.add_argument("--record-account", action="store_true", help="only sample the active account")
    ap.add_argument("--by-model", action="store_true", help="include per-model breakdown")
    ap.add_argument("--csv", metavar="PATH", help="export archive to CSV")
    args = ap.parse_args()

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    timeline = load_json(TIMELINE_PATH, [])

    if args.report:
        report(load_json(WEEKLY_PATH, {}), by_model=args.by_model)
        return

    timeline, email = record_account(timeline)
    atomic_write(TIMELINE_PATH, timeline)
    if email:
        print(f"Active account: {email}")

    if args.record_account:
        return

    archive = load_json(WEEKLY_PATH, {})
    fresh, unpriced = scan(timeline)
    archive = merge(archive, fresh)
    atomic_write(WEEKLY_PATH, archive)

    if unpriced:
        print(f"Note: assumed '{DEFAULT_TIER}' pricing for unknown model(s): "
              f"{', '.join(sorted(unpriced))}")

    report(archive, by_model=args.by_model)
    if args.csv:
        export_csv(archive, args.csv)


if __name__ == "__main__":
    main()
