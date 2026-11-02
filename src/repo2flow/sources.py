"""Resolve user-supplied sources (URLs, paths, GitHub users) into local repo directories."""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

GITHUB_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
GITHUB_SHORTHAND = re.compile(r"[\w.-]+/[\w.-]+")


@dataclass
class Repo:
    name: str
    path: Path


def classify(spec: str) -> str:
    """Return 'path', 'git', 'shorthand' (owner/repo) or 'user'."""
    if os.path.exists(spec):
        return "path"
    if "://" in spec or spec.startswith("git@") or spec.endswith(".git"):
        return "git"
    if GITHUB_SHORTHAND.fullmatch(spec):
        return "shorthand"
    if GITHUB_NAME.fullmatch(spec):
        return "user"
    raise ValueError(f"cannot tell what this source is: {spec!r}")


def list_github_repos(owner: str, token: str | None, skip_forks: bool) -> list[str]:
    """List clone URLs of a user's or org's public repos via the GitHub REST API."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "repo2flow"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    urls, page = [], 1
    while True:
        api = f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}"
        try:
            with urllib.request.urlopen(urllib.request.Request(api, headers=headers)) as resp:
                batch = json.load(resp)
        except urllib.error.HTTPError as e:
            hint = " (rate limited? set GITHUB_TOKEN)" if e.code == 403 else ""
            raise RuntimeError(f"GitHub API error {e.code} for {owner!r}{hint}") from e
        if not batch:
            return urls
        urls += [r["clone_url"] for r in batch if not (skip_forks and r["fork"])]
        page += 1


def shallow_clone(url: str, dest: Path) -> bool:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
        env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"warning: could not clone {url}: {result.stderr.strip()}", file=sys.stderr)
    return result.returncode == 0


@contextmanager
def materialize(specs: list[str], github_users: list[str], skip_forks: bool, token: str | None):
    """Yield a list of Repo objects; remote clones live in a temp dir removed on exit."""
    token = token or os.environ.get("GITHUB_TOKEN")
    repos: list[Repo] = []
    remote: list[str] = []
    for spec in specs:
        kind = classify(spec)
        if kind == "path":
            path = Path(spec).resolve()
            repos.append(Repo(path.name, path))
        elif kind == "git":
            remote.append(spec)
        elif kind == "shorthand":
            remote.append(f"https://github.com/{spec}.git")
        else:
            github_users = [*github_users, spec]
    for owner in github_users:
        remote += list_github_repos(owner, token, skip_forks)

    with tempfile.TemporaryDirectory(prefix="repo2flow-") as tmp:
        for i, url in enumerate(dict.fromkeys(remote)):
            dest = Path(tmp) / str(i)
            print(f"cloning {url}", file=sys.stderr)
            if shallow_clone(url, dest):
                repos.append(Repo(url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1], dest))
        yield repos
