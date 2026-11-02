# repo2flow

Turn your own code repositories into a CSV for [Wispr Flow](https://wisprflow.ai)'s dictionary, so dictation stops mangling the jargon of your field ("cuBLAS" → "Hubloss", "kubectl" → "cube cuddle").

Nothing is hardcoded about any person, language or domain: you supply repos, you get your own terms. It runs offline once the repos are on disk. It needs no accounts or API keys (a GitHub token is optional, only to raise API rate limits).

## Install

```bash
pip install -e .          # Python 3.11+, needs git on PATH; only dependency is wordfreq
```

## Usage

Sources can be git URLs, local paths, `owner/repo`, or a GitHub user/org (all public repos). Mix freely.

**Machine learning developer**
```bash
repo2flow karpathy/nanoGPT https://github.com/Dao-AILab/flash-attention.git ~/code/my-training-repo \
    --top 300 -o ml-terms.csv
```

**DevOps engineer**
```bash
repo2flow my-company-org --skip-forks --exclude 'vendor/*' --exclude '*.generated.*' \
    --weights docs=4,comments=2,code=1 --ignore-file my-ignore.txt -o devops-terms.csv
```

Remote repos are shallow-cloned into a temp directory that is deleted afterwards. Then import the CSV in Wispr Flow: *Settings → Experimental → enable Bulk import*, then use **Import** in the Dictionary.

### Config file

Every flag can live in a TOML file (`repo2flow --config me.toml`); list options are merged with the command line.

```toml
sources = ["karpathy/nanoGPT", "~/code/work-repo"]
github = ["my-org"]
skip-forks = true
top = 400
exclude = ["tests/fixtures/*"]
weights = { docs = 4, comments = 2, code = 1 }
```

### Flags

| Flag | Meaning |
|---|---|
| `SOURCE...`, `--github USER` | what to scan |
| `--skip-forks` | skip forks when expanding a GitHub user/org |
| `--github-token` / `$GITHUB_TOKEN` | optional, raises API rate limits |
| `--include GLOB` / `--exclude GLOB` | path filters (repeatable) |
| `--top N` (300) | terms to keep |
| `--min-files N` (2) | term must appear in at least N distinct files |
| `--max-zipf Z` (3.5) | drop words more common than this (see below) |
| `--weights docs=3,comments=2,code=1` | source-layer weights |
| `--ignore-file F` | terms to exclude, one per line, `#` comments allowed |
| `--corrections F` | CSV of `misheard,correct` rows, emitted as two-column entries |
| `-o PATH` | output (default `repo2flow.csv`) |

## Output format

Per [Wispr's docs](https://docs.wisprflow.ai/articles/8955301725-how-do-i-bulk-import-for-dictionary-and-snippets): one term per row, **no header** (it would import as a word), optional second column for a replacement, at most **1,000 entries per import** and 60 characters in the first field. If you ask for more than 1,000 terms, repo2flow writes `name.part01.csv`, `name.part02.csv`, … to import one at a time.

## How scoring works

1. **Layers.** Each file is split into *docs* (`.md`, `.rst`, `.txt`, …), *comments/docstrings* (found via a small table of comment delimiters per file extension, not language parsers) and *code* (everything else). People dictate what they say aloud, so docs weigh most (default 3 / 2 / 1).
2. **Tokens.** `snake_case` and `kebab-case` split into words. `camelCase` is split too, but the original is kept: `FlashAttention` yields `FlashAttention`, `Flash` and `Attention`; `cuBLAS` yields `cuBLAS`, `cu`, `BLAS`. Tokens under 3 or over 30 characters, hex strings and URLs are ignored.
3. **Weight.** For each term, `W` = sum over the files containing it of the weight of its *best* layer in that file. A term counts once per file, so a single huge file can't dominate.
4. **Rarity.** `zipf` comes from [`wordfreq`](https://github.com/rspeer/wordfreq) (about 7.7 for "the", 0 for unknown words like "cublas"). Words with `zipf > --max-zipf` are dropped as common English. The rest get `rarity = ((8 − zipf) / 8)²`.
5. **Score.**

   ```
   score = rarity × log2(1 + W) × (1 + 0.5 × log2(distinct repos))
   ```
   Terms must appear in `--min-files` files. Ranking is by score, with ties broken alphabetically, so output is deterministic.
6. **Casing.** Terms are merged case-insensitively. The spelling kept is the most common *mixed-case* form (`cuBLAS`), otherwise the most common form, preferring lower > Title > UPPER on ties (so sentence-initial "Kubectl" doesn't win).

## Known limitations

- Comment detection is delimiter-based, so a `#` or `//` inside a string literal is treated as a comment start. That's harmless noise.
- Universal programming words that are uncommon in English (`isinstance`, `ifndef`) and names in copyright headers can rank high. Put them in `--ignore-file` once and reuse it.
- `wordfreq` is English-only here; terms in other languages look "rare".

## Development

```bash
pip install -e '.[dev]' && pytest
```

MIT licensed.
