import math
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

try:
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestRegressor

    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


st.set_page_config(page_title="Saetöö kalkulaator", page_icon="🪚", layout="wide")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "saetoo_ajalugu.csv"

MAX_LENGTH_MM = 3050.0
MAX_WIDTH_MM = 2050.0

MIN_USABLE_OFFCUT_WIDTH_MM = 150.0
MIN_USABLE_OFFCUT_LENGTH_MM = 1000.0
MIN_USABLE_OFFCUT_AREA_M2 = 0.15

BASE_SETUP_SEC = 20 * 60
SMALL_BLADE_SWITCH_SEC = 5 * 60
BASE_HANDLING_PER_SHEET_SEC = 90
HANDLING_PER_M2_SEC = 45
RIP_HANDLING_PER_CUT_SEC = 20
PARTIAL_SHEET_EXTRA_SEC = 60
THIN_MATERIAL_HANDLING_FACTOR = 0.33

ML_MIN_ROWS_TO_TRAIN = 30
ML_MIN_ROWS_TO_DECIDE = 50
ML_MAX_ACCEPTABLE_MAE_SEC = 15 * 60

LARGE_BLADE = {
    "blade": "5.6 mm",
    "kerf_mm": 5.6,
    "max_stack_mm": 80.0,
    "is_default": True,
}

SMALL_BLADE = {
    "blade": "3.1 mm",
    "kerf_mm": 3.1,
    "max_stack_mm": 30.0,
    "is_default": False,
}

BLADES = [LARGE_BLADE, SMALL_BLADE]

THICKNESS_OPTIONS_MM = list(range(1, 13)) + [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]

COLOR_SHEET = "#e6e6e6"
COLOR_DETAIL = "#b7d7ff"
COLOR_DETAIL_EDGE = "#1f4e79"

