# Privacy and safety rules for the upload tool

The rules the upload report must follow, for anyone changing `app/` or `ghostlows.retro` and for clinical reviewers. Each rule is a requirement. Terms: Pyodide and stlite run Python inside the browser; a CDN is a public file host; an IRB is an ethics review board.

## Safety

1. **Retrospective only.** The tool analyses past data. It never runs live, never connects to a device's alarms, and never suggests silencing an alarm.
2. **Wording.** Flagged events are labelled **"possible compression artifact"**. The tool must never say a low "was not real", "was fake" or "can be ignored". Every page with flags shows: *"If you are unsure whether a low is real, check with a fingerstick and treat according to your care plan."* **[clinical review CR12](CLINICAL_REVIEW.md)**
3. **A flag never lowers a number.** Time below range and every other metric count every reading, flagged or not. Possible compression artifacts are shown as labelled annotations on the charts and as a count, next to the flags' measured performance on simulated data in plain words (amendment [A12](reference/DECISIONS.md#amendments)). **[clinical review CR12](CLINICAL_REVIEW.md)**
4. **Disclaimer** on every page: research software, not a medical device, not for treatment decisions.
5. **Method transparency.** Each flag shows why it was raised (drop rate, depth, duration, time of night) and names the published method used.

## Privacy

1. **No server.** The uploaded file is read and analysed in the user's browser (Pyodide / stlite). Nothing is sent anywhere. No accounts.
2. **No trackers.** No analytics, no third-party scripts beyond the pinned Pyodide/stlite runtime from a public CDN. Say so on the page.
3. **No storage.** Nothing is written to browser storage except optional display preferences.
4. **Downloads are local.** Any report or CSV the user downloads is generated in the browser.
5. **No data collection for research** until an IRB has approved a protocol with informed consent and de-identification.

## How the report meets them

- **Flag rule.** A flag needs two published methods to agree and must start at night (23:00–07:00).
- **Flags are often wrong.** On simulated data, flags caught 35% of injected compression artifacts. They also fell on other dips, a median of 4 per 14 days. In 37% of runs, a flag overlapped a real low.
- **So no number leaves out flagged readings.** Flags are annotations and a count, shown with that performance.
- **Network.** The page contacts only its pinned runtime and package hosts. A browser test fails if the uploaded file is sent anywhere.

Full detail, the sample data and the regulatory context: [UPLOAD_REPORT.md](reference/UPLOAD_REPORT.md).
