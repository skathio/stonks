# =============================================================================
# Entry point for the daily agent job.
#
#   python3 -m pipeline.cli history              update universe, price history, splits
#   python3 -m pipeline.cli prepare              history + features + regime + earnings
#   python3 -m pipeline.cli enrich AAPL,NVDA,... news / analyst / filings for a shortlist
#   python3 -m pipeline.cli publish              validate analysis.json, ledger, encrypt site
#   python3 -m pipeline.cli ship                 commit + push both repos to main
# =============================================================================
import argparse
import subprocess
import sys

from . import daily, history, universe
from .analysis import AnalysisError
from .common import REPO_ROOT, data_dir, log


def cmd_history(args):
    root = data_dir()
    members = universe.load(root, refresh=args.refresh_universe)
    symbols = sorted(set(members) | set(history.BENCHMARKS))
    added = history.update(root, symbols, max_calls=args.max_calls)
    new_splits = history.refresh_splits(root)
    days = history.stored_days(root)
    log("history.done", added=len(added), new_splits=new_splits, sessions=len(days),
        first=days[0].isoformat() if days else None, last=days[-1].isoformat() if days else None)


def cmd_prepare(args):
    print(daily.prepare(data_dir(), update_history=not args.no_history))


def cmd_enrich(args):
    print(daily.enrich(data_dir(), args.tickers.split(","), as_of=args.as_of))


def cmd_publish(args):
    try:
        print(daily.publish(data_dir(), as_of=args.as_of, encrypt=not args.no_encrypt))
    except AnalysisError as exc:
        # The agent reads this, fixes analysis.json and re-runs publish.
        print(f"analysis.json rejected: {exc}", file=sys.stderr)
        return 2
    return 0


def _git(repo, *cmd):
    return subprocess.run(["git", "-C", repo, *cmd], check=True, capture_output=True, text=True).stdout.strip()


def _commit_and_push(repo, paths, message):
    _git(repo, "add", "--", *paths)
    if not _git(repo, "status", "--porcelain", "--", *paths):
        log("ship.nothing_to_commit", repo=repo)
        return
    _git(repo, "commit", "-m", message)
    _git(repo, "pull", "--rebase", "origin", "main")
    _git(repo, "push", "origin", "HEAD:main")
    log("ship.pushed", repo=repo, head=_git(repo, "rev-parse", "--short", "HEAD"))


def cmd_ship(args):
    root = data_dir()
    as_of = daily.latest_as_of(root)
    # Private state first: if the public push fails, nothing references missing data.
    _commit_and_push(root, ["."], f"daily run {as_of}")
    _commit_and_push(REPO_ROOT, ["site/data"], f"dashboard: {as_of}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("history", help="update universe, price history and split ledger")
    p.add_argument("--refresh-universe", action="store_true")
    p.add_argument("--max-calls", type=int, default=None)
    p.set_defaults(func=cmd_history)
    p = sub.add_parser("prepare", help="features, regime, breadth, macro and earnings for the scan universe")
    p.add_argument("--no-history", action="store_true", help="skip the price-history update")
    p.set_defaults(func=cmd_prepare)
    p = sub.add_parser("enrich", help="news, analyst trends, metrics and SEC filings for a shortlist")
    p.add_argument("tickers", help="comma-separated, at most 40")
    p.add_argument("--as-of")
    p.set_defaults(func=cmd_enrich)
    p = sub.add_parser("publish", help="validate analysis.json, update the ledger, encrypt the dashboard")
    p.add_argument("--as-of")
    p.add_argument("--no-encrypt", action="store_true")
    p.set_defaults(func=cmd_publish)
    p = sub.add_parser("ship", help="commit and push stonks-data and the encrypted site to main")
    p.set_defaults(func=cmd_ship)
    args = ap.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