DEFAULTS = {
    "thickness_mm": 20,
    "raw_width_mm": "",
    "raw_length_mm": "",
    "detail_length_mm": "",
    "detail_width_mm": "",
    "detail_count": "",
    "trim_edges": True,
    "order_id": "",
    "operator": "",
    "material": "",
    "machine_id": "",
    "shift": "",
    "actual_time_min": "",
    "was_scrap": False,
    "scrap_reason": "",
    "rework_time_min": "",
    "last_results": None,
    "best_result": None,
    "history_df": pd.DataFrame(),
    "pending_save_row": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def clear_calc_inputs():
    st.session_state.thickness_mm = 20
    st.session_state.raw_width_mm = ""
    st.session_state.raw_length_mm = ""
    st.session_state.detail_length_mm = ""
    st.session_state.detail_width_mm = ""
    st.session_state.detail_count = ""
    st.session_state.trim_edges = True
    st.session_state.last_results = None
    st.session_state.best_result = None
    st.session_state.pending_save_row = None


def clear_worklog_inputs():
    st.session_state.order_id = ""
    st.session_state.operator = ""
    st.session_state.material = ""
    st.session_state.machine_id = ""
    st.session_state.shift = ""
    st.session_state.actual_time_min = ""
    st.session_state.was_scrap = False
    st.session_state.scrap_reason = ""
    st.session_state.rework_time_min = ""
    st.session_state.pending_save_row = None


def get_sec_per_meter(thickness_mm):
    if 1 <= thickness_mm <= 20:
        return 6
    if 20 < thickness_mm <= 40:
        return 7.5
    if 40 < thickness_mm <= 50:
        return 10
    if 50 < thickness_mm <= 60:
        return 12
    if 60 < thickness_mm <= 70:
        return 18
    if 70 < thickness_mm <= 80:
        return 24
    if 80 < thickness_mm <= 90:
        return 36
    return None


def sec_to_minsec(seconds):
    if seconds is None or pd.isna(seconds):
        return "-"
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    sec = round(seconds % 60, 1)
    return f"{minutes} min {sec} sek"


def fmt(v):
    if isinstance(v, float) and float(v).is_integer():
        return str(int(v))
    return str(round(float(v), 2))


def parse_float_text(value):
    return float(str(value).replace(",", ".").strip())


def area_m2(width_mm, length_mm):
    if width_mm <= 0 or length_mm <= 0:
        return 0.0
    return (width_mm * length_mm) / 1_000_000.0


def max_pieces_in_length(total_len_mm, piece_len_mm, kerf_mm):
    if total_len_mm <= 0 or piece_len_mm <= 0:
        return 0
    return max(0, math.floor((total_len_mm + kerf_mm) / (piece_len_mm + kerf_mm)))


def used_size_mm(piece_count, piece_size_mm, kerf_mm):
    if piece_count <= 0:
        return 0.0
    return piece_count * piece_size_mm + (piece_count - 1) * kerf_mm


def blade_switch_setup_sec(blade):
    return 0 if blade["is_default"] else SMALL_BLADE_SWITCH_SEC


def offcut_is_usable(width_mm, length_mm):
    short_side = min(width_mm, length_mm)
    long_side = max(width_mm, length_mm)
    offcut_area_m2 = area_m2(width_mm, length_mm)
    return (
        short_side >= MIN_USABLE_OFFCUT_WIDTH_MM
        and long_side >= MIN_USABLE_OFFCUT_LENGTH_MM
        and offcut_area_m2 >= MIN_USABLE_OFFCUT_AREA_M2
    )


def get_simple_offcuts(raw_width_mm, raw_length_mm, used_width_mm, used_length_mm):
    side_width = max(0.0, raw_width_mm - used_width_mm)
    end_length = max(0.0, raw_length_mm - used_length_mm)
    offcuts = []

    if side_width > 0:
        offcuts.append(
            {
                "name": "Küljeriba",
                "width_mm": side_width,
                "length_mm": raw_length_mm,
                "area_m2": area_m2(side_width, raw_length_mm),
                "usable": offcut_is_usable(side_width, raw_length_mm),
            }
        )

    if end_length > 0 and used_width_mm > 0:
        offcuts.append(
            {
                "name": "Otsajääk",
                "width_mm": used_width_mm,
                "length_mm": end_length,
                "area_m2": area_m2(used_width_mm, end_length),
                "usable": offcut_is_usable(used_width_mm, end_length),
            }
        )

    return offcuts


def summarize_offcuts(full_offcuts, partial_offcuts, full_pattern_count, partial_pattern_count):
    usable_area_m2 = 0.0
    all_offcuts = []

    for offcut in full_offcuts:
        o = offcut.copy()
        o["quantity"] = full_pattern_count
        all_offcuts.append(o)
        if offcut["usable"]:
            usable_area_m2 += offcut["area_m2"] * full_pattern_count

    for offcut in partial_offcuts:
        o = offcut.copy()
        o["quantity"] = partial_pattern_count
        all_offcuts.append(o)
        if offcut["usable"]:
            usable_area_m2 += offcut["area_m2"] * partial_pattern_count

    usable_offcuts = [o for o in all_offcuts if o["usable"] and o["quantity"] > 0]
    all_existing_offcuts = [o for o in all_offcuts if o["quantity"] > 0]

    largest_usable = max(usable_offcuts, key=lambda o: o["area_m2"]) if usable_offcuts else None
    largest_any = max(all_existing_offcuts, key=lambda o: o["area_m2"]) if all_existing_offcuts else None

    return usable_area_m2, largest_usable, largest_any


def validate_common(thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count):
    if thickness_mm <= 0:
        return "Paksus peab olema suurem kui 0 mm."
    if raw_length_mm <= 0 or raw_length_mm > MAX_LENGTH_MM:
        return f"Tooriku pikkus peab olema vahemikus 1 kuni {int(MAX_LENGTH_MM)} mm."
    if raw_width_mm <= 0 or raw_width_mm > MAX_WIDTH_MM:
        return f"Tooriku laius peab olema vahemikus 1 kuni {int(MAX_WIDTH_MM)} mm."
    if detail_length_mm <= 0 or detail_width_mm <= 0:
        return "Detaili mõõdud peavad olema suuremad kui 0 mm."
    if detail_count < 1:
        return "Detailide arv peab olema vähemalt 1."
    if thickness_mm not in THICKNESS_OPTIONS_MM:
        return (
            "Lubatud paksused on 1 kuni 12 mm sammuga 1 ning edasi "
            "15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85 ja 90 mm."
        )
    if get_sec_per_meter(thickness_mm) is None:
        return "Paksuse vahemik peab olema 1 kuni 90 mm."
    return None


def build_partial_layout_options(partial_piece_count, max_across, max_along, piece_w, piece_l, kerf_mm, raw_width_mm, raw_length_mm):
    options = []

    for cols in range(1, min(max_across, partial_piece_count) + 1):
        rows = math.ceil(partial_piece_count / cols)
        if rows > max_along:
            continue

        used_w = used_size_mm(cols, piece_w, kerf_mm)
        used_l = used_size_mm(rows, piece_l, kerf_mm)

        if used_w > raw_width_mm or used_l > raw_length_mm:
            continue

        offcuts = get_simple_offcuts(raw_width_mm, raw_length_mm, used_w, used_l)
        usable_area = sum(o["area_m2"] for o in offcuts if o["usable"])
        theoretical_offcut = max(0.0, area_m2(raw_width_mm, raw_length_mm) - area_m2(used_w, used_l))
        non_usable = max(0.0, theoretical_offcut - usable_area)

        options.append(
            {
                "cols": cols,
                "rows": rows,
                "used_width_mm": used_w,
                "used_length_mm": used_l,
                "usable_offcut_area_m2": usable_area,
                "non_usable_offcut_area_m2": non_usable,
                "offcuts": offcuts,
            }
        )

    if not options:
        return None

    options.sort(
        key=lambda x: (
            -x["usable_offcut_area_m2"],
            x["non_usable_offcut_area_m2"],
            x["used_width_mm"] * x["used_length_mm"],
        )
    )
    return options[0]


def build_orientation_result(
    blade,
    thickness_mm,
    raw_width_mm,
    raw_length_mm,
    input_detail_width_mm,
    input_detail_length_mm,
    detail_count,
    trim_edges,
    rotated,
):
    if thickness_mm > blade["max_stack_mm"]:
        return None

    if rotated:
        detail_width_mm = input_detail_length_mm
        detail_length_mm = input_detail_width_mm
    else:
        detail_width_mm = input_detail_width_mm
        detail_length_mm = input_detail_length_mm

    kerf_mm = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)

    across = max_pieces_in_length(raw_width_mm, detail_width_mm, kerf_mm)
    along = max_pieces_in_length(raw_length_mm, detail_length_mm, kerf_mm)
    pieces_per_sheet = across * along

    if pieces_per_sheet <= 0:
        return None

    full_pattern_count = detail_count // pieces_per_sheet
    partial_piece_count = detail_count % pieces_per_sheet
    partial_pattern_count = 1 if partial_piece_count > 0 else 0
    opened_sheet_count = full_pattern_count + partial_pattern_count

    full_used_width_mm = used_size_mm(across, detail_width_mm, kerf_mm)
    full_used_length_mm = used_size_mm(along, detail_length_mm, kerf_mm)

    if trim_edges:
        rip_cut_count_full = across
        cross_cut_count_full = across * along
    else:
        rip_cut_count_full = max(0, across - 1)
        cross_cut_count_full = across * max(0, along - 1)

    kerf_area_full_mm2 = rip_cut_count_full * raw_length_mm * kerf_mm + cross_cut_count_full * detail_width_mm * kerf_mm
    net_detail_area_full_mm2 = pieces_per_sheet * detail_width_mm * detail_length_mm

    partial_used_width_mm = 0.0
    partial_used_length_mm = 0.0
    partial_cols = 0
    partial_rows = 0
    partial_offcuts = []
    kerf_area_partial_mm2 = 0.0
    rip_cut_count_partial = 0
    cross_cut_count_partial = 0

    if partial_piece_count > 0:
        partial_layout = build_partial_layout_options(
            partial_piece_count,
            across,
            along,
            detail_width_mm,
            detail_length_mm,
            kerf_mm,
            raw_width_mm,
            raw_length_mm,
        )

        if partial_layout is None:
            return None

        partial_cols = partial_layout["cols"]
        partial_rows = partial_layout["rows"]
        partial_used_width_mm = partial_layout["used_width_mm"]
        partial_used_length_mm = partial_layout["used_length_mm"]
        partial_offcuts = partial_layout["offcuts"]

        if trim_edges:
            rip_cut_count_partial = partial_cols
            cross_cut_count_partial = partial_cols * partial_rows
        else:
            rip_cut_count_partial = max(0, partial_cols - 1)
            cross_cut_count_partial = partial_cols * max(0, partial_rows - 1)

        kerf_area_partial_mm2 = (
            rip_cut_count_partial * raw_length_mm * kerf_mm
            + cross_cut_count_partial * detail_width_mm * kerf_mm
        )

    net_detail_area_m2 = (
        full_pattern_count * net_detail_area_full_mm2
        + partial_piece_count * detail_width_mm * detail_length_mm
    ) / 1_000_000.0
    kerf_area_m2 = (full_pattern_count * kerf_area_full_mm2 + kerf_area_partial_mm2) / 1_000_000.0
    consumed_area_m2 = net_detail_area_m2 + kerf_area_m2

    sheet_area_m2 = area_m2(raw_width_mm, raw_length_mm)
    opened_sheet_area_m2 = opened_sheet_count * sheet_area_m2
    theoretical_offcut_area_m2 = max(0.0, opened_sheet_area_m2 - consumed_area_m2)

    full_offcuts = get_simple_offcuts(raw_width_mm, raw_length_mm, full_used_width_mm, full_used_length_mm)

    usable_offcut_area_m2, largest_usable_offcut, largest_any_offcut = summarize_offcuts(
        full_offcuts,
        partial_offcuts,
        full_pattern_count,
        partial_pattern_count,
    )

    non_usable_offcut_area_m2 = max(0.0, theoretical_offcut_area_m2 - usable_offcut_area_m2)

    if partial_piece_count > 0:
        scheme_used_width_mm = partial_used_width_mm
        scheme_used_length_mm = partial_used_length_mm
        scheme_piece_count = partial_piece_count
    else:
        scheme_used_width_mm = full_used_width_mm
        scheme_used_length_mm = full_used_length_mm
        scheme_piece_count = pieces_per_sheet

    rip_cut_count = full_pattern_count * rip_cut_count_full + rip_cut_count_partial
    cross_cut_count = full_pattern_count * cross_cut_count_full + cross_cut_count_partial
    total_cut_count = rip_cut_count + cross_cut_count

    rip_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * rip_cut_count
    cross_time_sec = (detail_width_mm / 1000.0) * sec_per_m * 2 * cross_cut_count
    cutting_time_sec = rip_time_sec + cross_time_sec

    setup_sec = BASE_SETUP_SEC + blade_switch_setup_sec(blade)
    handling_per_sheet_sec = BASE_HANDLING_PER_SHEET_SEC + sheet_area_m2 * HANDLING_PER_M2_SEC
    handling_factor = THIN_MATERIAL_HANDLING_FACTOR if thickness_mm < 10 else 1.0

    handling_sec = (
        opened_sheet_count * handling_per_sheet_sec
        + rip_cut_count * RIP_HANDLING_PER_CUT_SEC
        + (PARTIAL_SHEET_EXTRA_SEC if partial_pattern_count > 0 else 0)
    ) * handling_factor

    total_sec = cutting_time_sec + setup_sec + handling_sec
    warning = "Hoiatus: alla 20 mm ribade puhul võivad masina käpad segada." if detail_width_mm < 20 else None

    return {
        "blade": blade,
        "rotated": rotated,
        "trim_edges": trim_edges,
        "raw_width_mm": raw_width_mm,
        "raw_length_mm": raw_length_mm,
        "input_detail_width_mm": input_detail_width_mm,
        "input_detail_length_mm": input_detail_length_mm,
        "detail_width_mm": detail_width_mm,
        "detail_length_mm": detail_length_mm,
        "detail_count": detail_count,
        "across": across,
        "along": along,
        "pieces_per_sheet": pieces_per_sheet,
        "opened_sheet_count": opened_sheet_count,
        "full_pattern_count": full_pattern_count,
        "partial_pattern_count": partial_pattern_count,
        "partial_piece_count": partial_piece_count,
        "partial_cols": partial_cols,
        "partial_rows": partial_rows,
        "net_detail_area_m2": net_detail_area_m2,
        "kerf_area_m2": kerf_area_m2,
        "consumed_area_m2": consumed_area_m2,
        "opened_sheet_area_m2": opened_sheet_area_m2,
        "theoretical_offcut_area_m2": theoretical_offcut_area_m2,
        "usable_offcut_area_m2": usable_offcut_area_m2,
        "non_usable_offcut_area_m2": non_usable_offcut_area_m2,
        "largest_usable_offcut": largest_usable_offcut,
        "largest_any_offcut": largest_any_offcut,
        "full_offcuts": full_offcuts,
        "partial_offcuts": partial_offcuts,
        "rip_cut_count": rip_cut_count,
        "cross_cut_count": cross_cut_count,
        "total_cut_count": total_cut_count,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "handling_sec": handling_sec,
        "handling_per_sheet_sec": handling_per_sheet_sec,
        "handling_factor": handling_factor,
        "total_sec": total_sec,
        "scheme_used_width_mm": scheme_used_width_mm,
        "scheme_used_length_mm": scheme_used_length_mm,
        "scheme_piece_count": scheme_piece_count,
        "kerf_mm": kerf_mm,
        "warning": warning,
        "ml_predicted_actual_time_sec": None,
    }


