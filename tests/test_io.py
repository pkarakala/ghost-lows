import importlib.util
import logging
from pathlib import Path

import pandas as pd
import pytest

from ghostlows import io as gio
from ghostlows import metrics
from ghostlows.io.glucobench import DEFAULT_DIR

FIXTURES = Path(__file__).parent / "fixtures"


def readings(df):
    return df[df["glucose"].notna()]


def test_clarity_sample():
    df = gio.load_clarity(FIXTURES / "clarity_sample.csv")
    gio.validate(df)
    r = readings(df)
    assert len(r) == 3 * 288 - 12  # 3 days of 5-min EGVs minus a 1-h signal loss
    assert (df["patient_id"] == "clarity:upload").all() and (df["source"] == "dexcom_clarity").all()
    low = r[r["glucose_flag"] == "below_range"]
    high = r[r["glucose_flag"] == "above_range"]
    assert len(low) == 3 and (low["glucose"] == 40).all()
    assert len(high) == 2 and (high["glucose"] == 400).all()
    assert r.loc[r["time"] == "2026-01-13 00:00", "glucose"].item() == 95
    # the calibration at 09:00 is not a CGM reading
    assert len(r[r["time"] == "2026-01-13 09:00"]) == 1
    assert r.loc[r["time"] == "2026-01-13 09:00", "glucose"].item() != 118
    assert df["insulin_bolus"].sum() == pytest.approx(3 * (4.5 + 7 + 8))
    assert df["insulin_basal"].sum() == pytest.approx(3 * 20)
    assert df["carbs"].sum() == pytest.approx(3 * (45 + 70 + 80))
    assert df["time"].dt.tz is None


def test_clarity_drops_personal_details():
    df = gio.load_clarity(FIXTURES / "clarity_sample.csv")
    text = df.astype(str).to_csv()
    assert "Synthetic" not in text and "Fixture" not in text


def test_clarity_mmol_export_is_converted():
    df = gio.load_clarity(FIXTURES / "clarity_mmol.csv")
    assert df["glucose"].tolist() == pytest.approx([99.0, 70.2, 40.0, 180.0])
    assert df["glucose_flag"].astype(str).tolist() == ["ok", "ok", "below_range", "ok"]


def test_clarity_accepts_bytes_and_file_objects():
    data = (FIXTURES / "clarity_sample.csv").read_bytes()
    from_bytes = gio.load_clarity(data)
    with open(FIXTURES / "clarity_sample.csv", "rb") as f:
        from_file = gio.load_clarity(f)
    pd.testing.assert_frame_equal(from_bytes, from_file)


def test_libreview_sample():
    df = gio.load_libreview(FIXTURES / "libreview_sample.csv")
    gio.validate(df)
    r = readings(df)
    assert len(r) == 3 * 96 - 4  # 3 days of 15-min history minus a 1-h gap; scans excluded
    assert r["time"].min() == pd.Timestamp("2026-01-13 00:00")  # month first, from "01-13-2026"
    assert r["glucose_flag"].astype(str).value_counts()[
        ["below_range", "above_range"]
    ].tolist() == [1, 1]
    assert df["insulin_bolus"].sum() == pytest.approx(3 * (4.5 + 7 + 8))
    assert df["insulin_basal"].sum() == pytest.approx(60)
    assert df["carbs"].sum() == pytest.approx(585)
    assert metrics.sampling_interval(r["time"]) == 15
    assert "Synthetic" not in df.astype(str).to_csv()


def test_libreview_scans_on_request():
    df = gio.load_libreview(FIXTURES / "libreview_sample.csv", include_scans=True)
    assert len(readings(df)) == 3 * 96 - 4 + 9


def test_libreview_day_first_is_inferred():
    df = gio.load_libreview(FIXTURES / "libreview_dayfirst.csv")
    assert df["time"].tolist() == list(
        pd.to_datetime(["2026-01-13 23:45", "2026-01-14 00:00", "2026-01-14 00:15"])
    )
    assert df["glucose_flag"].astype(str).tolist() == ["ok", "below_range", "ok"]


