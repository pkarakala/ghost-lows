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

## Regulatory context (not legal advice)

- HIPAA covers healthcare providers, plans and their business associates; a public research tool generally is not one, but the FTC Health Breach Notification Rule (expanded in 2024 to health apps) and state laws such as Washington's My Health My Data Act can apply to apps that collect health data. Browser-only processing avoids collecting it.
- Software that analyses CGM data to drive treatment decisions can be a medical device under FDA rules. Keeping the tool retrospective, informational and clearly disclaimed keeps it out of that role. Ask a faculty adviser before any change in scope.
- Low-alarm gating with insulin and carb context is patented for products [US 11,406,331; US 9,119,528; US 10,231,659; US 2024/0139415]. The tool does not gate alarms. Consult the university tech-transfer office before any commercial or clinical use.
