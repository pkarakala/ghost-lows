# Data

No data is committed to this repository. Everything goes under `data/` (gitignored). Each dataset keeps its own licence; cite it whenever it is used.

## 1. Datasets

| Dataset | Population / device | Size | Access and licence | Use here | Get it |
|---|---|---|---|---|---|
| **Weinstock 2016** (via GlucoBench) | T1D older adults, Dexcom G4; recruited for a severe-hypoglycaemia study, so lows are over-represented (7.5% of readings <70, 3.8% <54) | 200 people; records span a median of 13.9 days (IQR 13.6–15.1) | CC BY-SA 4.0 (per GlucoBench) | Real overnight traces; semi-synthetic PISA injection; alarm counts on real data | `raw_data.zip` in [GlucoBench](https://github.com/IrinaStatsLab/GlucoBench) → `weinstock.csv`; original at [Jaeb](https://public.jaeb.org/dataset/537) |
| **Dubosson 2018 / D1NAMO** (via GlucoBench) | T1D, with fast/slow insulin, food, heart rate. Food is recorded as **calories, not carbohydrate grams**, so COB needs an assumption | 9 people, ~3.7 days each | CC BY-SA 4.0 | Small real check of context features | GlucoBench `dubosson.csv` |
| **Hall 2018**, **Colás 2019**, **Broll 2021** (via GlucoBench) | Mixed / non-T1D | 57 / 208 / 5 | CC BY 4.0 / CC BY 4.0 / GPL-2 | Parser and metrics tests; few lows | GlucoBench `hall.csv`, `colas.csv`, `iglu.csv` |
| **DiaData** | T1D, 13 merged studies (REPLACE-BG, DCLP3, PEDAP, …). **Includes Weinstock 2016 (Jaeb 537) and D1NAMO**: deduplicate before combining with the GlucoBench sets | 1,720 people; 51 with heart rate | CC BY-NC 4.0 | Large real overnight corpus. Use the **raw** release: the preprocessed one interpolates gaps up to 120 min and removes IQR outliers, which erases dropouts and can remove real lows | [Zenodo 17285631](https://zenodo.org/records/17285631) (v3) |
| **AZT1D** | T1D, Dexcom G6 + Control-IQ, insulin, carbs, pump sleep-mode flag | see paper | CC BY 4.0 | **Real-data context ablation** | [arXiv 2506.14789](https://arxiv.org/abs/2506.14789); data on [Mendeley](https://data.mendeley.com/datasets/gk9m674wcx/1) |
| **CGMacros** | Dexcom + Libre worn together; T2D, prediabetes, healthy | 45 people | CC BY-NC-SA 4.0 (PhysioNet page, v1.0.0) | Two-sensor disagreement as a proxy compression label (few lows) | [PhysioNet](https://physionet.org/content/cgmacros/1.0.0/) |
| **OhioT1DM** | T1D, Medtronic, fingersticks, sleep, HR | 12 people | Data use agreement | Optional: fingerstick reference, sleep | [OhioT1DM](https://webpages.charlotte.edu/rbunescu/data/ohiot1dm/OhioT1DM-dataset.html) |
| **MetaboNet** | T1D, 13 consolidated studies | see paper | Public release + DUA parts | Optional larger real set | [arXiv 2601.11505](https://arxiv.org/abs/2601.11505) |
| **simglucose** | 30 virtual T1D patients | unlimited | MIT | Main benchmark | `pip install simglucose` |

GlucoBench raw-file notes (checked 2026-10-18 at commit `661d840`): columns are `id, time, gl` plus covariates; `colas.csv` has a leading unnamed index column; `weinstock.csv` dates are shifted to around 1900-01-01 for de-identification (range 1899-12-27 to 1900-03-22; times of day are usable, calendar dates are not). `weinstock.csv` glucose runs from 39 to 401 mg/dL, with pile-ups at both ends (11,924 readings of 39 vs 605 of 40; 11,978 of 401 vs 187 of 400): 39 and 401 are sentinels for readings below and above the sensor's 40–400 mg/dL range. They are censored values; the loader must flag them (`below_range` / `above_range`) rather than treat them as measurements. The GlucoBench repository itself has no licence file; the licences above are the per-dataset ones its README states, and its Colás row says "Creative Commons 4.0" while linking to CC BY 3.0 US.

A copy of the GlucoBench CSVs and the simglucose and iglu sources is in the project's shared folder (`data/raw/`), but the download script must not depend on it.

## 2. Download script

`scripts/download_data.py` must:

1. Download GlucoBench `raw_data.zip` from GitHub and unzip to `data/raw/glucobench/`.
2. Download DiaData from Zenodo (5-minute archive first; it is ~2.3 GB, so make it opt-in with a flag).
3. Print manual instructions for AZT1D (Mendeley), CGMacros (PhysioNet) and OhioT1DM (DUA) rather than scraping them.
4. Write `data/raw/MANIFEST.json` with URL, date, size and SHA-256 of every file.

As implemented (standard library only; `uv run python scripts/download_data.py [--diadata] [--force]`):

- **Pinned sources.** GlucoBench is fetched from commit `661d840a98b316df51faa13a7100430afcbbb5b7` and must match SHA-256 `aecc5a50bd6b09799b90eddf127c8270e7292fee6840ac822f0e8092569fff61` (5,639,441 bytes). DiaData is record 17285631 (v3; concept DOI 10.5281/zenodo.16874128); `5_min_sampling.zip` (2,341,562,516 bytes), `README.md` and `Demographics.csv` are checked against Zenodo's published MD5s. A mismatch stops the script with an error and leaves nothing at the destination.
- **Layout.** The GlucoBench archive keeps its CSVs under `raw_data/` and includes a stray `.DS_Store`; the script writes `data/raw/glucobench/{weinstock,dubosson,hall,colas,iglu}.csv` (about 176 MB) next to the archive, skipping macOS metadata and refusing member paths that escape the folder. DiaData is **not** extracted (the archive is large); loaders read it from the zip.
- **Manual datasets** go in `data/raw/{azt1d,cgmacros,ohiot1dm}/`; re-running the script hashes whatever is there into the manifest.
- **Manifest.** One entry per archive and per extracted or manually placed file: dataset key (from `CITATIONS.md`), URL, pinned ref, retrieval time (UTC), size, SHA-256 (and MD5), licence as stated by the source, and for extracted files the archive member. Re-runs keep the first retrieval time of unchanged files. The manifest is gitignored with the data; reproducibility comes from the pins in the committed script.

## 3. Common schema

All loaders return one long table:

| Column | Type | Notes |
|---|---|---|
| `patient_id` | str | prefixed by dataset, e.g. `weinstock:199` |
| `time` | datetime64 (naive local time) | |
| `glucose` | float, mg/dL | NaN for gaps; `Low`/`High` strings become the device limits with a flag |
| `glucose_flag` | category | `ok`, `below_range`, `above_range` |
| `source` | str | dataset or device name |
| `insulin_bolus`, `insulin_basal`, `carbs` | float, optional | NaN when not available |
| `truth_glucose`, `fault_type`, `fault_id` | simulation only | |

## 4. User exports (upload tool)

**Dexcom Clarity CSV.** 14 columns: Index, Timestamp (YYYY-MM-DDThh:mm:ss), Event Type, Event Subtype, Patient Info, Device Info, Source Device ID, Glucose Value (mg/dL), Insulin Value (u), Carb Value (grams), Duration (hh:mm:ss), Glucose Rate of Change (mg/dL/min), Transmitter Time (Long Integer), Transmitter ID. Metadata rows sit above the readings; alert rows are mixed in; 5-minute readings; up to 90 days per export [UMich CGM exports]. Keep only `Event Type == "EGV"` for glucose. Values below/above range appear as `Low`/`High` text (confirm on a real G7 file). Timestamps have no timezone.

**LibreView CSV.** Two header rows, then 19 columns including Device, Serial Number, Device Timestamp, Record Type, Historic Glucose mg/dL, Scan Glucose mg/dL, Strip Glucose mg/dL, insulin and carbs. Timestamps like `4/12/2023 14:30` [UMich CGM exports]. Record Type distinguishes historic, scan and strip rows.

**Dexcom API v3** (later, optional): OAuth 2.0; endpoints egvs, events, alerts, calibrations, devices, dataRange; data delayed 1 h (US) / 3 h (elsewhere); 30-day request window; sandbox user `SandboxUser7` for G7; Limited Access allows 5 users [Dexcom API docs].

**Test fixtures:** create small synthetic Clarity and LibreView files by hand in `tests/fixtures/` (never real patient data). Replace with a de-identified real export when one is available, with the owner's consent.
