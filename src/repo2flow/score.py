"""Aggregate candidate terms across files/repos and rank them by rarity-weighted score."""

import math
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from wordfreq import zipf_frequency

from repo2flow.extract import iter_files, layers, read_text
from repo2flow.sources import Repo
from repo2flow.tokenize import candidates

DEFAULT_WEIGHTS = {"docs": 3.0, "comments": 2.0, "code": 1.0}
ZIPF_CEILING = 8.0  # zipf of the most common English words is ~7.7


@dataclass
class Stat:
    files: int = 0
    weight: float = 0.0
    repos: set[str] = field(default_factory=set)
    forms: Counter = field(default_factory=Counter)  # surface form -> number of files


@dataclass
class Term:
    key: str
    text: str
    score: float
    files: int
    repos: int


def collect(repos: list[Repo], include, exclude, weights) -> dict[str, Stat]:
    """Scan every file once; per file, each term counts once at its best layer's weight."""
    stats: dict[str, Stat] = {}
    for repo in repos:
        for rel, path in iter_files(repo.path, include, exclude):
            text = read_text(path)
            if text is None:
                continue
            best: dict[str, float] = {}  # lowercase key -> best layer weight in this file
            file_forms: dict[str, set[str]] = {}
            for layer, layer_text in layers(rel, text):
                for form in candidates(layer_text):
                    key = form.lower()
                    best[key] = max(best.get(key, 0.0), weights[layer])
                    file_forms.setdefault(key, set()).add(form)
            for key, weight in best.items():
                stat = stats.setdefault(key, Stat())
                stat.files += 1
                stat.weight += weight
                stat.repos.add(repo.name)
                stat.forms.update(file_forms[key])
    return stats


def is_mixed(form: str) -> bool:
    """True for names like 'cuBLAS' or 'FlashAttention' (an inner capital plus a lowercase)."""
    return any(c.isupper() for c in form[1:]) and any(c.islower() for c in form)


def best_casing(forms: Counter) -> str:
    """Prefer the most common mixed-case spelling; else the most common, lower > Title > UPPER."""
    mixed = {f: n for f, n in forms.items() if is_mixed(f)}
    pool = mixed or forms
    rank = lambda f: (pool[f], f.islower(), not f.isupper(), f)  # noqa: E731
    return max(pool, key=rank)


@lru_cache(maxsize=None)
def zipf(word: str) -> float:
    return zipf_frequency(word, "en")


def rarity(z: float) -> float:
    return ((ZIPF_CEILING - z) / ZIPF_CEILING) ** 2


def rank(stats: dict[str, Stat], top: int, min_files: int, max_zipf: float, ignore: set[str]) -> list[Term]:
    terms = []
    for key, stat in stats.items():
        if stat.files < min_files or key in ignore:
            continue
        z = zipf(key)
        if z > max_zipf:
            continue
        score = rarity(z) * math.log2(1 + stat.weight) * (1 + 0.5 * math.log2(len(stat.repos)))
        terms.append(Term(key, best_casing(stat.forms), score, stat.files, len(stat.repos)))
    terms.sort(key=lambda t: (-t.score, t.key))
    return terms[:top]


def load_ignore(path: str | None) -> set[str]:
    if not path:
        return set()
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return {l.strip().lower() for l in lines if l.strip() and not l.lstrip().startswith("#")}
