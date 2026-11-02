"""Walk a repository and split each file into weighted text layers."""

import os
import re
from fnmatch import fnmatch
from pathlib import Path

SKIP_DIRS = {"node_modules", "vendor", "dist", "build", "target", "__pycache__", "site-packages"}
SKIP_EXTS = {".json", ".lock", ".csv", ".tsv", ".svg", ".ipynb", ".map", ".min.js", ".min.css"}
SKIP_NAMES = ("license", "copying", "notice")  # boilerplate shared by every project
DOC_EXTS = {".md", ".markdown", ".rst", ".txt", ".adoc", ".org"}
MAX_BYTES = 1_000_000

# Comment syntax by extension. This is a table of delimiters, not a parser.
SLASH = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
HASH = re.compile(r"#[^\n]*")
HASH_PY = re.compile(r"#[^\n]*|\"\"\".*?\"\"\"|'''.*?'''", re.S)
DASH = re.compile(r"--[^\n]*")
COMMENT_RES = {}
for exts, regex in [
    ("c h cc cpp hpp cu cuh java js jsx ts tsx go rs swift kt scala cs php dart", SLASH),
    ("py", HASH_PY),
    ("sh bash zsh rb pl r yaml yml toml tf hcl cmake mk", HASH),
    ("sql lua hs", DASH),
]:
    for ext in exts.split():
        COMMENT_RES["." + ext] = regex


def iter_files(root: Path, include: list[str], exclude: list[str]):
    """Yield (relative posix path, absolute path) for candidate text files, sorted."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath, name)
            rel = path.relative_to(root).as_posix()
            lower = name.lower()
            if lower.startswith(SKIP_NAMES) or lower.endswith(tuple(SKIP_EXTS)):
                continue
            if include and not any(fnmatch(rel, g) for g in include):
                continue
            if any(fnmatch(rel, g) for g in exclude):
                continue
            yield rel, path


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="ignore")


def layers(rel: str, text: str) -> list[tuple[str, str]]:
    """Split a file into (layer name, text) pairs: docs, or comments + code."""
    ext = Path(rel).suffix.lower()
    if ext in DOC_EXTS:
        return [("docs", text)]
    out = [("code", text)]
    regex = COMMENT_RES.get(ext)
    if regex:
        out.append(("comments", "\n".join(m.group(0) for m in regex.finditer(text))))
    return out