def result_sort_key(result):
    return (
        result["opened_sheet_count"],
        result["consumed_area_m2"],
        -result["usable_offcut_area_m2"],
        result["non_usable_offcut_area_m2"],
        result["total_cut_count"],
        result["total_sec"],
        0 if result["blade"]["is_default"] else 1,
    )


def result_sort_key_ml(result):
    predicted_time = result.get("ml_predicted_actual_time_sec")
    if predicted_time is None or pd.isna(predicted_time):
        predicted_time = result["total_sec"]

    return (
        result["opened_sheet_count"],
        result["consumed_area_m2"],
        -result["usable_offcut_area_m2"],
        result["non_usable_offcut_area_m2"],
        predicted_time,
        result["total_cut_count"],
        0 if result["blade"]["is_default"] else 1,
    )


def choose_best_result(results):
    valid = [r for r in results if r is not None]
    return min(valid, key=result_sort_key) if valid else None


def choose_best_result_ml(results):
    valid = [r for r in results if r is not None]
    return min(valid, key=result_sort_key_ml) if valid else None


def build_best_result_for_blade(
    blade,
    thickness_mm,
    raw_width_mm,
    raw_length_mm,
    detail_width_mm,
    detail_length_mm,
    detail_count,
    trim_edges,
):
    normal = build_orientation_result(
        blade,
        thickness_mm,
        raw_width_mm,
        raw_length_mm,
        detail_width_mm,
        detail_length_mm,
        detail_count,
        trim_edges,
        False,
    )
    rotated = build_orientation_result(
        blade,
        thickness_mm,
        raw_width_mm,
        raw_length_mm,
        detail_width_mm,
        detail_length_mm,
        detail_count,
        trim_edges,
        True,
    )
    return choose_best_result([normal, rotated])


