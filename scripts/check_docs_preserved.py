"""Check that a docs restructure lost nothing: numbers, estimates, citation keys, CR items,
RESEARCH.md §6 limitations and the safety sentences.

Compares every Markdown file (and CITATION.cff) at a git ref with the working tree. An item is
LOST when no copy of it is left anywhere; that fails the check. FEWER COPIES lists items that
survive with fewer copies than before (duplicates removed on purpose), for a person to review.
CHANGED ON PURPOSE lists LOST items that match INTENDED, a reviewed change; they do not fail it.

    uv run python scripts/check_docs_preserved.py --before v0.2.0
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SAFETY = [
    "possible compression artifact",
    "If you are unsure whether a low is real, check with a fingerstick and treat according to "
    "your care plan.",
    "Not a medical device. Not for treatment decisions.",
    "If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.",
]

# Reviewed changes: (start of the item, text only the old version has, why). An item that
# matches is reported as CHANGED ON PURPOSE instead of LOST.
INTENDED = [
    (
        "CR item - [ ] CR12.",
        "Sign-off by Cohen Ferrari is still open",
        "0075ea4: Cohen Ferrari is a literature fact-checker, not a clinician",
    ),
    ("number 0.3.0", "0.3.0", "v0.4.0: CITATION.cff's version moves from 0.3.0 to 0.4.0"),
]

NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
ESTIMATE = re.compile(r"-?\d+(?:\.\d+)?%? \(-?\d+(?:\.\d+)?%?(?:–| to )-?\d+(?:\.\d+)?%?\)")
BRACKET_CITE = re.compile(r"\[([A-Z][^\[\]]*?\d{4}[a-z]?)\]")
PANDOC_CITE = re.compile(r"@([A-Za-z][\w]*\d{4}\w*)")
CR_ITEM = re.compile(r"^- \[[ x]\] \*\*CR\d+\..*$", re.M)


def is_doc(path: str) -> bool:
    return path.endswith(".md") or path == "CITATION.cff"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout


def docs_at(ref: str) -> dict[str, str]:
    files = [p for p in git("ls-tree", "-r", "--name-only", ref).splitlines() if is_doc(p)]
    return {p: git("show", f"{ref}:{p}") for p in files}


def docs_now() -> dict[str, str]:
    files = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    return {p: (REPO / p).read_text() for p in files if is_doc(p) and (REPO / p).exists()}


def plain(text: str) -> str:
    """Drop link targets and emphasis, so adding a link or bold does not count as a change."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.replace("**", "").replace("`", "")


def citation_keys(docs: dict[str, str]) -> set[str]:
    keys = set()
    for line in docs.get("docs/CITATIONS.md", "").splitlines():
        if line.startswith("|"):
            first = line.strip("|").split("|")[0].strip()
            if first and first != "Key" and not set(first) <= set("-: "):
                keys.add(first)
    return keys


def limitations(docs: dict[str, str]) -> list[str]:
    for path, text in docs.items():
        if path.endswith("RESEARCH.md"):
            m = re.search(r"## 6\. Known limitations to state up front\n(.*?)\n## ", text, re.S)
            if m:
                return [line[2:] for line in m.group(1).splitlines() if line.startswith("- ")]
    return []


def inventory(docs: dict[str, str], keys: set[str], limits: list[str]) -> Counter:
    items: Counter = Counter()
    for text in docs.values():
        flat = plain(text)
        items.update(f"number {n}" for n in NUMBER.findall(flat))
        items.update(f"date {d}" for d in DATE.findall(flat))
        items.update(f"estimate {e}" for e in ESTIMATE.findall(flat))
        for group in BRACKET_CITE.findall(flat):
            cites = [c.strip() for c in group.split(";") if re.search(r"\d{4}", c)]
            items.update(f"citation [{c}]" for c in cites)
        items.update(f"citation @{c}" for c in PANDOC_CITE.findall(text))
        items.update(f"key {k}" for k in keys for _ in range(flat.count(k)))
        items.update(f"CR item {plain(line)}" for line in CR_ITEM.findall(text))
        for lim in map(plain, limits):
            items.update([f"limitation {lim}"] * flat.count(lim))
        items.update(f"safety {s}" for s in SAFETY for _ in range(flat.count(s)))
    return items


def intended(item: str) -> str | None:
    for start, old_text, why in INTENDED:
        if item.startswith(start) and old_text in item:
            return why
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", required=True, help="git ref of the docs before the change")
    args = parser.parse_args()

    before_docs, after_docs = docs_at(args.before), docs_now()
    keys, limits = citation_keys(before_docs), limitations(before_docs)
    before = inventory(before_docs, keys, limits)
    after = inventory(after_docs, keys, limits)

    gone = sorted(item for item in before if after[item] == 0)
    lost = [item for item in gone if not intended(item)]
    changed = [item for item in gone if intended(item)]
    fewer = sorted(
        (item, before[item], after[item]) for item in before if 0 < after[item] < before[item]
    )

    print(f"Compared {len(before_docs)} files at {args.before} with {len(after_docs)} now.")
    print(f"{len(before)} distinct items before, {len(after)} after.")
    print(f"\nLOST ({len(lost)}): no copy left anywhere")
    for item in lost:
        print(f"  {item}")
    if changed:
        print(f"\nCHANGED ON PURPOSE ({len(changed)}): see INTENDED")
        for item in changed:
            print(f"  {intended(item)}: {item[:100]}...")
    print(f"\nFEWER COPIES ({len(fewer)}): duplicates removed")
    for item, n_before, n_after in fewer:
        print(f"  {n_before} -> {n_after}  {item}")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
