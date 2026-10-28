# Release checklist

The steps no pull request can do, for the project lead. Version steps are in [ENGINEERING.md](../reference/ENGINEERING.md#package) (Releases).

## GitHub settings (once)

1. **About** (gear icon on the repository page):
   - Description: `Open benchmark for real-time CGM low-glucose alarms under sensor faults, including compression lows (PISA). Research software, not a medical device.`
   - Website: `https://pkarakala.github.io/ghost-lows/`
   - Topics: `continuous-glucose-monitoring`, `cgm`, `hypoglycemia`, `type-1-diabetes`, `diabetes-technology`, `low-glucose-alarms`, `false-alarms`, `compression-artifacts`, `pressure-induced-sensor-attenuation`, `sensor-faults`, `benchmark`, `simglucose`, `python`, `reproducible-research`.
2. **Social preview** (Settings > General > Social preview): upload `docs/figures/social_preview.png` (1280 x 640).

## Release v0.4.0

1. Merge the audit, figures, docs and metadata pull requests. Wait for CI on `main` to pass.
2. Set `__version__ = "0.4.0"` in `src/ghostlows/__init__.py`, and `version: 0.4.0` and `date-released` in `CITATION.cff`. Move the CHANGELOG's Unreleased entry under `## v0.4.0 (<date>)`, dropping any part whose pull request was not merged. Commit, push and wait for CI.
3. Tag: `git tag -a v0.4.0 -m "v0.4.0" && git push origin v0.4.0`. The Release workflow (`.github/workflows/release.yml`) then publishes the GitHub Release with the CHANGELOG entry as its notes. Without permission to push tags, run it by hand instead (Actions > Release > Run workflow, on `main`, version `0.4.0`); it creates the tag at the head of `main`.

## Zenodo (after the release is archived)

1. Open the new version from the concept DOI, `10.5281/zenodo.23573707`. Check:
   - version 0.4.0, title, licence MIT, language English;
   - both creators with ORCID and affiliation;
   - the description and keywords match `.zenodo.json`;
   - the five related works resolve (upload report, specifications, results, simglucose, Facchinetti 2016);
   - the concept DOI now resolves to 0.4.0, and "Cite as" names both authors.
2. Communities: on the record, choose *Submit to community*, and search for diabetes, digital health, biomedical engineering and research software. Request only communities whose scope covers open research software; a curator must accept each. The names could not be checked from here.
3. If a field is wrong, edit the record's metadata on Zenodo (files cannot change), and fix `.zenodo.json` before the next release.