def add_blade_reasons(results, best):
    for r in results:
        if r is None:
            continue

        orientation_text = "pööratud detailiga" if r["rotated"] else "pööramata detailiga"
        trim_text = "ääretrimmi arvestusega" if r["trim_edges"] else "ilma ääretrimmi arvestuseta"
        prefix = "Soovitatud variant" if r is best else "Alternatiiv"

        ml_text = ""
        if r.get("ml_predicted_actual_time_sec") is not None:
            ml_text = f", ML prognoos {sec_to_minsec(r['ml_predicted_actual_time_sec'])}"

        r["blade_reason"] = (
            f"{prefix}: {orientation_text}, {trim_text}, avatud plaate {r['opened_sheet_count']} tk, "
            f"detailide pind + saetee kadu {r['consumed_area_m2']:.2f} m², "
            f"kasutatav jääk {r['usable_offcut_area_m2']:.2f} m², "
            f"mittearvestatav jääk {r['non_usable_offcut_area_m2']:.2f} m², "
            f"lõikeid kokku {r['total_cut_count']}{ml_text}."
        )


def offcut_label(offcut):
    if offcut is None:
        return "Puudub"
    usable_text = "kasutatav" if offcut["usable"] else "mittearvestatav"
    return (
        f"{offcut['name']}: {fmt(offcut['width_mm'])} x {fmt(offcut['length_mm'])} mm, "
        f"{offcut['area_m2']:.2f} m², {usable_text}"
    )


def draw_scheme(result):
    piece_w = float(result["detail_width_mm"])
    piece_h = float(result["detail_length_mm"])
    kerf = float(result["kerf_mm"])
    scheme_w = max(float(result.get("scheme_used_width_mm", piece_w)), piece_w)
    scheme_l = max(float(result.get("scheme_used_length_mm", piece_h)), piece_h)
    total_pieces = int(result.get("scheme_piece_count", 0))

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_xlim(0, scheme_w)
    ax.set_ylim(scheme_l, 0)
    ax.set_aspect("equal", adjustable="box")
    ax.add_patch(Rectangle((0, 0), scheme_w, scheme_l, facecolor=COLOR_SHEET, edgecolor="black", linewidth=2))

    placed = 0
    x = 0.0
    while x + piece_w <= scheme_w + 0.001 and placed < total_pieces:
        y = 0.0
        while y + piece_h <= scheme_l + 0.001 and placed < total_pieces:
            ax.add_patch(
                Rectangle(
                    (x, y),
                    piece_w,
                    piece_h,
                    facecolor=COLOR_DETAIL,
                    edgecolor=COLOR_DETAIL_EDGE,
                    linewidth=0.8,
                )
            )
            placed += 1
            y += piece_h + kerf
        x += piece_w + kerf

    ax.set_title("Lõikeskeem")
    ax.set_xlabel("Laius mm")
    ax.set_ylabel("Pikkus mm")
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    return fig


