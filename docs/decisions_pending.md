# Decisions pending the project lead

Choices made during the Phase 2 fixes of [`development/REVIEW.md`](development/REVIEW.md) while the project lead was away (2026-10-18). Each choice was the one most consistent with `CLAUDE.md`. Any of them can be reversed.

`docs/model_card.md`, named in the instruction as a second reference, does not exist in this repository. `CLAUDE.md` and the specs in `docs/` were used instead.

Scientific decisions are not made here. They are listed as proposals P1–P9 in [`DECISIONS.md`](DECISIONS.md) and wait for the project lead.

| # | Question | Chosen | Why |
|---|---|---|---|
| 1 | The treatment rule (`HypoTreatment`) should be configurable (rule 2). Exposing it through `SimConfig` changes the cohort cache key (`SimConfig.key()` hashes every field). Do that, or leave it? | Left as a dataclass with defaults; not exposed through `SimConfig`. | A new cache key would orphan the cached cohort that `make reproduce` relies on. The plan said to stop if the hash would change. |
| 2 | `MIN_L2_EVENTS`, `TAIL_FRACTIONS` and the retro flag-rule constants are hard-coded. Plumb them too? | Left as named, marked module constants. | Plumbing them needs signature changes through the parallel fold code (more risk than value). The flag rule must not change (review instruction). |
| 3 | Where the Weinstock 2016 and Kovatchev 2009 DOIs were only in `paper.bib`, should `CITATIONS.md` gain them and keep status "verify"? | Added the DOI links. The status stays "verify", annotated "DOI record checked 2026-10-18". | The bibliographic record was checked, but the content was not opened, which is what the status describes. |
| 4 | `paper.bib` cites the AZT1D data record (`AZT1Ddata`), which had no key in `CITATIONS.md`. Add a key? | Added "AZT1D data 2025" to `CITATIONS.md` and `references.bib`. | Rule 1: every source used is listed. |
| 5 | Should bib entries without a DOI (patents, web pages, arXiv-only benchmarks, CFR, CDC) be filled from other registries? | Left as placeholders, each noted "no DOI recorded; verify before citing". | The approved scope was DOI-registry records only. No field is typed from memory (rule 1). |
