"""Download the public datasets listed in docs/DATA.md into data/raw/ and record them in a manifest.

By default this fetches GlucoBench's raw_data.zip (5.6 MB) and extracts its CSVs. --diadata adds
the DiaData 5-minute archive (2.3 GB) and --azt1d the AZT1D archive (776 MB), neither extracted.
CGMacros and OhioT1DM need a manual download; instructions are printed, and files placed in their
folders are added to the manifest.

Every remote file is pinned to an upstream version and checked against a published hash, so a
changed upstream file fails loudly instead of silently changing results. data/raw/MANIFEST.json
records URL, retrieval date, size and SHA-256 for every file.

Standard library only (Python 3.11+), so it runs with or without the project environment:

    uv run python scripts/download_data.py [--diadata] [--force] [--data-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import shutil
import sys
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1 << 20
JUNK_NAMES = {".DS_Store", "Thumbs.db"}


class DownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Remote:
    """A file to download, pinned to an upstream version and hash."""

    dataset: str  # key in docs/CITATIONS.md
    path: str  # destination, relative to data/raw/
    url: str
    ref: str  # upstream version the URL points at
    licence: str  # as stated by the source; see docs/DATA.md
    size: int | None = None
    sha256: str | None = None
    md5: str | None = None


# GlucoBench at the commit checked on 2026-10-18 (docs/DATA.md §1). The URL names the commit,
# not a branch, so the bytes cannot change under us; the SHA-256 is of that file.
GLUCOBENCH_COMMIT = "661d840a98b316df51faa13a7100430afcbbb5b7"
GLUCOBENCH = Remote(
    dataset="GlucoBench 2024",
    path="glucobench/raw_data.zip",
    url=f"https://raw.githubusercontent.com/IrinaStatsLab/GlucoBench/{GLUCOBENCH_COMMIT}/raw_data.zip",
    ref=f"IrinaStatsLab/GlucoBench@{GLUCOBENCH_COMMIT}",
    licence="per dataset (GlucoBench README); the repository itself has no licence",
    size=5_639_441,
    sha256="aecc5a50bd6b09799b90eddf127c8270e7292fee6840ac822f0e8092569fff61",
)
GLUCOBENCH_PREFIX = "raw_data/"
# Archive member -> (dataset key, licence as stated in the GlucoBench README).
GLUCOBENCH_MEMBERS = {
    "weinstock.csv": ("Weinstock 2016", "CC BY-SA 4.0 (per GlucoBench)"),
    "dubosson.csv": ("Dubosson 2018", "CC BY-SA 4.0 (per GlucoBench)"),
    "hall.csv": ("Hall 2018", "CC BY 4.0 (per GlucoBench)"),
    "colas.csv": ("Colás 2019", "CC 4.0 per GlucoBench text; its link is CC BY 3.0 US"),
    "iglu.csv": ("Broll 2021", "GPL-2 (per GlucoBench)"),
}

# DiaData v3 on Zenodo (concept DOI 10.5281/zenodo.16874128). Zenodo publishes MD5 checksums;
# SHA-256 is computed on download and recorded in the manifest.
DIADATA_RECORD = "17285631"
DIADATA = [
    Remote(
        dataset="DiaData 2026",
        path=f"diadata/{name}",
        url=f"https://zenodo.org/records/{DIADATA_RECORD}/files/{name}?download=1",
        ref=f"zenodo:{DIADATA_RECORD} (v3)",
        licence="CC BY-NC 4.0",
        size=size,
        md5=md5,
    )
    for name, size, md5 in [
        ("README.md", 4_591, "34dd49570ec6bed002d20f053929556a"),
        ("Demographics.csv", 132_128, "bfdad21f65f60d79eb6bf3d293916954"),
        ("5_min_sampling.zip", 2_341_562_516, "5a7f9eae1c59e4c3c65c0b5b25367b47"),
    ]
]

# AZT1D v1 on Mendeley Data (doi:10.17632/gk9m674wcx.1), the file listed by Mendeley's public
# API on 2026-10-18, which publishes its SHA-256. Kept zipped; the loader reads the archive.
AZT1D = Remote(
    dataset="AZT1D 2025",
    path="azt1d/AZT1D_2025.zip",
    url=(
        "https://data.mendeley.com/public-files/datasets/gk9m674wcx/files/"
        "b02a20be-27c4-4dd0-8bb5-9171c66262fb/file_downloaded"
    ),
    ref="mendeley:gk9m674wcx (v1)",
    licence="CC BY 4.0",
    size=776_131_685,
    sha256="2c6b4183fdc729c708c1b3230ab1988d2c9006dd35729537f2de07f649f0d113",
)

# Datasets that need a sign-in, a click-through licence or a data use agreement.
MANUAL = [
    ("CGMacros", "cgmacros", "https://physionet.org/content/cgmacros/1.0.0/", "CC BY-NC-SA 4.0"),
    (
        "OhioT1DM",
        "ohiot1dm",
        "https://webpages.charlotte.edu/rbunescu/data/ohiot1dm/OhioT1DM-dataset.html",
        "data use agreement",
    ),
]


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def human(n: float) -> str:
    for unit in ["B", "kB", "MB"]:
        if n < 1000:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} GB"


def file_facts(path: Path) -> dict:
    """Size, SHA-256 and MD5 of a file."""
    sha256, md5, size = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            sha256.update(chunk)
            md5.update(chunk)
            size += len(chunk)
    return {"size_bytes": size, "sha256": sha256.hexdigest(), "md5": md5.hexdigest()}


def mismatches(facts: dict, remote: Remote) -> list[str]:
    expected = {"size_bytes": remote.size, "sha256": remote.sha256, "md5": remote.md5}
    return [
        f"{key} is {facts[key]}, expected {want}"
        for key, want in expected.items()
        if want is not None and facts[key] != want
    ]


def fetch(remote: Remote, raw_dir: Path, force: bool = False) -> tuple[dict, bool]:
    """Download `remote` unless an identical copy is already there.

    Returns the file's facts and whether it was downloaded. Raises DownloadError if the
    downloaded bytes do not match the pins; nothing is left at the destination in that case.
    """
    dest = raw_dir / remote.path
    if dest.exists() and not force:
        facts = file_facts(dest)
        if not mismatches(facts, remote):
            print(f"present   {remote.path} ({human(facts['size_bytes'])}, hashes match)")
            return facts, False
        print(f"stale     {remote.path} does not match its pins; downloading again")

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    print(f"download  {remote.path} <- {remote.url}")
    sha256, md5, size = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
    request = urllib.request.Request(remote.url, headers={"User-Agent": "ghostlows-download"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as out:
            total = int(response.headers.get("Content-Length") or 0) or remote.size
            next_report = 0.1
            while chunk := response.read(CHUNK):
                out.write(chunk)
                sha256.update(chunk)
                md5.update(chunk)
                size += len(chunk)
                if total and total > 100 * CHUNK and size / total >= next_report:
                    print(f"          {size / total:4.0%} of {human(total)}")
                    next_report += 0.1
    except (OSError, http.client.HTTPException) as exc:  # URLError and timeouts are OSErrors
        part.unlink(missing_ok=True)
        raise DownloadError(f"{remote.url}: {exc}") from exc

    facts = {"size_bytes": size, "sha256": sha256.hexdigest(), "md5": md5.hexdigest()}
    problems = mismatches(facts, remote)
    if problems:
        part.unlink()
        raise DownloadError(f"{remote.url}: " + "; ".join(problems))
    part.replace(dest)
    print(f"verified  {remote.path} ({human(size)}, sha256 {facts['sha256'][:12]}…)")
    return facts, True


def crc32(path: Path) -> int:
    value = 0
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            value = zlib.crc32(chunk, value)
    return value


def extract(archive: Path, prefix: str, out_dir: Path) -> list[tuple[str, Path]]:
    """Extract the members under `prefix` into `out_dir`, dropping the prefix.

    Skips directories, macOS metadata and members outside `prefix`. Refuses members whose
    path would escape `out_dir`. A member already present with the same CRC-32 is not rewritten.
    Returns (member name, written path) pairs.
    """
    written = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            rel = PurePosixPath(info.filename[len(prefix) :])
            if rel.name in JUNK_NAMES or rel.name.startswith("._") or "__MACOSX" in rel.parts:
                continue
            if rel.is_absolute() or ".." in rel.parts or "\\" in info.filename:
                raise DownloadError(f"{archive}: refusing unsafe member path {info.filename!r}")
            target = out_dir.joinpath(*rel.parts)
            if not (target.exists() and crc32(target) == info.CRC):
                target.parent.mkdir(parents=True, exist_ok=True)
                part = target.with_name(target.name + ".part")
                with zf.open(info) as src, part.open("wb") as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
                part.replace(target)
                print(f"extract   {target.name} ({human(info.file_size)})")
            written.append((info.filename, target))
    return written


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"files": {}}


def record(manifest: dict, rel_path: str, entry: dict) -> None:
    """Add or update a manifest entry, keeping the first retrieval date of unchanged files."""
    old = manifest["files"].get(rel_path)
    if old and old.get("sha256") == entry["sha256"]:
        entry["retrieved_at"] = old.get("retrieved_at", entry["retrieved_at"])
    manifest["files"][rel_path] = entry


def remote_entry(remote: Remote, facts: dict) -> dict:
    return {
        "dataset": remote.dataset,
        "url": remote.url,
        "ref": remote.ref,
        "licence": remote.licence,
        "retrieved_at": now(),
        **facts,
    }


def download_glucobench(raw_dir: Path, manifest: dict, force: bool) -> None:
    remote = GLUCOBENCH
    facts, _ = fetch(remote, raw_dir, force)
    record(manifest, remote.path, remote_entry(remote, facts))
    archive = raw_dir / remote.path
    for member, target in extract(archive, GLUCOBENCH_PREFIX, archive.parent):
        dataset, licence = GLUCOBENCH_MEMBERS.get(target.name, (remote.dataset, remote.licence))
        entry = {
            "dataset": dataset,
            "from_archive": remote.path,
            "archive_member": member,
            "ref": remote.ref,
            "licence": licence,
            "retrieved_at": now(),
            **file_facts(target),
        }
        record(manifest, target.relative_to(raw_dir).as_posix(), entry)


def download_diadata(raw_dir: Path, manifest: dict, force: bool) -> None:
    for remote in DIADATA:
        facts, _ = fetch(remote, raw_dir, force)
        record(manifest, remote.path, remote_entry(remote, facts))


def download_azt1d(raw_dir: Path, manifest: dict, force: bool) -> None:
    facts, _ = fetch(AZT1D, raw_dir, force)
    record(manifest, AZT1D.path, remote_entry(AZT1D, facts))


def record_manual(raw_dir: Path, manifest: dict) -> None:
    """Print instructions for manual datasets and hash any files already placed."""
    print("\nManual downloads (sign-in, licence click-through or data use agreement):")
    for dataset, folder, url, licence in MANUAL:
        files = sorted(p for p in (raw_dir / folder).rglob("*") if p.is_file())
        status = f"{len(files)} file(s) found" if files else "not present"
        print(f"  {dataset:<11} {url}\n  {'':<11} -> data/raw/{folder}/  [{licence}; {status}]")
        for path in files:
            entry = {
                "dataset": dataset,
                "url": url,
                "ref": "manual download",
                "licence": licence,
                "retrieved_at": now(),
                **file_facts(path),
            }
            record(manifest, path.relative_to(raw_dir).as_posix(), entry)
    print("  Re-run this script after adding files to record them in the manifest.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--diadata", action="store_true", help="also download DiaData (5-min archive, 2.3 GB)"
    )
    parser.add_argument(
        "--azt1d", action="store_true", help="also download AZT1D (Mendeley archive, 776 MB)"
    )
    parser.add_argument(
        "--force", action="store_true", help="download again even if files match their pins"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=REPO_ROOT / "data", help="data root (default: ./data)"
    )
    args = parser.parse_args(argv)

    raw_dir = args.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "MANIFEST.json"
    manifest = load_manifest(manifest_path)
    try:
        download_glucobench(raw_dir, manifest, args.force)
        if args.diadata:
            download_diadata(raw_dir, manifest, args.force)
        if args.azt1d:
            download_azt1d(raw_dir, manifest, args.force)
        record_manual(raw_dir, manifest)
    except DownloadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        manifest["generated_by"] = "scripts/download_data.py"
        manifest["updated_at"] = now()
        manifest["files"] = dict(sorted(manifest["files"].items()))
        text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        manifest_path.write_text(text, encoding="utf-8")
    print(f"\nmanifest  {manifest_path} ({len(manifest['files'])} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