def load_history():
    if HISTORY_FILE.exists():
        try:
            return pd.read_csv(HISTORY_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def save_history_row(row):
    df = pd.DataFrame([row])
    if HISTORY_FILE.exists():
        old = pd.read_csv(HISTORY_FILE)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(HISTORY_FILE, index=False)
    st.cache_resource.clear()


def get_onehot_encoder():
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


@st.cache_resource
def train_ml_model_cached(csv_path, mtime):
    if not SKLEARN_AVAILABLE:
        return None, None, None, 0

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None, None, None, 0

    if df.empty or "actual_time_sec" not in df.columns:
        return None, None, None, len(df)

    numeric_features = [
        "thickness_mm",
        "raw_width_mm",
        "raw_length_mm",
        "detail_width_mm",
        "detail_length_mm",
        "detail_count",
        "opened_sheet_count",
        "pieces_per_sheet",
        "rip_cut_count",
        "cross_cut_count",
        "total_cut_count",
        "kerf_mm",
        "rotated",
        "trim_edges",
        "estimated_time_sec",
        "usable_offcut_m2",
        "non_usable_offcut_m2",
        "was_scrap",
        "rework_time_sec",
    ]

    categorical_features = [
        "operator",
        "material",
        "machine_id",
        "shift",
        "blade",
    ]

    available_numeric = [c for c in numeric_features if c in df.columns]
    available_categorical = [c for c in categorical_features if c in df.columns]

    data = df.dropna(subset=["actual_time_sec"]).copy()
    data["actual_time_sec"] = pd.to_numeric(data["actual_time_sec"], errors="coerce")
    data = data.dropna(subset=["actual_time_sec"])

    if len(data) < ML_MIN_ROWS_TO_TRAIN:
        return None, available_numeric + available_categorical, None, len(data)

    for col in available_numeric:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    for col in available_categorical:
        data[col] = data[col].fillna("").astype(str)

    X = data[available_numeric + available_categorical].copy()
    y = data["actual_time_sec"].astype(float)

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", SimpleImputer(strategy="median"), available_numeric),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", get_onehot_encoder()),
                    ]
                ),
                available_categorical,
            ),
        ],
        remainder="drop",
    )

    model = Pipeline(
        [
            ("preprocess", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=300,
                    random_state=42,
                    min_samples_leaf=3,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    mae = None
    if len(data) >= 50:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.25,
            random_state=42,
        )
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))

    model.fit(X, y)

    return model, available_numeric + available_categorical, mae, len(data)


def get_trained_model():
    if not HISTORY_FILE.exists():
        return None, None, None, 0
    mtime = HISTORY_FILE.stat().st_mtime
    return train_ml_model_cached(str(HISTORY_FILE), mtime)


def predict_result_time(model, feature_cols, result, thickness_mm):
    if model is None or not feature_cols:
        return None

    ml_row = {
        "thickness_mm": int(thickness_mm),
        "raw_width_mm": result["raw_width_mm"],
        "raw_length_mm": result["raw_length_mm"],
        "detail_width_mm": result["input_detail_width_mm"],
        "detail_length_mm": result["input_detail_length_mm"],
        "detail_count": result["detail_count"],
        "opened_sheet_count": result["opened_sheet_count"],
        "pieces_per_sheet": result["pieces_per_sheet"],
        "rip_cut_count": result["rip_cut_count"],
        "cross_cut_count": result["cross_cut_count"],
        "total_cut_count": result["total_cut_count"],
        "kerf_mm": result["kerf_mm"],
        "rotated": int(result["rotated"]),
        "trim_edges": int(result["trim_edges"]),
        "estimated_time_sec": result["total_sec"],
        "usable_offcut_m2": result["usable_offcut_area_m2"],
        "non_usable_offcut_m2": result["non_usable_offcut_area_m2"],
        "was_scrap": 0,
        "rework_time_sec": 0.0,
        "operator": st.session_state.operator,
        "material": st.session_state.material,
        "machine_id": st.session_state.machine_id,
        "shift": st.session_state.shift,
        "blade": result["blade"]["blade"],
    }

    X = pd.DataFrame([ml_row])
    for col in feature_cols:
        if col not in X.columns:
            X[col] = None
    X = X[feature_cols]

    return float(model.predict(X)[0])


