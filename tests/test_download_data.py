"""Tests for scripts/download_data.py. Offline except the one test marked `network`."""

import dataclasses
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("download_data", ROOT / "scripts/download_data.py")
dd = importlib.util.module_from_spec(spec)
sys.modules["download_data"] = dd  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(dd)


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def remote_for(src: Path, **overrides) -> "dd.Remote":
    """A Remote serving `src` from a file:// URL, pinned to its real size and hash."""
    data = src.read_bytes()
    fields = {
        "dataset": "Test",
        "path": f"test/{src.name}",
        "url": src.as_uri(),
        "ref": "test",
        "licence": "test",
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return dd.Remote(**(fields | overrides))


@pytest.fixture
def fake_glucobench(tmp_path, monkeypatch):
    """Point the GlucoBench pin at a small local zip with the real archive's layout."""
    archive = make_zip(
        tmp_path / "raw_data.zip",
        {
            "raw_data/weinstock.csv": b"id,gl,time\n1,100,1900-01-01 00:00:00\n",
            "raw_data/colas.csv": b",id,time,gl\n0,1,2012-01-01 00:00:00,86\n",
            "raw_data/.DS_Store": b"junk",
            "__MACOSX/raw_data/._weinstock.csv": b"junk",
        },
    )
    remote = remote_for(archive, path=dd.GLUCOBENCH.path, dataset=dd.GLUCOBENCH.dataset)
    monkeypatch.setattr(dd, "GLUCOBENCH", remote)
    return remote


def test_fetch_verifies_and_skips_identical_copy(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 1000)
    remote = remote_for(src)
    raw = tmp_path / "raw"

    facts, downloaded = dd.fetch(remote, raw)
    assert downloaded and facts["sha256"] == remote.sha256
    assert (raw / remote.path).read_bytes() == src.read_bytes()

    src.unlink()  # a second call must not touch the network (here: the missing source)
    facts, downloaded = dd.fetch(remote, raw)
    assert not downloaded and facts["sha256"] == remote.sha256


def test_fetch_rejects_hash_mismatch_and_leaves_nothing(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"payload")
    remote = remote_for(src, sha256="0" * 64)
    raw = tmp_path / "raw"
    with pytest.raises(dd.DownloadError, match="sha256"):
        dd.fetch(remote, raw)
    assert not (raw / remote.path).exists()
    assert not list(raw.rglob("*.part"))


def test_fetch_checks_md5_when_only_md5_is_published(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"payload")
    good = remote_for(src, sha256=None, md5=hashlib.md5(b"payload").hexdigest())
    assert dd.fetch(good, tmp_path / "a")[1]
    with pytest.raises(dd.DownloadError, match="md5"):
        dd.fetch(dataclasses.replace(good, md5="f" * 32), tmp_path / "b")


def test_fetch_replaces_a_corrupted_copy(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"good bytes")
    remote = remote_for(src)
    dest = tmp_path / "raw" / remote.path
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"bad bytes!")
    assert dd.fetch(remote, tmp_path / "raw")[1]
    assert dest.read_bytes() == b"good bytes"


def test_fetch_reports_unreachable_url(tmp_path):
    missing = tmp_path / "missing.bin"
    remote = dd.Remote("Test", "test/missing.bin", missing.as_uri(), "test", "test")
    with pytest.raises(dd.DownloadError):
        dd.fetch(remote, tmp_path / "raw")
    assert not list((tmp_path / "raw").rglob("*.part"))


def test_extract_strips_prefix_and_skips_junk(tmp_path):
    archive = make_zip(
        tmp_path / "a.zip",
        {
            "raw_data/": b"",
            "raw_data/a.csv": b"a",
            "raw_data/sub/b.csv": b"b",
            "raw_data/.DS_Store": b"junk",
            "raw_data/._a.csv": b"junk",
            "__MACOSX/raw_data/._a.csv": b"junk",
            "other/c.csv": b"c",
        },
    )
    out = tmp_path / "out"
    written = dd.extract(archive, "raw_data/", out)
    assert sorted(p.relative_to(out).as_posix() for _, p in written) == ["a.csv", "sub/b.csv"]
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "a.csv",
        "sub/b.csv",
    ]


@pytest.mark.parametrize("bad", ["raw_data/../evil.csv", "raw_data/sub/../../evil.csv"])
def test_extract_refuses_paths_that_escape(tmp_path, bad):
    archive = make_zip(tmp_path / "a.zip", {bad: b"evil"})
    with pytest.raises(dd.DownloadError, match="unsafe"):
        dd.extract(archive, "raw_data/", tmp_path / "out")
    assert not list(tmp_path.rglob("evil.csv"))


