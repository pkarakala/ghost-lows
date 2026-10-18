# Citations

Every claim in this repository's docs, code comments and results cites a key from this file. Add new sources here first (and to `references.bib`), then cite them.

In code, write `# SOURCE: <key>`. Separate several keys with `;`; a key may be followed by a locator, as in `# SOURCE: Baysal 2014 (Table 1)`. `tests/test_repo_rules.py` fails if a key is not in this file.

**Status column**
- **opened**: abstract or full text was opened during the 2026-10-18 review; link checked then.
- **ref-only**: seen in reference lists or summaries only; not opened.
- **verify**: added from general knowledge; details and DOI must be checked before use in a paper.

Literature preparation for the paper is a separate, later step. This list exists so that the code and docs never make an uncited claim.

**Note:** the Reference column gives first author, a *descriptive* title and venue. Titles are not exact. Before a source goes into a paper, fill its exact bibliographic record from the DOI (for example with `doi2bib`) into `references.bib`.

## Compression artifacts (PISA): mechanism, size, frequency

| Key | Reference | Link | Status | Used for |
|---|---|---|---|---|
| Mensh 2013 | Mensh BD, et al. Susceptibility of interstitial CGM to compression during sleep. *J Diabetes Sci Technol* 2013 | [doi](https://doi.org/10.1177/193229681300700408) | opened | Mechanism; filmed sleep study |
| Helton 2011 | Helton KL, et al. Biomechanics of the sensor-tissue interface. *J Diabetes Sci Technol* 2011 | [doi](https://doi.org/10.1177/193229681100500318) | opened | Pressure and micromotion review |
| Facchinetti 2016 | Facchinetti A, et al. Modeling transient disconnections and compression artifacts of CGM sensors. *Diabetes Technol Ther* 2016 | [doi](https://doi.org/10.1089/dia.2015.0250) | opened (abstract) | **PISA model**: median 45 min, 24 mg/dL; first-order shape |
| Baysal 2014 | Baysal N, et al. A novel method to detect pressure-induced sensor attenuations (PISA) in an artificial pancreas. *J Diabetes Sci Technol* 2014 | [doi](https://doi.org/10.1177/1932296814553267) | opened | Rule-based real-time detector; rate thresholds; AID suspensions |
| Lobo 2026 | Lobo B. (UVA) Real-time detection of PISA onset. *J Diabetes Sci Technol*, online Aug 2026 | [doi](https://doi.org/10.1177/19322968261469536) | opened (abstract only) | Frequency (1 per 73 h); strongest recent baseline |

## Detectors and fault detection

| Key | Reference | Link | Status | Used for |
|---|---|---|---|---|
| Navarathna 2023 | Navarathna P, et al. ML detection of PISAs. *Ind Eng Chem Res* 2023 | [doi](https://doi.org/10.1021/acs.iecr.2c03259) | opened | Gradient-boosting baseline |
| Idi 2023 | Idi E, et al. Matched-filter PISA detection. *IEEE BSN* 2023 | [doi](https://doi.org/10.1109/BSN58485.2023.10331579) | opened | Matched-filter baseline |
| Idi 2024 | Idi E, et al. Unsupervised PISA detection (isolation forest). *IEEE J Biomed Health Inform*, online 2024 (issue 2025) | [doi](https://doi.org/10.1109/JBHI.2024.3465893) | opened | Isolation-forest baseline; uses Facchinetti model; 36-adult dual-G6 set |
| Manzoni 2025 | Manzoni E, et al. Bayesian PISA detection. *IEEE Trans Biomed Eng* 2025 | [doi](https://doi.org/10.1109/TBME.2025.3536805) | opened | Bayesian CGM-only detector; FP/day metric precedent |
| Turksoy 2017 | Turksoy K, et al. Sensor fault detection with insulin/meal information. *IEEE Trans Biomed Eng* 2017 | [doi](https://doi.org/10.1109/TBME.2016.2535412) | opened | Model-based fault detection with context |
| Facchinetti 2013 | Facchinetti A, et al. Online sensor and pump failure detection. *IEEE Trans Biomed Eng* 2013 | — | ref-only | Model-based fault detection precedent |
| Mahmoudi 2017 | Mahmoudi Z, et al. Sensor fault detection. *Biomed Signal Process Control* 2017 | — | ref-only | Kalman/HMM precedent |
| Del Favero 2014 | Del Favero S, et al. *IFAC* 2014 | — | ref-only | Fault detection precedent |
| Baysal ACC 2013 | Baysal N, et al. *American Control Conference* 2013 | — | ref-only | Early PISA detection |
| Sanchez 2025 | Sanchez et al. Fault-tolerant glucose prediction with insulin and carbs. *Algorithms* 2025 | [doi](https://doi.org/10.3390/a18110688) | opened | Noise/dropout faults with context; OhioT1DM |

## Benchmarks, testbeds and datasets

| Key | Reference | Link | Status | Used for |
|---|---|---|---|---|
| Zhou 2021 | Zhou et al. Fault-injection testbed for AID | [arXiv 2104.02545](https://arxiv.org/abs/2104.02545) | opened | Nearest testbed (controller faults, no PISA) |
| APS_TestBed 2022 | UVA-DSA APS_TestBed | [arXiv 2208.06479](https://arxiv.org/abs/2208.06479) | opened | Nearest testbed (generic faults) |
| GlucoBench 2024 | Sergazinov R, et al. GlucoBench. *ICLR* 2024 | [arXiv 2410.05780](https://arxiv.org/abs/2410.05780); [code](https://github.com/IrinaStatsLab/GlucoBench) | opened | Forecasting benchmark (no faults); data source |
| GlucoFM-Bench 2026 | GlucoFM-Bench | [arXiv 2606.06881](https://arxiv.org/abs/2606.06881) | opened | Forecasting benchmark (no faults) |
| MetaboNet 2026 | MetaboNet consolidated T1D dataset | [arXiv 2601.11505](https://arxiv.org/abs/2601.11505) | opened | Dataset |
| MetaboNet-Bench 2026 | MetaboNet-Bench | [arXiv 2606.18640](https://arxiv.org/abs/2606.18640) | opened | Forecasting benchmark (no faults) |
| Glucose-ML 2025 | Glucose-ML dataset collection | [arXiv 2507.14077](https://arxiv.org/abs/2507.14077) | opened | Dataset catalogue |
| DiaData 2026 | Cinar B, Maleshkova M. DiaData v3. Zenodo 2026 | [Zenodo](https://zenodo.org/records/17285631) | opened | Dataset |
| AZT1D 2025 | AZT1D: a real-world dataset for T1D | [arXiv 2506.14789](https://arxiv.org/abs/2506.14789); [data](https://data.mendeley.com/datasets/gk9m674wcx/1) | opened | Real-data context ablation |
| OhioT1DM | Marling C, Bunescu R. OhioT1DM dataset | [site](https://webpages.charlotte.edu/rbunescu/data/ohiot1dm/OhioT1DM-dataset.html) | opened | Dataset (DUA) |
| Weinstock 2016 | Weinstock RS, et al. Severe hypoglycemia in older adults with T1D (Jaeb) | [Jaeb](https://public.jaeb.org/dataset/537) | verify | Dataset via GlucoBench |
| Dubosson 2018 | Dubosson F, et al. D1NAMO dataset | [Zenodo](https://doi.org/10.5281/zenodo.1421615) | verify | Dataset via GlucoBench |
| Hall 2018 | Hall H, et al. Glucotypes. *PLoS Biol* 2018 | [journal](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.2005143) | verify | Dataset via GlucoBench |
| Colás 2019 | Colás A, et al. *PLoS One* 2019 | [journal](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0225817) | verify | Dataset via GlucoBench |
| Broll 2021 | Broll S, et al. iglu R package | [code](https://github.com/irinagain/iglu) | verify | Metrics cross-check; dataset |
| CGMacros | CGMacros dual-sensor dataset (PhysioNet) | — | verify | Two-sensor proxy labels |
| Tidepool | Tidepool Big Data Donation Project | [site](https://tidepool.org/bigdata) | opened | Possible future data |

## Simulator and sensor models

| Key | Reference | Link | Status | Used for |
|---|---|---|---|---|
| simglucose | Xie J. simglucose v0.2.11 (UVA/Padova 2008 in Python) | [code](https://github.com/jxx123/simglucose) | opened (source) | Simulator |
| Kovatchev 2009 | Kovatchev BP, et al. In silico preclinical trials (UVA/Padova simulator). *J Diabetes Sci Technol* 2009 | — | verify | Simulator model |
| Breton 2008 | Breton M, Kovatchev B. Analysis, modeling and simulation of CGM sensor accuracy. *J Diabetes Sci Technol* 2008 | — | verify | simglucose noise model |
| Basu 2013 | Basu A, et al. Time lag of glucose from intravascular to interstitial compartment. *Diabetes* 2013 | [doi](https://doi.org/10.2337/db13-1132) | opened | Blood-to-ISF lag |

## Clinical definitions, devices and regulation

| Key | Reference | Link | Status | Used for |
|---|---|---|---|---|
| Battelino 2019 | Battelino T, et al. International consensus on time in range. *Diabetes Care* 2019 | — | verify | TIR/TBR/TAR targets; dashboard metrics |
| Battelino 2023 | Battelino T, et al. CGM consensus. *Lancet Diabetes Endocrinol* 2023 | [doi](https://doi.org/10.1016/S2213-8587(22)00319-9) | opened | Event definition (≥15 min) |
| IHSG 2017 | International Hypoglycaemia Study Group. *Diabetes Care* 2017 | — | verify | Hypoglycaemia levels |
| Garg 2022 | Garg SK, et al. Dexcom G7 accuracy. *Diabetes Technol Ther* 2022 | [doi](https://doi.org/10.1089/dia.2022.0011) | opened | G7 MARD; alerts |
| 21 CFR 862.1355 | iCGM special controls | [eCFR](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-862/subpart-B/section-862.1355) | verify | Alert-rate definitions |
| FDA K212132 | FreeStyle Libre 3 decision summary | [pdf](https://www.accessdata.fda.gov/cdrh_docs/reviews/K212132.pdf) | opened | Alert-rate definitions |
| Shivers 2013 | Shivers JP, et al. Turn it off! Alarm fatigue. *J Diabetes Sci Technol* 2013 | [doi](https://doi.org/10.1177/193229681300700324) | opened | Alarm fatigue |
| Eichenlaub 2024 | Eichenlaub M, et al. *J Diabetes Sci Technol* 2024 | [doi](https://doi.org/10.1177/19322968241267765) | opened | Artifacts inflate counted hypoglycaemia |
| Kaylor 2022 | Kaylor and Morrow. Caregiver sleep survey, 2022 | — | ref-only | Caregiver sleep burden |
| Altnickel 2026 | Altnickel. CamAPS FX with Libre 3 case report. *Cureus* 2026 | [doi](https://doi.org/10.7759/cureus.106803) | opened | AID suspensions from compression |
| Trinity Biotech 2026 | Trinity Biotech. CGM+ nocturnal compression lows press release, Jul 2026 | [pdf](https://trinitybiotech.com/wp-content/uploads/2026/07/Trinity-Biotech-CGM-Clinical-Trial-Data-Nocturnal-Compression-Lows.pdf) | opened | Commercial multi-sensor approach |

## Patents (summaries only, not legal opinion)

| Key | Holder / topic | Link | Status |
|---|---|---|---|
| US 2024/0139415 | UVA (Kovatchev, Lobo), PISA-aware alarm disabling / insulin resumption, pending | [Google Patents](https://patents.google.com/patent/US20240139415A1/en) | opened (summary) |
| US 2024/0138770 | UVA, PISA detection with interstitial clearance model | [Justia](https://patents.justia.com/patent/20240138770) | opened (summary) |
| US 2026/0096748 | Padova inventors, unsupervised PISA detection | [Justia](https://patents.justia.com/patent/20260096748) | opened (summary) |
| US 10,546,659 | UVA in-silico test environment with sensor-error models | [Google Patents](https://patents.google.com/patent/US10546659B2/en) | opened (summary) |
| US 11,406,331 | Abbott, alarm gating with insulin/carb context | [Google Patents](https://patents.google.com/patent/US11406331B2/en) | opened (summary) |
| US 9,119,528 | Dexcom family, context-based alarm handling | [Google Patents](https://patents.google.com/patent/US9119528) | opened (summary) |
| US 10,231,659 | Dexcom, context-based fault classification incl. compression | [Google Patents](https://patents.google.com/patent/US10231659) | opened (summary) |

## Data access and export formats

| Key | Reference | Link | Status |
|---|---|---|---|
| UMich CGM exports | U. Michigan Depression Center KB: patient vs. provider CGM exports | [page](https://teamdynamix.umich.edu/TDClient/210/DepressionCenter/Questions/Details/100073) | opened |
| Dexcom API docs | Dexcom Developer API v3: endpoints; scopes and access | [endpoints](https://developer.dexcom.com/docs/dexcomv3/endpoint-overview), [access](https://developer.dexcom.com/docs/dexcom/scopes-access/) | opened |
