from pathlib import Path
import pandas as pd
import datetime

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "saetoo_ajalugu.csv"

HISTORY_COLUMNS = [
    "kuupaev", "materjal_paksus_mm",
    "toorik_laius_mm", "toorik_pikkus_mm",
    "detail_laius_mm", "detail_pikkus_mm",
    "detailide_arv", "avaraadiusega_ketas",
    "ketas", "avatud_plaadid",
    "poogitud_aeg_sek", "tegelik_aeg_sek",
    "tunnihind_eur", "materjali_hind_m2_eur",
    "kokku_kulu_eur", "markused",
]

def normalize_history_df(df):
    for col in HISTORY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[HISTORY_COLUMNS]

def load_history():
    if HISTORY_FILE.exists():
        try:
            df = pd.read_csv(HISTORY_FILE)
            return normalize_history_df(df)
        except Exception:
            pass
    return pd.DataFrame(columns=HISTORY_COLUMNS)

def save_history_row(row):
    existing = load_history()
    new_row = normalize_history_df(pd.DataFrame([row]))
    combined = pd.concat([existing, new_row], ignore_index=True)
    combined.to_csv(HISTORY_FILE, index=False)

def build_pending_save_row(state, result, actual_blade, actual_rotated,
                            actual_time_sec, rework_time_sec):
    total_sec_save = actual_time_sec if actual_time_sec is not None else result["total_sec"]
    if rework_time_sec:
        total_sec_save += rework_time_sec
    return {
        "kuupaev": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "materjal_paksus_mm": state.get("thickness_mm"),
        "toorik_laius_mm": state.get("raw_width_mm"),
        "toorik_pikkus_mm": state.get("raw_length_mm"),
        "detail_laius_mm": state.get("detail_width_mm"),
        "detail_pikkus_mm": state.get("detail_length_mm"),
        "detailide_arv": state.get("detail_count"),
        "avaraadiusega_ketas": "Jah" if result["blade"]["is_default"] else "Ei",
        "ketas": actual_blade,
        "avatud_plaadid": result["opened_sheet_count"],
        "poogitud_aeg_sek": round(result["total_sec"]),
        "tegelik_aeg_sek": round(total_sec_save),
        "tunnihind_eur": state.get("hourly_rate_eur"),
        "materjali_hind_m2_eur": state.get("material_price_m2_eur"),
        "kokku_kulu_eur": round(result["total_estimated_cost_eur"], 2),
        "markused": state.get("notes", ""),
    }