def test_extract_does_not_rewrite_identical_members(tmp_path):
    archive = make_zip(tmp_path / "a.zip", {"raw_data/a.csv": b"a"})
    out = tmp_path / "out"
    dd.extract(archive, "raw_data/", out)
    target = out / "a.csv"
    before = target.stat().st_mtime_ns
    dd.extract(archive, "raw_data/", out)
    assert target.stat().st_mtime_ns == before


def test_main_writes_manifest_for_archive_and_members(tmp_path, fake_glucobench, capsys):
    assert dd.main(["--data-dir", str(tmp_path / "data")]) == 0
    raw = tmp_path / "data" / "raw"
    manifest = json.loads((raw / "MANIFEST.json").read_text())

    files = manifest["files"]
    assert set(files) == {
        "glucobench/raw_data.zip",
        "glucobench/weinstock.csv",
        "glucobench/colas.csv",
    }
    archive = files["glucobench/raw_data.zip"]
    assert archive["sha256"] == fake_glucobench.sha256
    assert archive["size_bytes"] == fake_glucobench.size
    assert {"url", "ref", "licence", "retrieved_at", "dataset"} <= set(archive)

    weinstock = files["glucobench/weinstock.csv"]
    csv_bytes = (raw / "glucobench/weinstock.csv").read_bytes()
    assert weinstock["dataset"] == "Weinstock 2016"
    assert weinstock["archive_member"] == "raw_data/weinstock.csv"
    assert weinstock["sha256"] == hashlib.sha256(csv_bytes).hexdigest()
    assert "Manual downloads" in capsys.readouterr().out


def test_main_is_idempotent_and_keeps_other_entries(tmp_path, fake_glucobench):
    data = tmp_path / "data"
    raw = data / "raw"
    raw.mkdir(parents=True)
    other = {"dataset": "DiaData 2026", "sha256": "abc", "retrieved_at": "2026-01-01T00:00:00Z"}
    (raw / "MANIFEST.json").write_text(json.dumps({"files": {"diadata/README.md": other}}))

    assert dd.main(["--data-dir", str(data)]) == 0
    first = json.loads((raw / "MANIFEST.json").read_text())["files"]
    assert first["diadata/README.md"] == other

    assert dd.main(["--data-dir", str(data)]) == 0
    second = json.loads((raw / "MANIFEST.json").read_text())["files"]
    assert second == first  # same hashes, first retrieval dates kept


def test_main_records_manually_placed_files(tmp_path, fake_glucobench):
    data = tmp_path / "data"
    (data / "raw" / "cgmacros").mkdir(parents=True)
    (data / "raw" / "cgmacros" / "subject1.csv").write_text("time,cgm\n")
    assert dd.main(["--data-dir", str(data)]) == 0
    files = json.loads((data / "raw" / "MANIFEST.json").read_text())["files"]
    assert files["cgmacros/subject1.csv"]["dataset"] == "CGMacros"
    assert files["cgmacros/subject1.csv"]["ref"] == "manual download"


def test_main_fails_on_hash_mismatch(tmp_path, fake_glucobench, monkeypatch, capsys):
    monkeypatch.setattr(dd, "GLUCOBENCH", dataclasses.replace(fake_glucobench, sha256="0" * 64))
    assert dd.main(["--data-dir", str(tmp_path / "data")]) == 1
    assert "sha256" in capsys.readouterr().err
    assert not (tmp_path / "data/raw/glucobench/raw_data.zip").exists()


def test_pins_point_at_fixed_versions():
    assert dd.GLUCOBENCH_COMMIT in dd.GLUCOBENCH.url
    assert dd.GLUCOBENCH.sha256 and dd.GLUCOBENCH.size
    assert all(r.md5 and r.size and dd.DIADATA_RECORD in r.url for r in dd.DIADATA)
    assert dd.AZT1D.sha256 and dd.AZT1D.size and "gk9m674wcx" in dd.AZT1D.url


@pytest.mark.network
def test_real_glucobench_download(tmp_path):
    assert dd.main(["--data-dir", str(tmp_path)]) == 0
    raw = tmp_path / "raw"
    files = json.loads((raw / "MANIFEST.json").read_text())["files"]
    assert files["glucobench/raw_data.zip"]["sha256"] == dd.GLUCOBENCH.sha256
    for name in dd.GLUCOBENCH_MEMBERS:
        assert (raw / "glucobench" / name).stat().st_size > 0
        assert f"glucobench/{name}" in files
