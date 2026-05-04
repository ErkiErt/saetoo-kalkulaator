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
APP_VERSION = "2026-05-04-new-build"

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
CUT_RETURN_FACTOR = 0.20

ML_MIN_ROWS_TO_TRAIN = 30
ML_MIN_ROWS_TO_DECIDE = 50
ML_MAX_ACCEPTABLE_MAE_SEC = 15 * 60
ML_MIN_FACTOR = 0.4
ML_MAX_FACTOR = 2.5

MIN_SMALL_BLADE_COST_SAVING_EUR = 5.0
MIN_SMALL_BLADE_TIME_SAVING_SEC = 10 * 60
MIN_SMALL_BLADE_USABLE_OFFCUT_GAIN_M2 = 0.15

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
    "raw_width_mm": 1250.0,
    "raw_length_mm": 2800.0,
    "detail_length_mm": 400.0,
    "detail_width_mm": 95.0,
    "detail_count": 20,
    "trim_edges": True,
    "hourly_rate_eur": "60",
    "material_price_m2_eur": "48",
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
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def parse_float_text(value, default=0.0):
    try:
        text = str(value).replace(',', '.').strip()
        if text == '':
            return default
        return float(text)
    except Exception:
        return default


def fmt(value):
    if value is None or pd.isna(value):
        return '-'
    try:
        value = float(value)
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    except Exception:
        return str(value)


def sec_to_minsec(seconds):
    if seconds is None or pd.isna(seconds):
        return '-'
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = round(seconds % 60)
    if hours > 0:
        return f"{hours} h {minutes} min {sec} sek"
    return f"{minutes} min {sec} sek"


def area_m2(width_mm, length_mm):
    return max(0.0, width_mm) * max(0.0, length_mm) / 1_000_000.0


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
