"""Ghost Lows upload report (runs in the browser with stlite; docs/PRIVACY_AND_SAFETY.md).

Reads a Dexcom Clarity or LibreView CSV inside the browser tab, shows the consensus CGM metrics
[Battelino 2019], the ambulatory glucose profile, daily traces and nights with retrospective
"possible compression artifact" flags from published CGM-only methods, each with its reasons.

"Try it with sample data" shows the report for a synthetic export (sample_clarity_export.csv,
written by scripts/make_sample_export.py) under a banner, with what really happened in it from
the simulation (sample_answer_key.json).
"""

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from ghostlows import io as gio
from ghostlows import metrics, retro

DISCLAIMER = "Research software, not a medical device. Not for treatment decisions."
FINGERSTICK = (
    "If you are unsure whether a low is real, check with a fingerstick and treat according to "
    "your care plan."
)
PRIVACY = (
    "Your file is read inside this browser tab and never leaves it: there is no server, no account "
    "and no analytics. Nothing is stored after you close the tab."
)
SAMPLE = Path(__file__).with_name("sample_clarity_export.csv")
ANSWER_KEY = Path(__file__).with_name("sample_answer_key.json")
SAMPLE_BANNER = "You are viewing synthetic sample data, not a real person's data."


def night_of(t: pd.Timestamp) -> pd.Timestamp:
    """20:00 on the evening that starts the night containing `t`."""
    start = t.normalize() + pd.Timedelta(hours=20)
    return start - pd.Timedelta(days=1) if t.hour < 12 else start


def night_label(t: pd.Timestamp) -> str:
    start = night_of(t)
    return f"the night of {start:%a %d} to {start + pd.Timedelta(days=1):%a %d %b}"


def in_night(frame: pd.DataFrame, night_start: pd.Timestamp) -> pd.DataFrame:
    """Rows from 20:00 on `night_start` to 08:00 the next morning."""
    end = night_start + pd.Timedelta(hours=12)
    return frame[(frame["time"] >= night_start) & (frame["time"] <= end)]


def overlapping(start, end, spans: pd.DataFrame) -> bool:
    return bool(((spans["start"] <= end) & (spans["end"] >= start)).any()) if len(spans) else False


def use_sample() -> None:
    st.session_state["sample"] = True


def use_upload() -> None:
    st.session_state["sample"] = False


st.set_page_config(page_title="Ghost Lows CGM report", layout="wide")
banner = st.container()  # the sample-data banner, above everything else
st.title("CGM report with possible compression artifacts")
st.warning(DISCLAIMER)
st.caption(PRIVACY)

upload_col, sample_col = st.columns([3, 1], vertical_alignment="center")
uploaded = upload_col.file_uploader(
    "Dexcom Clarity or LibreView CSV export", type=["csv"], on_change=use_upload
)
sample_col.button("Try it with sample data", on_click=use_sample, type="primary")
sample_col.download_button(
    "Download the sample file",
    SAMPLE.read_bytes(),
    file_name=SAMPLE.name,
    mime="text/csv",
    on_click="ignore",
    type="tertiary",
    icon=":material/download:",
)
sample_col.caption("A synthetic 14-day export in the Dexcom Clarity format.")
sample = st.session_state.get("sample", False)
if not sample and uploaded is None:
    st.info(
        "Export your data as CSV from Dexcom Clarity or LibreView and drop the file here, or "
        "press **Try it with sample data** to see the report for a synthetic export first."
    )
    st.stop()
if sample:
    banner.info(SAMPLE_BANNER, icon=":material/science:")

try:
    data = gio.load_export(SAMPLE.read_bytes() if sample else uploaded.getvalue())
except ValueError as exc:
    st.error(f"This file could not be read as a Clarity or LibreView export: {exc}")
    st.stop()

readings = data[data["glucose"].notna()]
if len(readings) < 10:
    st.error("The file has too few glucose readings for a report.")
    st.stop()

flags = retro.flag_possible_artifacts(data)
found = retro.detections(data)
with_all = metrics.summary(data)
without = metrics.summary(retro.without_flagged(data, flags))
source = "Dexcom Clarity" if data["source"].iloc[0] == "dexcom_clarity" else "LibreView"
first, last = readings["time"].min(), readings["time"].max()
what = f"Synthetic sample in the **{source}** format" if sample else f"**{source}** export"
st.write(
    f"{what}: {len(readings):,} readings from {first:%d %b %Y} to {last:%d %b %Y} "
    f"({with_all['days']:.0f} days, sensor active {with_all['wear_pct']:.0f}% of the time)."
)