def render_result_card(result, best_blade_name):
    if result is None:
        st.error("Selle kettaga detail ei mahu või ketta max paksus ei luba.")
        return

    st.success("Soovitatud variant" if result["blade"]["blade"] == best_blade_name else "Alternatiiv")
    st.subheader(result["blade"]["blade"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Avatud plaate", f"{result['opened_sheet_count']} tk")
    c2.metric("Valemi aeg", sec_to_minsec(result["total_sec"]))
    c3.metric("ML tegelik aeg", sec_to_minsec(result.get("ml_predicted_actual_time_sec")))

    c4, c5 = st.columns(2)
    c4.metric("Detailide pind + saetee kadu", f"{result['consumed_area_m2']:.2f} m²")
    c5.metric("Kasutatav jääk", f"{result['usable_offcut_area_m2']:.2f} m²")

    st.caption(result["blade_reason"])

    rows = [
        ["Sisestatud detail", f"{fmt(result['input_detail_width_mm'])} x {fmt(result['input_detail_length_mm'])} mm"],
        ["Arvutuses kasutatud detail", f"{fmt(result['detail_width_mm'])} x {fmt(result['detail_length_mm'])} mm"],
        ["Pööratud", "Jah" if result["rotated"] else "Ei"],
        ["Ääretrimmi arvestus", "Jah" if result["trim_edges"] else "Ei"],
        ["Ühest plaadist", f"{result['pieces_per_sheet']} detaili"],
        ["Laiuses", f"{result['across']} tk"],
        ["Pikkuses", f"{result['along']} tk"],
        ["Täismustriga plaate", f"{result['full_pattern_count']} tk"],
        ["Osalisi plaate", f"{result['partial_pattern_count']} tk"],
        ["Viimasel osalisel plaadil", f"{result['partial_piece_count']} detaili"],
        ["Osalise plaadi paigutus", f"{result['partial_cols']} veergu x {result['partial_rows']} rida" if result["partial_piece_count"] > 0 else "-"],
        ["Detailide netopind", f"{result['net_detail_area_m2']:.2f} m²"],
        ["Saetee kadu", f"{result['kerf_area_m2']:.2f} m²"],
        ["Teoreetiline jääk", f"{result['theoretical_offcut_area_m2']:.2f} m²"],
        ["Mittearvestatav jääk", f"{result['non_usable_offcut_area_m2']:.2f} m²"],
        ["Suurim kasutatav jääk", offcut_label(result["largest_usable_offcut"])],
        ["Ribilõikeid", f"{result['rip_cut_count']}"],
        ["Ristlõikeid", f"{result['cross_cut_count']}"],
        ["Lõikeid kokku", f"{result['total_cut_count']}"],
        ["Lõikeaeg", sec_to_minsec(result["cutting_time_sec"])],
        ["Setup aeg", sec_to_minsec(result["setup_sec"])],
        ["Käsitsemisaeg", sec_to_minsec(result["handling_sec"])],
    ]
    st.table(rows)

    fig = draw_scheme(result)
    st.pyplot(fig)
    plt.close(fig)

    if result.get("warning"):
        st.warning(result["warning"])

    with st.expander("Jäägid selle variandi puhul"):
        if result["full_offcuts"]:
            st.write("Täismustriga plaadi jäägid:")
            for offcut in result["full_offcuts"]:
                st.write(f"- {offcut_label(offcut)}")
        if result["partial_offcuts"]:
            st.write("Osalise viimase plaadi jäägid:")
            for offcut in result["partial_offcuts"]:
                st.write(f"- {offcut_label(offcut)}")


def build_pending_save_row(best_result, actual_time_sec_num, rework_time_sec_num):
    return {
        "work_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "order_id": st.session_state.order_id,
        "operator": st.session_state.operator,
        "material": st.session_state.material,
        "machine_id": st.session_state.machine_id,
        "shift": st.session_state.shift,
        "thickness_mm": int(st.session_state.thickness_mm),
        "raw_width_mm": best_result["raw_width_mm"],
        "raw_length_mm": best_result["raw_length_mm"],
        "detail_width_mm": best_result["input_detail_width_mm"],
        "detail_length_mm": best_result["input_detail_length_mm"],
        "detail_count": int(best_result["detail_count"]),
        "calculator_recommended_blade": best_result["blade"]["blade"],
        "calculator_recommended_rotated": int(best_result["rotated"]),
        "actual_blade": best_result["blade"]["blade"],
        "actual_rotated": int(best_result["rotated"]),
        "operator_changed_recommendation": 0,
        "blade": best_result["blade"]["blade"],
        "rotated": int(best_result["rotated"]),
        "trim_edges": int(best_result["trim_edges"]),
        "opened_sheet_count": best_result["opened_sheet_count"],
        "pieces_per_sheet": best_result["pieces_per_sheet"],
        "rip_cut_count": best_result["rip_cut_count"],
        "cross_cut_count": best_result["cross_cut_count"],
        "total_cut_count": best_result["total_cut_count"],
        "kerf_mm": best_result["kerf_mm"],
        "estimated_time_sec": best_result["total_sec"],
        "actual_time_sec": actual_time_sec_num,
        "usable_offcut_m2": best_result["usable_offcut_area_m2"],
        "non_usable_offcut_m2": best_result["non_usable_offcut_area_m2"],
        "was_scrap": int(st.session_state.was_scrap),
        "scrap_reason": st.session_state.scrap_reason,
        "rework_time_sec": rework_time_sec_num,
        "ml_predicted_actual_time_sec": best_result.get("ml_predicted_actual_time_sec"),
    }


st.title("🪚 Saetöö kalkulaator")
st.caption("Arvutus + töölogi + ajalugu + ML. Ajalukku salvestamine toimub käsitsi pärast arvutust.")

top1, top2 = st.columns([5, 1])
with top2:
    if st.button("Tühjenda kalkulaatori väljad", use_container_width=True):
        clear_calc_inputs()
        st.rerun()

tab_calc, tab_worklog, tab_history, tab_ml = st.tabs(["Kalkulaator", "Tehtud töö", "Ajalugu", "ML"])

with tab_worklog:
    st.subheader("Tehtud töö andmed")

    with st.form("worklog_form", enter_to_submit=False):
        wl1, wl2 = st.columns(2)

        with wl1:
            order_id = st.text_input("Tellimuse / töö number", value=st.session_state.order_id, placeholder="Nt T-240426-01")
            operator = st.text_input("Operaator", value=st.session_state.operator, placeholder="Nimi")
            material = st.text_input("Materjal", value=st.session_state.material, placeholder="Nt PE1000")
            machine_id = st.text_input("Masin", value=st.session_state.machine_id, placeholder="Nt Saag-1")

        with wl2:
            shift = st.text_input("Vahetus", value=st.session_state.shift, placeholder="Nt hommik")
            actual_time_min = st.text_input("Tegelik tööaeg minutites", value=st.session_state.actual_time_min, placeholder="Nt 20")
            was_scrap = st.checkbox("Tekkis praak / ümbertöö", value=st.session_state.was_scrap)
            scrap_reason = st.text_input("Praagi põhjus", value=st.session_state.scrap_reason, placeholder="Nt mõõduviga")
            rework_time_min = st.text_input("Ümbertöö aeg minutites", value=st.session_state.rework_time_min, placeholder="Nt 5")

        save_worklog = st.form_submit_button("Uuenda tööandmed", use_container_width=True)

    if save_worklog:
        st.session_state.order_id = order_id
        st.session_state.operator = operator
        st.session_state.material = material
        st.session_state.machine_id = machine_id
        st.session_state.shift = shift
        st.session_state.actual_time_min = actual_time_min
        st.session_state.was_scrap = was_scrap
        st.session_state.scrap_reason = scrap_reason
        st.session_state.rework_time_min = rework_time_min
        st.session_state.pending_save_row = None
        st.success("Tööandmed uuendatud.")

    if st.button("Tühjenda töölogi väljad", use_container_width=True):
        clear_worklog_inputs()
        st.rerun()

with tab_history:
    st.subheader("Ajalugu")

    uploaded = st.file_uploader("Laadi ajaloo CSV", type=["csv"], key="history_upload")
    if uploaded is not None:
        try:
            st.session_state.history_df = pd.read_csv(uploaded)
            st.success("Ajalugu laaditud sessiooni vaatamiseks.")
        except Exception:
            st.error("CSV laadimine ebaõnnestus.")

    history_df = st.session_state.history_df if not st.session_state.history_df.empty else load_history()
    st.write(f"Ajaloo ridu: {len(history_df)}")

    if not history_df.empty:
        st.dataframe(history_df.tail(30), use_container_width=True)
        st.download_button(
            "Laadi ajalugu alla CSV-na",
            data=history_df.to_csv(index=False).encode("utf-8"),
            file_name="saetoo_ajalugu.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_ml:
    st.subheader("ML prognoos")

    model, feature_cols, mae, n_rows = get_trained_model()

    if not SKLEARN_AVAILABLE:
        st.error("scikit-learn ei ole paigaldatud. Paigalda: pip install scikit-learn")
    elif model is None:
        st.info(f"ML mudelit pole veel võimalik kasutada. Õpperidu: {n_rows}. Vajalik vähemalt {ML_MIN_ROWS_TO_TRAIN}.")
    else:
        st.success(f"ML mudel on treenitud. Õpperidu: {n_rows}.")
        st.write("Kasutatud tunnused:", ", ".join(feature_cols))
        if mae is not None:
            st.metric("Mudeli keskmine viga (MAE)", sec_to_minsec(mae))
        else:
            st.info("MAE kuvatakse siis, kui ridu on vähemalt 50.")

        if n_rows >= ML_MIN_ROWS_TO_DECIDE and (mae is None or mae <= ML_MAX_ACCEPTABLE_MAE_SEC):
            st.success("ML võib osaleda soovituse valikus.")
        else:
            st.warning("ML prognoosi kuvatakse, kuid otsuse valik jääb reeglipõhiseks.")

    history_for_plot = load_history()
    if not history_for_plot.empty and {"estimated_time_sec", "actual_time_sec"}.issubset(history_for_plot.columns):
        plot_df = history_for_plot.copy()
        plot_df["estimated_time_sec"] = pd.to_numeric(plot_df["estimated_time_sec"], errors="coerce")
        plot_df["actual_time_sec"] = pd.to_numeric(plot_df["actual_time_sec"], errors="coerce")
        plot_df = plot_df.dropna(subset=["estimated_time_sec", "actual_time_sec"])

        if not plot_df.empty:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.scatter(plot_df["estimated_time_sec"] / 60, plot_df["actual_time_sec"] / 60, alpha=0.65)
            lim = max(plot_df["estimated_time_sec"].max(), plot_df["actual_time_sec"].max()) / 60
            ax.plot([0, lim], [0, lim])
            ax.set_title("Valemiga arvutatud aeg vs tegelik aeg")
            ax.set_xlabel("Valemiga aeg, min")
            ax.set_ylabel("Tegelik aeg, min")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            plt.close(fig)

with tab_calc:
    with st.form("calc_form", enter_to_submit=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            thickness_mm = st.selectbox(
                "Paksus mm",
                THICKNESS_OPTIONS_MM,
                index=THICKNESS_OPTIONS_MM.index(int(st.session_state.thickness_mm)),
            )
        with col2:
            raw_width_mm = st.text_input("Tooriku laius mm", value=st.session_state.raw_width_mm, placeholder="Nt 1000")
        with col3:
            raw_length_mm = st.text_input("Tooriku pikkus mm", value=st.session_state.raw_length_mm, placeholder="Nt 2000")

        col4, col5 = st.columns(2)
        with col4:
            detail_width_mm = st.text_input("Detaili laius mm", value=st.session_state.detail_width_mm, placeholder="Nt 95")
        with col5:
            detail_length_mm = st.text_input("Detaili pikkus mm", value=st.session_state.detail_length_mm, placeholder="Nt 300")

        detail_count = st.text_input("Detailide arv", value=st.session_state.detail_count, placeholder="Nt 20")
        trim_edges = st.checkbox("Arvesta ääretrimmi / väliste eralduslõigetega", value=st.session_state.trim_edges)

        submitted = st.form_submit_button("Arvuta", use_container_width=True)

    if not submitted and not st.session_state.pending_save_row:
        st.info("Sisesta andmed ja vajuta Arvuta.")

    if submitted:
        try:
            raw_width_mm = parse_float_text(raw_width_mm)
            raw_length_mm = parse_float_text(raw_length_mm)
            detail_width_mm = parse_float_text(detail_width_mm)
            detail_length_mm = parse_float_text(detail_length_mm)
            detail_count = int(str(detail_count).strip())
        except ValueError:
            st.error("Palun sisesta kõik kalkulaatori väljad korrektselt numbritena.")
            st.stop()

        st.session_state.thickness_mm = int(thickness_mm)
        st.session_state.raw_width_mm = str(raw_width_mm)
        st.session_state.raw_length_mm = str(raw_length_mm)
        st.session_state.detail_width_mm = str(detail_width_mm)
        st.session_state.detail_length_mm = str(detail_length_mm)
        st.session_state.detail_count = str(detail_count)
        st.session_state.trim_edges = bool(trim_edges)
        st.session_state.pending_save_row = None

        error = validate_common(
            int(thickness_mm),
            raw_length_mm,
            raw_width_mm,
            detail_length_mm,
            detail_width_mm,
            int(detail_count),
        )
        if error:
            st.error(error)
            st.stop()

        results = [
            build_best_result_for_blade(
                blade,
                int(thickness_mm),
                raw_width_mm,
                raw_length_mm,
                detail_width_mm,
                detail_length_mm,
                int(detail_count),
                bool(trim_edges),
            )
            for blade in BLADES
        ]

        model, feature_cols, mae, n_rows = get_trained_model()

        if model is not None:
            for r in results:
                if r is not None:
                    r["ml_predicted_actual_time_sec"] = predict_result_time(
                        model, feature_cols, r, thickness_mm
                    )

        ml_can_decide = (
            model is not None
            and n_rows >= ML_MIN_ROWS_TO_DECIDE
            and (mae is None or mae <= ML_MAX_ACCEPTABLE_MAE_SEC)
        )

        if ml_can_decide:
            best_result = choose_best_result_ml(results)
            decision_mode = "ML-toega soovitus"
        else:
            best_result = choose_best_result(results)
            decision_mode = "Reeglipõhine soovitus"

        if best_result is None:
            st.error("Detail ei mahu antud toorikusse või ketta max paksus ei luba kummagi variandi kasutamist.")
            st.stop()

        add_blade_reasons(results, best_result)
        st.session_state.last_results = results
        st.session_state.best_result = best_result

        st.success(
            f"{decision_mode}: {best_result['blade']['blade']} | avatud plaate {best_result['opened_sheet_count']} tk | "
            f"valemi aeg {sec_to_minsec(best_result['total_sec'])}"
            + (
                f" | ML aeg {sec_to_minsec(best_result['ml_predicted_actual_time_sec'])}"
                if best_result.get("ml_predicted_actual_time_sec") is not None
                else ""
            )
        )

        if model is not None:
            if mae is not None:
                st.info(f"ML info: õpperidu {n_rows}, MAE {sec_to_minsec(mae)}.")
            else:
                st.info(f"ML treenitud, kuid MAE veel puudub. Õpperidu {n_rows}.")
        else:
            st.info(f"ML ei ole veel aktiivne. Õpperidu {n_rows}, vajalik vähemalt {ML_MIN_ROWS_TO_TRAIN}.")

        left, right = st.columns(2)
        with left:
            render_result_card(results[0], best_result["blade"]["blade"])
        with right:
            render_result_card(results[1], best_result["blade"]["blade"])

        actual_time_sec_num = None
        rework_time_sec_num = 0.0

        if str(st.session_state.actual_time_min).strip():
            try:
                actual_time_sec_num = parse_float_text(st.session_state.actual_time_min) * 60
            except ValueError:
                st.warning("Tegelik tööaeg minutites ei ole korrektne number.")

        if str(st.session_state.rework_time_min).strip():
            try:
                rework_time_sec_num = parse_float_text(st.session_state.rework_time_min) * 60
            except ValueError:
                st.warning("Ümbertöö aeg minutites ei ole korrektne number. Kasutatakse 0.")
                rework_time_sec_num = 0.0

        if actual_time_sec_num is not None:
            st.session_state.pending_save_row = build_pending_save_row(
                best_result,
                actual_time_sec_num,
                rework_time_sec_num,
            )

        with st.expander("Arvestuse loogika"):
            st.write("- Mõlemale kettale arvutatakse parim orientatsioon.")
            st.write("- Kui ML mudel on piisavalt treenitud ja vea tase on mõistlik, kasutatakse valikul ML prognoosi.")
            st.write("- Kui ML pole veel usaldusväärne, kasutatakse reeglipõhist valikut.")
            st.write("- Tegelik töö salvestatakse alles käsitsi nupuga, et vältida topeltsalvestust.")
            st.write("- Tegelik aeg sisestatakse minutites, aga ajalukku salvestatakse sekundites.")
            st.write("- Kasutatav jääk peab olema vähemalt 150 mm kitsamast küljest ja 1000 mm pikemast küljest ning vähemalt 0.15 m².")

    if st.session_state.pending_save_row is not None:
        st.subheader("Tehtud töö salvestus")
        st.write(
            f"Valmis salvestamiseks: töö/tellimus "
            f"**{st.session_state.pending_save_row.get('order_id') or st.session_state.pending_save_row.get('work_id')}**, "
            f"tegelik aeg {sec_to_minsec(st.session_state.pending_save_row['actual_time_sec'])}."
        )
        if st.button("Salvesta tehtud töö ajalukku", use_container_width=True):
            save_history_row(st.session_state.pending_save_row)
            st.session_state.pending_save_row = None
            st.success("Töö salvestati ajalukku.")
            st.rerun()
    elif submitted:
        st.subheader("Tehtud töö salvestus")
        st.warning("Ajalukku salvestamiseks sisesta 'Tehtud töö' tabis tegelik tööaeg minutites ja arvuta uuesti.")
