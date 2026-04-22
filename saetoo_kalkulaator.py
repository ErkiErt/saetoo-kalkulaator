import math
import streamlit as st

st.set_page_config(page_title="Saetöö kalkulaator", page_icon="🪚", layout="wide")

MAX_LENGTH_MM = 3050.0
MAX_WIDTH_MM = 2050.0
LAST_UPDATED = "2026-04-22"

LARGE_BLADE = {"blade": "5.6 mm", "kerf_mm": 5.6, "max_stack_mm": 80.0, "is_default": True}
SMALL_BLADE = {"blade": "3.5 mm", "kerf_mm": 3.5, "max_stack_mm": 30.0, "is_default": False}

STANDARD_SHEETS = {
    "Tavaplaat": [(1000.0, 2000.0), (1000.0, 3000.0), (1250.0, 3000.0), (1500.0, 3000.0)],
    "PC": [(2000.0, 3000.0)],
    "PMMA": [(2000.0, 3000.0)],
}

DEFAULTS = {
    "material_type": "Tavaplaat",
    "sheet_index": 0,
    "thickness_mm": 20.0,
    "use_custom_size": False,
    "raw_width_mm": 1000.0,
    "raw_length_mm": 2000.0,
    "detail_length_mm": 300.0,
    "detail_width_mm": 95.0,
    "detail_count": 20,
    "strip_width_mm": 95.0,
    "show_details": True,
    "last_result": None,
    "last_alternative": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def load_example():
    st.session_state.material_type = "Tavaplaat"
    st.session_state.sheet_index = 0
    st.session_state.thickness_mm = 20.0
    st.session_state.use_custom_size = True
    st.session_state.raw_width_mm = 1005.0
    st.session_state.raw_length_mm = 2005.0
    st.session_state.strip_width_mm = 95.0
    st.session_state.detail_length_mm = 300.0
    st.session_state.detail_width_mm = 95.0
    st.session_state.detail_count = 20
    st.session_state.show_details = True


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
    minutes = int(seconds // 