# ---------------------------------------------------------------- sample: what really happened
key, artifacts, true_glucose = None, pd.DataFrame(columns=["start", "end"]), None
if sample:
    key = json.loads(ANSWER_KEY.read_text())
    artifacts = pd.DataFrame(key["artifacts"])
    lows = pd.DataFrame(key["real_lows"])
    for frame in (artifacts, lows):
        frame[["start", "end"]] = frame[["start", "end"]].apply(pd.to_datetime)
    tg = key["true_glucose"]
    true_glucose = pd.DataFrame(
        {
            "time": pd.date_range(
                tg["start"], periods=len(tg["mg_dl"]), freq=f"{tg['step_min']}min"
            ),
            "glucose": tg["mg_dl"],
        }
    )
    sim, faults = key["simulation"], key["faults"]
    rows = [
        {
            "When": f"{night_label(a.start)}, {a.start:%H:%M}-{a.end:%H:%M}",
            "What happened": f"compression artifact (injected), {a.depth_mg_dl:.0f} mg/dL deep"
            + (", CGM below 70 mg/dL: a ghost low" if a.ghost_low else ""),
            "Flagged in this report": "yes" if overlapping(a.start, a.end, flags) else "no",
        }
        for a in artifacts.itertuples()
    ] + [
        {
            "When": (night_label(low.start) if low.night else f"{low.start:%a %d %b}")
            + f", {low.start:%H:%M}-{low.end:%H:%M}",
            "What happened": f"real low: true glucose below 70 mg/dL, lowest {low.lowest_true_mg_dl:.0f} mg/dL",
            "Flagged in this report": "yes" if overlapping(low.start, low.end, flags) else "no",
        }
        for low in lows.itertuples()
    ]
    on_artifact = sum(overlapping(f.start, f.end, artifacts) for f in flags.itertuples())
    with banner.expander("What really happened in this sample"):
        st.write(
            f"A virtual {sim['patient'].split('#')[0]} of the UVA/Padova 2008 model (simglucose), "
            f"simulated for {with_all['days']:.0f} days, with the benchmark's sensor faults added: "
            f"compression artifacts on {len(artifacts)} nights, plus signal gaps, repeated "
            "readings, noisy stretches and slow sensor drift. Because it is simulated, the true "
            "glucose is known, so we can say what each event was."
        )
        st.table(pd.DataFrame(rows).set_index("When"))
        st.write(
            f"The report raised {len(flags)} flag(s): {on_artifact} on injected artifacts and "
            f"{len(flags) - on_artifact} where no artifact was injected. This run was picked by a "
            "fixed rule (the first simulated run with two flagged artifacts and an unflagged real "
            "low at night), not for how well the flags do; on simulated data they miss many "
            "artifacts and also fall on other dips."
        )

# ---------------------------------------------------------------- consensus metrics
st.header("Consensus metrics")
st.caption(
    "Definitions and targets: international consensus on time in range (Battelino 2019); GMI from Bergenstal 2018."
)
c = st.columns(4)
c[0].metric("Time in range 70-180 mg/dL", f"{with_all['tir_70_180_pct']:.1f}%")
c[1].metric("Mean glucose", f"{with_all['mean']:.0f} mg/dL")
c[2].metric("GMI", f"{with_all['gmi_pct']:.1f}%")
c[3].metric("Coefficient of variation", f"{with_all['cv_pct']:.1f}%")
c = st.columns(4)
c[0].metric("Time below 54 mg/dL", f"{with_all['tbr_54_pct']:.1f}%")
c[1].metric("Time below 70 mg/dL", f"{with_all['tbr_70_pct']:.1f}%")
c[2].metric("Time above 180 mg/dL", f"{with_all['tar_180_pct']:.1f}%")
c[3].metric("Time above 250 mg/dL", f"{with_all['tar_250_pct']:.1f}%")

# ---------------------------------------------------------------- TBR with and without
st.header("Time below range, with and without possible compression artifacts")
st.write(
    "Both numbers are shown side by side. The first counts every reading; the second leaves out "
    "readings inside the flagged nights below. A flag is not proof: if a low felt real, it was "
    "worth treating."
)
tbr = pd.DataFrame(
    {
        "": ["Time below 70 mg/dL", "Time below 54 mg/dL"],
        "All readings": [f"{with_all['tbr_70_pct']:.2f}%", f"{with_all['tbr_54_pct']:.2f}%"],
        "Without possible compression artifacts": [
            f"{without['tbr_70_pct']:.2f}%",
            f"{without['tbr_54_pct']:.2f}%",
        ],
    }
).set_index("")
st.table(tbr)

