"""Turn raw text into candidate terms (surface forms), with no language-specific parsing."""

import re

URL_RE = re.compile(r"\w+://\S+")
# Underscores and hyphens are not part of a token, so snake_case and kebab-case
# split into their spoken words for free.
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
# Camel/Pascal pieces: "HTTPServer" -> HTTP, Server; "cuBLAS" -> cu, BLAS.
PIECE_RE = re.compile(r"[A-Z]+(?![a-z])\d*|[A-Z]?[a-z]+\d*")
HEX_RE = re.compile(r"[0-9a-fA-F]{8,}")

MIN_LEN = 3
MAX_LEN = 30


def candidates(text: str) -> set[str]:
    """Return the distinct surface forms in `text` worth considering as terms.

    A camelCase identifier yields both the whole identifier (so "FlashAttention"
    is kept) and its pieces (so "Flash" and "Attention" are scored on their own).
    """
    found = set()
    for token in TOKEN_RE.findall(URL_RE.sub(" ", text)):
        if len(token) > MAX_LEN or HEX_RE.fullmatch(token):
            continue
        pieces = PIECE_RE.findall(token) if token != token.lower() else [token]
        if len(pieces) > 1:
            found.update(p for p in pieces if len(p) >= MIN_LEN)
        if len(token) >= MIN_LEN:
            found.add(token)
    return found
