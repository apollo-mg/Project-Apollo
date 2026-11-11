"""The Qwen 4 kit (2026-11-11): abstend.py scaffold against canned Hugging Face API answers, and fetch against a local web
server. No network, no /mnt path: scaffold's API and fetch's base URL are pointed at fixtures."""
import functools, hashlib, http.server, json, threading
import pytest
import abstend

REV = "a" * 40


def oid(k): return f"{k:064x}"


def canned(tree, gen=None):
    """A stand-in for abstend.hf_json: revision -> REV, tree -> one page, generation_config.json -> gen or an error."""
    def hf_json(url):
        if "/revision/" in url: return {"sha": REV}, None
        if "/tree/" in url: return [{"type": "file", "path": p, "size": s, **({"lfs": {"oid": o}} if o else {})} for p, (s, o) in tree.items()], None
        if url.endswith("generation_config.json") and gen: return gen, None
        raise OSError("404")
    return hf_json


def fill(rc):
    """What a person writes over the CHOOSE placeholders."""
    rc["model"].update(arch="dense", total_b=27, active_b=27, lineage=None)
    for m in ("sampled", "vendor"):
        rc["modes"][m].update(sampling={"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0}, sampling_source="card: thinking, general")
    if "abench" in rc: rc["abench"]["template_kwargs"] = {"enable_thinking": False}
    return rc


def test_scaffold_split_in_a_subfolder(monkeypatch):
    tree = {"UD-Q4_K_XL/Toy-UD-Q4_K_XL-00002-of-00002.gguf": (5, oid(2)), "UD-Q4_K_XL/Toy-UD-Q4_K_XL-00001-of-00002.gguf": (7, oid(1)),
            "Toy-Q8_0.gguf": (9, oid(3)), "README.md": (10, None)}
    monkeypatch.setattr(abstend, "hf_json", canned(tree))
    rc = abstend.scaffold("org/Toy-GGUF", "toy-27b", "spark-x2.6-4b", "Toy-UD-Q4_K_XL-00001-of-*.gguf", prefix="TOY", stdout=True)
    f = rc["file"]
    assert f["revision"] == REV and f["subdir"] == "UD-Q4_K_XL" and f["quant"] == "UD-Q4_K_XL"
    assert [p["name"] for p in f["parts"]] == ["Toy-UD-Q4_K_XL-00001-of-00002.gguf", "Toy-UD-Q4_K_XL-00002-of-00002.gguf"]
    assert (f["name"], f["sha256"]) == ("Toy-UD-Q4_K_XL-00001-of-00002.gguf", oid(1))
    assert [m["arm"] for m in rc["modes"].values()] == ["TOYG", "TOYS", "TOYV"]
    with pytest.raises(SystemExit, match="CHOOSE placeholder"): abstend.validate(rc, "toy-27b.json")
    abstend.validate(fill(rc), "toy-27b.json")   # once a person has decided, it is a valid recipe


def test_scaffold_split_at_the_top_level(monkeypatch):   # the bug found live on Scantist/GLM-5.3-SLIM-GGUF
    tree = {f"Toy-E192-0000{k}-of-00003.gguf": (k, oid(k)) for k in (1, 2, 3)}
    monkeypatch.setattr(abstend, "hf_json", canned(tree))
    rc = abstend.scaffold("org/Toy", "toy-slim", "spark-x2.6-4b", "*00001-of-00003.gguf", stdout=True)
    assert len(rc["file"]["parts"]) == 3 and "subdir" not in rc["file"]


def test_scaffold_refuses_a_missing_shard_and_an_ambiguous_glob(monkeypatch):
    monkeypatch.setattr(abstend, "hf_json", canned({"Toy-00001-of-00002.gguf": (1, oid(1))}))
    with pytest.raises(SystemExit, match="1 shards found, the name says 2"):
        abstend.scaffold("org/Toy", "toy", "spark-x2.6-4b", "*00001-of-00002.gguf", stdout=True)
    monkeypatch.setattr(abstend, "hf_json", canned({"Toy-Q8_0.gguf": (1, oid(1)), "Toy-Q6_K.gguf": (1, oid(2))}))
    with pytest.raises(SystemExit, match="matches 2 files"):
        abstend.scaffold("org/Toy", "toy", "spark-x2.6-4b", "Toy-Q*.gguf", stdout=True)


@pytest.fixture
def hub(tmp_path):
    """A local stand-in for huggingface.co serving org/toy at REV: two shards, and their real sha256s."""
    root = tmp_path / "hub"; d = root / "org" / "toy" / "resolve" / REV; d.mkdir(parents=True)
    data = {"Toy-00001-of-00002.gguf": b"first shard " * 1000, "Toy-00002-of-00002.gguf": b"second shard " * 1000}
    for n, b in data.items(): (d / n).write_bytes(b)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root)))
    srv.RequestHandlerClass.log_message = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", {n: hashlib.sha256(b).hexdigest() for n, b in data.items()}
    srv.shutdown()


