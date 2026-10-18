# Privacy and safety rules for the upload tool

These are requirements, not suggestions.

## Safety

1. **Retrospective only.** The tool analyses past data. It never runs live, never connects to a device's alarms, and never suggests silencing an alarm.
2. **Wording.** Flagged events are labelled **"possible compression artifact"**. The tool must never say a low "was not real", "was fake" or "can be ignored". Every page with flags shows: *"If you are unsure whether a low is real, check with a fingerstick and treat according to your care plan."* **[clinical review]**
3. **Show both numbers.** Time below range is shown with and without possible artifacts, side by side, never only the lower one.
4. **Disclaimer** on every page: research software, not a medical device, not for treatment decisions.
5. **Method transparency.** Each flag shows why it was raised (drop rate, depth, duration, time of night) and names the published method used.

## Privacy

1. **No server.** The uploaded file is read and analysed in the user's browser (Pyodide / stlite). Nothing is sent anywhere. No accounts.
2. **No trackers.** No analytics, no third-party scripts beyond the pinned Pyodide/stlite runtime from a public CDN. Say so on the page.
3. **No storage.** Nothing is written to browser storage except optional display preferences.
4. **Downloads are local.** Any report or CSV the user downloads is generated in the browser.
5. **No data collection for research** until an IRB has approved a protocol with informed consent and de-identification.

## As implemented (phase 8)

- **Flag rule.** A detection becomes a "possible compression artifact" flag only if two published CGM-only methods agree (the Baysal 2014 rules and a matched filter for the Facchinetti 2016 PISA shape after Idi 2023) and it starts at night (23:00–07:00), when compression is most common. On the synthetic test export, either method alone also fired on a genuine-looking daytime fall to 54 mg/dL, and a flag must not hide a real low from time below range. Detections that are not flags are listed under "Detections that are not flags" and change no number. **[clinical review CR12]**
- **How the flags do on simulated data.** `scripts/make_sample_export.py --survey <cohort>` runs the app's loader and flags on all 150 default-mix runs of the benchmark cohort, with faults as in the PISA sweep at the 25% level (other faults moderate, fault seed 0). Of 492 injected PISAs, 35% are flagged. Flags also fall where no PISA was injected: a median of 4 (mean 3.6) per 14-day run, on dips from simulated sensor noise or on real falls in glucose. In 37% of runs at least one flag overlaps a real low (plasma glucose below 70 mg/dL for 15 min or more), so the "without possible compression artifacts" column can leave out real low readings. The simulated sensor noise is smoother than real noise, and the injected PISAs share the matched filter's template (RESEARCH.md §6), so these numbers do not transfer to real exports, which have no labels. They do show that "conservative" means "needs two methods and a night-time start", not "rarely wrong". **[clinical review CR12]**
- **Sample data.** *Try it with sample data* shows the report for `app/sample_clarity_export.csv`, a synthetic 14-day export in the Clarity format written by `scripts/make_sample_export.py`. It holds one virtual adult of the benchmark cohort with the benchmark's faults. Its header rows and a banner ("You are viewing synthetic sample data, not a real person's data.") say it is synthetic. The run is the first in the benchmark's order with two flagged PISA nights (one a ghost low) and an unflagged real low at night, with no condition on other flags. It is one of 15 of 150 runs that qualify, and its 4 flags elsewhere are the cohort median. Because the truth is known, the app shows, for the sample only, which flags fall on an injected artifact and the true glucose on each flagged night (`app/sample_answer_key.json`). *Download the sample file* is generated in the page from the bundled file.
- **Both numbers.** Time below 70 and below 54 mg/dL are shown with all readings and without readings inside flags, side by side.
- **Network.** The page (`app/`) contacts only cdn.jsdelivr.net (the pinned stlite 1.9.2 runtime and Pyodide), pypi.org and files.pythonhosted.org (Python packages). The browser test `tests/test_app_browser.py` uploads the synthetic export and fails if any request URL or body contains the file's contents, or if any other host is contacted. Streamlit's usage statistics are turned off. The sample download is served from inside the page under stlite's reserved host `stlite.invalid`; the browser's own request for it never resolves, and the test checks that it fails and carries no body.
- **Storage.** The app writes nothing to browser storage.

## Regulatory context (not legal advice)

- HIPAA covers healthcare providers, plans and their business associates; a public research tool generally is not one, but the FTC Health Breach Notification Rule (expanded in 2024 to health apps) and state laws such as Washington's My Health My Data Act can apply to apps that collect health data. Browser-only processing avoids collecting it.
- Software that analyses CGM data to drive treatment decisions can be a medical device under FDA rules. Keeping the tool retrospective, informational and clearly disclaimed keeps it out of that role. Ask a faculty adviser before any change in scope.
- Low-alarm gating with insulin and carb context is patented for products [US 11,406,331; US 9,119,528; US 10,231,659; US 2024/0139415]. The tool does not gate alarms. Consult the university tech-transfer office before any commercial or clinical use.