# ---------------------------------------------------------------- AGP
st.header("Ambulatory glucose profile")
agp = metrics.agp(data).reset_index()
agp["hour"] = [int(t[:2]) + int(t[3:]) / 60 for t in agp["time_of_day"]]
base = alt.Chart(agp).encode(
    x=alt.X("hour:Q", title="time of day (h)", scale=alt.Scale(domain=[0, 24]))
)
agp_chart = (
    base.mark_area(opacity=0.18, color="#2a78d6").encode(y=alt.Y("p5:Q", title="mg/dL"), y2="p95:Q")
    + base.mark_area(opacity=0.35, color="#2a78d6").encode(y="p25:Q", y2="p75:Q")
    + base.mark_line(color="#2a78d6", strokeWidth=2).encode(y="p50:Q")
    + alt.Chart(pd.DataFrame({"y": [70, 180]}))
    .mark_rule(color="#52514e", strokeDash=[4, 3])
    .encode(y="y:Q")
)
st.altair_chart(agp_chart.properties(height=280), use_container_width=True)
st.caption(
    "Median (line), 25th-75th and 5th-95th percentiles (bands) by time of day; dashed lines at 70 and 180 mg/dL."
)

# ---------------------------------------------------------------- daily traces
st.header("Daily traces")
daily = readings.assign(
    day=readings["time"].dt.strftime("%a %d %b"),
    hour=readings["time"].dt.hour + readings["time"].dt.minute / 60,
)
daily_chart = (
    alt.Chart(daily)
    .mark_line(strokeWidth=1, opacity=0.6)
    .encode(
        x=alt.X("hour:Q", title="time of day (h)", scale=alt.Scale(domain=[0, 24])),
        y=alt.Y("glucose:Q", title="mg/dL"),
        detail="day:N",
        tooltip=["day:N", "glucose:Q"],
    )
)
st.altair_chart(daily_chart.properties(height=260), use_container_width=True)

# ---------------------------------------------------------------- nights with flags
st.header("Nights with possible compression artifacts")
if flags.empty:
    st.write("No possible compression artifacts were flagged in this export.")
else:
    st.info(FINGERSTICK)
    st.write(
        f"{len(flags)} possible compression artifact(s) flagged. A flag needs two published "
        "methods to agree and must start at night (23:00-07:00), when compression from lying on "
        "the sensor is most common."
    )
    for _, f in flags.iterrows():
        night_start = night_of(f["start"])
        night = in_night(readings, night_start)
        st.subheader(
            f"{f['label'].capitalize()} on {night_label(f['start'])}, "
            f"{f['start']:%H:%M}-{f['end']:%H:%M}"
        )
        span = pd.DataFrame({"start": [f["start"]], "end": [f["end"]]})
        chart = alt.Chart(span).mark_rect(color="#eda100", opacity=0.25).encode(
            x="start:T", x2="end:T"
        ) + alt.Chart(night).mark_line(color="#2a78d6", strokeWidth=2).encode(
            x=alt.X("time:T", title=None),
            y=alt.Y("glucose:Q", title="mg/dL"),
            tooltip=["time:T", "glucose:Q"],
        )
        if true_glucose is not None:
            chart += (
                alt.Chart(in_night(true_glucose, night_start))
                .mark_line(color="#52514e", strokeWidth=1.5, strokeDash=[4, 3])
                .encode(x="time:T", y="glucose:Q", tooltip=["time:T", "glucose:Q"])
            )
        st.altair_chart(chart.properties(height=220), use_container_width=True)
        st.write(f"**Why it was flagged:** {f['reasons']}.")
        st.caption(f"Methods: {f['citations']}.")
        if key is not None:
            st.caption(
                "In this sample: "
                + (
                    "an injected compression artifact."
                    if overlapping(f["start"], f["end"], artifacts)
                    else "no artifact was injected here."
                )
                + " Solid line: the CGM in the file; dashed line: the true glucose, known only "
                "because the sample is simulated; shaded: the flagged span."
            )

with st.expander("Detections that are not flags"):
    other = found[~found["flagged"].astype(bool)]
    if other.empty:
        st.write("None.")
    else:
        st.write(
            "These were raised by only one method or started during the day. They are listed for "
            "transparency and are not left out of any number above."
        )
        st.dataframe(
            other[["start", "end", "methods", "nadir", "depth", "reasons"]], hide_index=True
        )

st.divider()
st.caption(
    f"{DISCLAIMER} Methods: Baysal 2014; matched filter after Idi 2023 with the PISA model of "
    "Facchinetti 2016; metrics after Battelino 2019. Source code and citations: github.com/pkarakala/ghost-lows."
)