def toy_recipe(tmp_path, shas):
    names = sorted(shas)
    return {"file": {"repo": "org/toy", "revision": REV, "name": names[0], "sha256": shas[names[0]], "store": str(tmp_path / "store"),
                     "parts": [{"name": n, "sha256": shas[n]} for n in names]}}


def test_fetch_downloads_checks_and_skips(monkeypatch, tmp_path, hub, capsys):
    url, shas = hub
    monkeypatch.setattr(abstend, "HF", url); monkeypatch.setattr(abstend, "hf_tree", lambda repo, rev: {n: (24000, s) for n, s in shas.items()})
    rc = toy_recipe(tmp_path, shas)
    assert abstend.fetch(tmp_path / "toy.json", rc)
    store = tmp_path / "store"
    for n, s in shas.items():
        assert hashlib.sha256((store / n).read_bytes()).hexdigest() == s and (store / f"{n}.sha256").read_text() == f"{s}  {n}\n"
    capsys.readouterr()
    assert abstend.fetch(tmp_path / "toy.json", rc)   # a rerun downloads nothing
    assert capsys.readouterr().out.count("already there") == 2


def test_fetch_renames_a_mismatch_and_fails(monkeypatch, tmp_path, hub):
    url, shas = hub
    monkeypatch.setattr(abstend, "HF", url); monkeypatch.setattr(abstend, "hf_tree", lambda repo, rev: {})
    rc = toy_recipe(tmp_path, {**shas, "Toy-00002-of-00002.gguf": "f" * 64})
    assert not abstend.fetch(tmp_path / "toy.json", rc)
    assert (tmp_path / "store" / "Toy-00002-of-00002.gguf.bad").exists() and not (tmp_path / "store" / "Toy-00002-of-00002.gguf").exists()


def test_fetch_needs_the_full_revision(tmp_path):
    rc = {"file": {"repo": "org/toy", "revision": "aaaaaaaa", "name": "x.gguf", "sha256": "0" * 64, "store": str(tmp_path)}}
    with pytest.raises(SystemExit, match="full 40-hex"): abstend.fetch(tmp_path / "toy.json", rc)


def test_mode_order_and_the_sampled_mode():
    p, rc = abstend.HERE / "recipes" / "spark-x2.6-4b.json", json.load(open(abstend.HERE / "recipes" / "spark-x2.6-4b.json"))
    rc["modes"] = {"vendor": rc["modes"]["vendor"], "greedy": rc["modes"]["greedy"],
                   "sampled": {**rc["modes"]["vendor"], "arm": "S26S", "thinking": False, "max_tokens": 1024}}
    assert [k for k, _ in abstend.ordered(rc)] == ["greedy", "sampled", "vendor"]
    abstend.validate(rc, p)
    rc["modes"]["sampled"]["thinking"] = True
    with pytest.raises(SystemExit, match="the sampled mode is thinking off with sampling"): abstend.validate(rc, p)
