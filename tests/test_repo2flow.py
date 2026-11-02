import itertools
import subprocess
from collections import Counter

from repo2flow.cli import main
from repo2flow.score import best_casing, rarity
from repo2flow.tokenize import candidates


def test_candidates_split_and_keep_original():
    found = candidates("FlashAttention uses cuBLAS and flash_attn_func, see https://x.io/AbcDef")
    assert {"FlashAttention", "Flash", "Attention", "cuBLAS", "BLAS", "attn", "func"} <= found
    assert "flash_attn_func" not in found and "AbcDef" not in found


def test_candidates_keep_digit_tokens_and_skip_hex():
    found = candidates("k8s deadbeef0123 HTTPServer")
    assert "k8s" in found and "deadbeef0123" not in found
    assert {"HTTPServer", "HTTP", "Server"} <= found


def test_best_casing():
    assert best_casing(Counter({"cublas": 5, "cuBLAS": 1})) == "cuBLAS"
    assert best_casing(Counter({"Kubectl": 1, "kubectl": 1})) == "kubectl"
    assert best_casing(Counter({"Terraform": 4, "terraform": 1})) == "Terraform"


def test_rarity_monotonic():
    assert rarity(0) > rarity(3) > rarity(6)


def test_end_to_end(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "README.md").write_text("We use kubectl and Terraform with the cluster.\n")
    (repo / "docs" / "a.md").write_text("Run kubectl apply. kubectl is great.\n")
    (repo / "main.py").write_text('"""Wraps kubectl."""\nx = 1  # kubectl call\n')
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "junk.js").write_text("kubectl kubectl zzzjunk zzzjunk")
    out = tmp_path / "out.csv"
    assert main([str(repo), "-o", str(out), "--min-files", "2"]) == 0
    lines = out.read_text().splitlines()
    assert lines[0] == "kubectl"
    assert "zzzjunk" not in lines
    assert "the" not in lines
    # deterministic
    out2 = tmp_path / "out2.csv"
    main([str(repo), "-o", str(out2)])
    assert out.read_text() == out2.read_text()


def test_ignore_and_split(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    names = ("qzx" + "".join(c) + "k" for c in itertools.product("abcdefghijklmnopqrstuvwxyz", repeat=2))
    words = " ".join(itertools.islice(names, 676)) + " " + " ".join(f"qzy{i}k" for i in range(600))
    (repo / "a.md").write_text(words)
    (repo / "b.md").write_text(words)
    out = tmp_path / "t.csv"
    main([str(repo), "-o", str(out), "--top", "1100", "--ignore-file", str(_ignore(tmp_path))])
    parts = sorted(tmp_path.glob("t.part*.csv"))
    assert len(parts) == 2
    assert len(parts[0].read_text().splitlines()) == 1000
    assert "qzxaak" not in parts[0].read_text() + parts[1].read_text()


def _ignore(tmp_path):
    p = tmp_path / "ignore.txt"
    p.write_text("# comment\nQZXAAK\n")
    return p


def test_local_git_clone(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text("cublas cublas\n")
    (src / "b.md").write_text("cublas\n")
    run = lambda *a: subprocess.run(["git", "-C", str(src), *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q"); run("add", "."); run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
    out = tmp_path / "o.csv"
    assert main([f"file://{src}", "-o", str(out)]) == 0
    assert out.read_text().strip() == "cublas"
