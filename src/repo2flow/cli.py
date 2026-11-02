"""Command-line entry point."""

import argparse
import sys
import tomllib

from repo2flow.output import print_top, read_corrections, write_csv
from repo2flow.score import DEFAULT_WEIGHTS, collect, load_ignore, rank
from repo2flow.sources import materialize


def parse_weights(value) -> dict[str, float]:
    """Accept 'docs=3,code=1' (CLI) or a table (config file); unspecified layers keep defaults."""
    if isinstance(value, str):
        value = dict(pair.split("=", 1) for pair in value.split(",") if pair)
    weights = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in value.items()}}
    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown weight layer(s): {', '.join(sorted(unknown))}")
    return weights


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="repo2flow", description="Build a Wispr Flow dictionary CSV from repositories.")
    p.add_argument("sources", nargs="*", help="git URL, local path, owner/repo, or GitHub user/org")
    p.add_argument("--config", help="TOML file; keys mirror the flags (e.g. sources, top, weights)")
    p.add_argument("--github", action="append", default=[], metavar="USER", help="GitHub user/org whose public repos to fetch")
    p.add_argument("--skip-forks", action="store_true", help="skip forks when expanding a GitHub user/org")
    p.add_argument("--github-token", help="optional token to raise API rate limits (or set GITHUB_TOKEN)")
    p.add_argument("--include", action="append", default=[], metavar="GLOB", help="only scan paths matching GLOB")
    p.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="skip paths matching GLOB")
    p.add_argument("-o", "--output", default="repo2flow.csv", help="output CSV path (default: %(default)s)")
    p.add_argument("--top", type=int, default=300, help="number of terms to keep (default: %(default)s)")
    p.add_argument("--min-files", type=int, default=2, help="min distinct files a term must appear in (default: %(default)s)")
    p.add_argument("--max-zipf", type=float, default=3.5, help="drop words more common than this wordfreq zipf (default: %(default)s)")
    p.add_argument("--weights", default={}, help="layer weights, e.g. docs=3,comments=2,code=1")
    p.add_argument("--ignore-file", help="file of terms to exclude, one per line")
    p.add_argument("--corrections", help="CSV of 'misheard,correct' rows to include as two-column entries")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)
    cfg = {}
    if args.config:
        with open(args.config, "rb") as f:
            cfg = {k.replace("-", "_"): v for k, v in tomllib.load(f).items()}
        lists = {"sources", "github", "include", "exclude"}
        parser.set_defaults(**{k: v for k, v in cfg.items() if k in vars(args) and k not in lists})
    args = parser.parse_args(argv)

    # List-valued options from the config file are added to those given on the command line.
    for key in ("sources", "github", "include", "exclude"):
        extra = cfg.get(key, [])
        setattr(args, key, [*getattr(args, key), *([extra] if isinstance(extra, str) else extra)])
    if not args.sources and not args.github:
        parser.error("give at least one source (or --github USER)")

    try:
        with materialize(args.sources, args.github, args.skip_forks, args.github_token) as repos:
            if not repos:
                print("error: no repositories could be read", file=sys.stderr)
                return 1
            print(f"scanning {len(repos)} repo(s)", file=sys.stderr)
            stats = collect(repos, args.include, args.exclude, parse_weights(args.weights))
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    terms = rank(stats, args.top, args.min_files, args.max_zipf, load_ignore(args.ignore_file))
    paths = write_csv(terms, args.output, read_corrections(args.corrections))
    print_top(terms)
    print(f"\nwrote {len(terms)} terms to {', '.join(map(str, paths))}")
    if len(paths) > 1:
        print("note: Wispr Flow imports at most 1,000 entries at a time; import each part file in turn")
    return 0
