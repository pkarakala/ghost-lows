# Data

No data is committed to this repository. Everything goes under `data/` (gitignored). Each dataset keeps its own licence; cite it whenever it is used.

## 1. Datasets

| Dataset | Population / device | Size | Access and licence | Use here | Get it |
|---|---|---|---|---|---|
| **Weinstock 2016** (via GlucoBench) | T1D older adults, Dexcom G4 | 200 people, ~10 days each | CC BY-SA 4.0 (per GlucoBench) | Real overnight traces; semi-synthetic PISA injection; alarm counts on real data | `raw_data.zip` in [GlucoBench](https://github.com/IrinaStatsLab/GlucoBench) → `weinstock.csv`; original at [Jaeb](https://public.jaeb.org/dataset/537) |
| **Dubosson 2018 / D1NAMO** (via GlucoBench) | T1D, with insulin, food, heart rate | 9 people | CC BY-SA 4.0 | Small real check of context features | GlucoBench `dubosson.csv` |
| **Hall 2018**, **Colás 2019**, **Broll 2021** (via GlucoBench) | Mixed / non-T1D | 57 / 208 / 5 | CC BY 4.0 / CC BY 4.0 / GPL-2 | Parser and metrics tests; few lows | GlucoBench `hall.csv`, `colas.csv`, `iglu.csv` |
| **DiaData** | T1D, 13 merged studies (REPLACE-BG, DCLP3, PEDAP, …) | 1,720 people; 51 with heart rate | CC BY-NC 4.0 | Large real overnight corpus | [Zenodo 17285631](https://zenodo.org/records/17285631) |
| **AZT1D** | T1D, Dexcom G6 + Control-IQ, insulin, carbs, pump sleep-mode flag | see paper | CC BY 4.0 | **Real-data context ablation** | [arXiv 2506.14789](https://arxiv.org/abs/2506.14789); data on [Mendeley](https://data.mendeley.com/datasets/gk9m674wcx/1) |
| **CGMacros** | Dexcom + Libre worn together; T2D, prediabetes, healthy | 45 people | Open (check licence on PhysioNet) | Two-sensor disagreement as a proxy compression label (few lows) | PhysioNet |
| **OhioT1DM** | T1D, Medtronic, fingersticks, sleep, HR | 12 people | Data use agreement | Optional: fingerstick reference, sleep | [OhioT1DM](https://webpages.charlotte.edu/rbunescu/data/ohiot1dm/OhioT1DM-dataset.html) |
| **MetaboNet** | T1D, 13 consolidated studies | see paper | Public release + DUA parts | Optional larger real set | [arXiv 2601.11505](https://arxiv.org/abs/2601.11505) |
| **simglucose** | 30 virtual T1D patients | unlimited | MIT | Main benchmark | `pip install simglucose` |

GlucoBench raw-file notes (checked 2026-10-18 at commit `661d840`): columns are `id, time, gl` plus covariates; `colas.csv` has a leading unnamed index column; `weinstock.csv` dates are shifted to 1900-01-01 for de-identification (times of day are usable, calendar dates are not).

A copy of the GlucoBench CSVs and the simglucose and iglu sources is in the project's shared folder (`data/raw/`), but the download script must not depend on it.

## 2. Download script

`scripts/download_data.py` must:

1. Download GlucoBench `raw_data.zip` from GitHub and unzip to `data/raw/glucobench/`.
2. Download DiaData from Zenodo (5-minute archive first; it is ~2.3 GB, so make it opt-in with a flag).
3. Print manual instructions for AZT1D (Mendeley), CGMacros (PhysioNet) and OhioT1DM (DUA) rather than scraping them.
4. Write `data/raw/MANIFEST.json` with URL, date, size and SHA-256 of every file.

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