def test_libreview_ambiguous_dates_warn_and_assume_month_first():
    stamps = pd.Series(["01-02-2026 00:00", "01-02-2026 00:15"])
    with pytest.warns(UserWarning, match="ambiguous"):
        out = gio.libreview.parse_timestamps(stamps)
    assert out.iloc[0] == pd.Timestamp("2026-01-02 00:00")
    assert gio.libreview.parse_timestamps(stamps, dayfirst=True).iloc[0] == pd.Timestamp(
        "2026-02-01"
    )


def test_libreview_twelve_hour_clock_and_iso_dates():
    p = gio.libreview.parse_timestamps
    assert p(pd.Series(["1/13/2026 1:05 PM"])).iloc[0] == pd.Timestamp("2026-01-13 13:05")
    assert p(pd.Series(["1/13/2026 12:05 AM"])).iloc[0] == pd.Timestamp("2026-01-13 00:05")
    assert p(pd.Series(["2026-01-13 07:30"])).iloc[0] == pd.Timestamp("2026-01-13 07:30")


def test_detect_and_load_export():
    clarity, libre = FIXTURES / "clarity_sample.csv", FIXTURES / "libreview_sample.csv"
    assert gio.detect_export(clarity) == "clarity" and gio.detect_export(libre) == "libreview"
    assert gio.load_export(libre)["source"].iloc[0] == "libreview"
    with pytest.raises(ValueError, match="not a recognised"):
        gio.detect_export(b"a,b\n1,2\n")


def write_glucobench(folder: Path) -> None:
    """Tiny files with the real files' quirks (see docs/reference/DATA.md §1)."""
    folder.mkdir()
    (folder / "weinstock.csv").write_text(
        "id,gl,time,Gender\n199,39,1900-01-01 00:00:00,F\n199,120,1900-01-01 00:05:00,F\n"
        "199,401,1900-01-01 00:10:00,F\n7,100,1899-12-31 23:55:00,M\n"
    )
    (folder / "colas.csv").write_text(
        ",id,time,gl,gender\n0,1,2012-01-01 00:00:00,40,1\n1,1,2012-01-01 00:05:00,86,1\n"
    )
    (folder / "dubosson.csv").write_text(
        "id,time,gl,fast_insulin\n"
        "1.0,2014-10-01 19:14:00,39.6,6.0\n1.0,2014-10-01 19:19:00,180.0,5.8\n"
    )


def test_load_glucobench_quirks(tmp_path):
    folder = tmp_path / "glucobench"
    write_glucobench(folder)
    w = gio.load_glucobench("weinstock", folder)
    gio.validate(w)
    assert sorted(w["patient_id"].unique()) == ["weinstock:199", "weinstock:7"]
    p199 = w[w["patient_id"] == "weinstock:199"]
    assert p199["glucose"].tolist() == [40.0, 120.0, 400.0]
    assert p199["glucose_flag"].astype(str).tolist() == ["below_range", "ok", "above_range"]
    c = gio.load_glucobench("colas", folder)
    assert c["patient_id"].iloc[0] == "colas:1" and c["glucose_flag"].iloc[0] == "below_range"
    d = gio.load_glucobench("dubosson", folder)
    assert d["patient_id"].iloc[0] == "dubosson:1" and d["insulin_bolus"].isna().all()
    with pytest.raises(ValueError):
        gio.load_glucobench("nope", folder)
    with pytest.raises(FileNotFoundError, match="download_data"):
        gio.load_glucobench("hall", folder)


EXPECTED = {  # rows, patients; measured on the pinned archive (docs/reference/DATA.md §1)
    "weinstock": (647_858, 200),
    "dubosson": (8_055, 9),
    "hall": (105_426, 57),
    "colas": (114_253, 208),
    "iglu": (13_866, 5),
}


