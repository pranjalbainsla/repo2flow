"""Write Wispr Flow dictionary CSVs and print a sanity-check table."""

import csv
from pathlib import Path

from repo2flow.score import Term

MAX_ROWS = 1000  # Wispr Flow accepts at most 1,000 entries per import
MAX_FIELD = 60  # and 60 characters in the first column


def read_corrections(path: str | None) -> list[tuple[str, str]]:
    """Read optional 'misheard,correct' rows to emit as two-column dictionary entries."""
    if not path:
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [(r[0].strip(), r[1].strip()) for r in csv.reader(f) if len(r) >= 2 and r[0].strip()]


def write_csv(terms: list[Term], out: str, corrections: list[tuple[str, str]]) -> list[Path]:
    """Write a headerless CSV (Wispr would import a header as a word); split past 1,000 rows."""
    rows = [list(c) for c in corrections] + [[t.text] for t in terms]
    rows = [r for r in rows if len(r[0]) <= MAX_FIELD]
    out_path = Path(out)
    chunks = [rows[i:i + MAX_ROWS] for i in range(0, len(rows), MAX_ROWS)] or [[]]
    paths = []
    for n, chunk in enumerate(chunks, 1):
        path = out_path if len(chunks) == 1 else out_path.with_suffix(f".part{n:02d}{out_path.suffix}")
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerows(chunk)
        paths.append(path)
    return paths


def print_top(terms: list[Term], n: int = 50) -> None:
    print(f"\n{'#':>3}  {'term':<28} {'score':>7} {'files':>6} {'repos':>6}")
    for i, t in enumerate(terms[:n], 1):
        print(f"{i:>3}  {t.text:<28} {t.score:>7.2f} {t.files:>6} {t.repos:>6}")