@pytest.mark.skipif(
    not (DEFAULT_DIR / "weinstock.csv").exists(), reason="GlucoBench not downloaded"
)
@pytest.mark.parametrize("name", list(EXPECTED))
def test_real_glucobench_files_load(name, caplog):
    with caplog.at_level(logging.INFO, logger="ghostlows.io.glucobench"):
        df = gio.load_glucobench(name)
    gio.validate(df)
    assert (len(df), df["patient_id"].nunique()) == EXPECTED[name]
    assert f"loaded {name}: {EXPECTED[name][0]} rows, {EXPECTED[name][1]} patients" in caplog.text


def test_fixtures_match_their_generator(tmp_path):
    spec = importlib.util.spec_from_file_location("make_fixtures", FIXTURES / "make_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(tmp_path)
    for path in sorted(tmp_path.iterdir()):
        assert path.read_bytes() == (FIXTURES / path.name).read_bytes(), path.name


AZT1D_HEADER = (
    "EventDateTime,DeviceMode,BolusType,Basal,CorrectionDelivered,"
    "TotalBolusInsulinDelivered,FoodDelivered,CarbSize,CGM"
)


def test_azt1d_keeps_user_boluses_apart_and_drops_unresolvable_readings(tmp_path):
    import zipfile

    rows = [
        "2026-01-05 00:04:00,,,,,,,,151",
        "2026-01-05 00:04:00,,,,,,,,151",  # exact duplicate row
        "2026-01-05 00:09:00,sleep,,0.8,,,,,40",
        "2026-01-05 00:14:00,,,,,,,,160",
        "2026-01-05 00:14:00,,,,,,,,120",  # two different readings at one time
        "2026-01-05 00:19:00,,Automatic Bolus/Correction,,1.2,1.2,0.0,0.0,180",
        "2026-01-05 00:24:00,,Standard,,0.0,4.0,4.0,40.0,400",
        "2026-01-05 00:29:00,sleepsleep,Extended 50.00%/3.00,,0.0,1.5,1.5,36.0,170",
        "2026-01-05 00:34:00,0,0,0.5,0.0,0.0,0.0,0,165",
    ]
    other = (
        "EventDateTime,Basal,BolusType,CarbSize,CorrectionDelivered,FoodDelivered,"
        "Readings (CGM / BGM),TotalBolusInsulinDelivered,DeviceMode\n"
        "2026-01-05 00:00:00,,,,,,99,,exercise\n"
    )
    archive = tmp_path / "azt1d.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "AZT1D 2025/CGM Records/Subject 1/Subject 1.csv", "\n".join([AZT1D_HEADER, *rows])
        )
        z.writestr("AZT1D 2025/CGM Records/Subject 2/Subject 2.csv", other)
        z.writestr("AZT1D 2025/Visual Statistics/Subject 1/notes.csv", "not a record")
    df = gio.load_azt1d(archive)
    gio.validate(df)
    s1 = df[df["patient_id"] == "azt1d:1"]
    assert len(s1) == 8
    clash = s1[s1["time"] == pd.Timestamp("2026-01-05 00:14")]
    assert len(clash) == 2 and clash["glucose"].isna().all()
    assert s1.loc[s1["glucose_flag"] == "below_range", "glucose"].tolist() == [40.0]
    assert s1.loc[s1["glucose_flag"] == "above_range", "glucose"].tolist() == [400.0]
    assert s1["insulin_bolus"].sum() == pytest.approx(5.5)  # standard + extended, user-entered
    assert s1["insulin_bolus_auto"].sum() == pytest.approx(1.2)
    assert s1["carbs"].sum() == pytest.approx(76.0)
    assert set(s1["device_mode"]) == {"", "sleep"}
    s2 = df[df["patient_id"] == "azt1d:2"]
    assert s2["glucose"].tolist() == [99.0] and s2["device_mode"].tolist() == ["exercise"]
