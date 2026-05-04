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
        'cross_time_sec': cross_forward_time_sec,
        'forward_cutting_time_sec': forward_cutting_time_sec,
        'return_travel_time_sec': return_travel_time_sec,
        'cutting_time_sec': cutting_time_sec,
        'setup_sec': setup_sec,
        'handling_sec': handling_sec,
        'total_sec': total_sec,
        'kerf_mm': kerf_mm,
        'scheme_used_width_mm': partial_used_width_mm if partial_piece_count > 0 else full_used_width_mm,
        'scheme_used_length_mm': partial_used_length_mm if partial_piece_count > 0 else full_used_length_mm,
        'scheme_piece_count': partial_piece_count if partial_piece_count > 0 else pieces_per_sheet,
        'hourly_rate_eur': hourly_rate_eur,
        'material_price_m2_eur': material_price_m2_eur,
        'material_billable_area_m2': material_billable_area_m2,
        'estimated_work_cost_eur': estimated_work_cost_eur,
        'material_cost_eur': material_cost_eur,
        'total_estimated_cost_eur': total_estimated_cost_eur,
        'warning': 'Hoiatus: alla 20 mm detaili/riba puhul võivad masina käpad segada.' if piece_w < 20 else None,
        'ml_predicted_actual_time_sec': None,
    }


def result_sort_key(result):
    return (
        result['opened_sheet_count'],
        result['total_estimated_cost_eur'],
        result['total_sec'],
        result['total_cut_count'],
        -result['usable_offcut_area_m2'],
        result['non_usable_offcut_area_m2'],
        0 if result['blade']['is_default'] else 1,
    )


def choose_best_orientation_result(results):
    valid = [r for r in results if r is not None]
    return min(valid, key=result_sort_key) if valid else None


def choose_best_result(results):
    valid = [r for r in results if r is not None]
    if not valid:
        return None

    large = next((r for r in valid if r['blade']['is_default']), None)
    small = next((r for r in valid if not r['blade']['is_default']), None)

    if large is None:
        return small
    if small is None:
        return large

    if small['opened_sheet_count'] < large['opened_sheet_count']:
        return small
    if large['opened_sheet_count'] < small['opened_sheet_count']:
        return large

    cost_saving = large['total_estimated_cost_eur'] - small['total_estimated_cost_eur']
    time_saving = large['total_sec'] - small['total_sec']
    offcut_gain = small['usable_offcut_area_m2'] - large['usable_offcut_area_m2']

    if (
        cost_saving >= MIN_SMALL_BLADE_COST_SAVING_EUR
        or time_saving >= MIN_SMALL_BLADE_TIME_SAVING_SEC
        or offcut_gain >= MIN_SMALL_BLADE_USABLE_OFFCUT_GAIN_M2
    ):
        return small

    return large


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
    )

    rotated = build_orientation_result(
        blade,
        thickness_mm,
        raw_width_mm,
        raw_length_mm,
        detail_length_mm,
        detail_width_mm,
        detail_count,
        trim_edges,
    )

    if normal is not None:
        normal['rotated'] = False
        normal['input_detail_width_mm'] = detail_width_mm
        normal['input_detail_length_mm'] = detail_length_mm
        normal['detail_width_mm'] = detail_width_mm
        normal['detail_length_mm'] = detail_length_mm

    if rotated is not None:
        rotated['rotated'] = True
        rotated['input_detail_width_mm'] = detail_width_mm
        rotated['input_detail_length_mm'] = detail_length_mm
        rotated['detail_width_mm'] = detail_length_mm
        rotated['detail_length_mm'] = detail_width_mm

    return choose_best_orientation_result([normal, rotated])


def add_blade_reasons(results, best):
    for r in results:
        if r is None:
            continue

        prefix = 'Soovitatud variant' if r is best else 'Alternatiiv'
        orientation = 'pööratud detailiga' if r.get('rotated') else 'pööramata detailiga'
        trim_text = 'ääretrimmi arvestusega' if r['trim_edges'] else 'ilma ääretrimmi arvestuseta'

        r['blade_reason'] = (
            f"{prefix}: {orientation}, {trim_text}, avatud plaate {r['opened_sheet_count']} tk, "
            f"lõikeid kokku {r['total_cut_count']}, koguaeg {sec_to_minsec(r['total_sec'])}, "
            f"hinnanguline kogukulu {r['total_estimated_cost_eur']:.2f} €."
        )


def offcut_label(offcut):
    if offcut is None:
        return 'Puudub'

    return (
        f"{offcut['name']}: {fmt(offcut['width_mm'])} x {fmt(offcut['length_mm'])} mm, "
        f"{offcut['area_m2']:.2f} m², "
        f"{'kasutatav' if offcut['usable'] else 'mittearvestatav'}"
    )


def draw_scheme(result):
    piece_w = float(result['detail_width_mm'])
    piece_h = float(result['detail_length_mm'])
    kerf = float(result['kerf_mm'])
    scheme_w = max(float(result.get('scheme_used_width_mm', piece_w)), piece_w)
    scheme_l = max(float(result.get('scheme_used_length_mm', piece_h)), piece_h)
    total_pieces = int(result.get('scheme_piece_count', 0))

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_xlim(0, scheme_w)
    ax.set_ylim(scheme_l, 0)
    ax.set_aspect('equal', adjustable='box')

    ax.add_patch(
        Rectangle(
            (0, 0),
            scheme_w,
            scheme_l,
            facecolor=COLOR_SHEET,
            edgecolor='black',
            linewidth=2,
        )
    )

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

    ax.set_title('Lõikeskeem')
    ax.set_xlabel('Laius mm')
    ax.set_ylabel('Pikkus mm')
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
    file_exists = HISTORY_FILE.exists()
    df.to_csv(HISTORY_FILE, mode='a', header=not file_exists, index=False)
    st.cache_data.clear()
    st.cache_resource.clear()


def build_history_row(best_result):
    actual_time_sec = (
        parse_float_text(st.session_state.actual_time_min, 0.0) * 60
        if str(st.session_state.actual_time_min).strip()
        else None
    )
    rework_time_sec = (
        parse_float_text(st.session_state.rework_time_min, 0.0) * 60
        if str(st.session_state.rework_time_min).strip()
        else 0.0
    )

    return {
        'app_version': APP_VERSION,
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'order_id': st.session_state.order_id,
        'operator': st.session_state.operator,
        'material': st.session_state.material,
        'machine_id': st.session_state.machine_id,
        'shift': st.session_state.shift,
        'thickness_mm': st.session_state.thickness_mm,
        'raw_width_mm': best_result['raw_width_mm'],
        'raw_length_mm': best_result['raw_length_mm'],
        'detail_width_mm': best_result['input_detail_width_mm'],
        'detail_length_mm': best_result['input_detail_length_mm'],
        'detail_count': best_result['detail_count'],
        'blade': best_result['blade']['blade'],
        'rotated': int(best_result.get('rotated', False)),
        'trim_edges': int(best_result['trim_edges']),
        'opened_sheet_count': best_result['opened_sheet_count'],
        'pieces_per_sheet': best_result['pieces_per_sheet'],
        'longitudinal_cut_count': best_result['longitudinal_cut_count'],
        'cross_cut_count': best_result['cross_cut_count'],
        'total_cut_count': best_result['total_cut_count'],
        'kerf_mm': best_result['kerf_mm'],
        'estimated_time_sec': best_result['total_sec'],
        'actual_time_sec': actual_time_sec,
        'usable_offcut_m2': best_result['usable_offcut_area_m2'],
        'non_usable_offcut_m2': best_result['non_usable_offcut_area_m2'],
        'was_scrap': int(st.session_state.was_scrap),
        'scrap_reason': st.session_state.scrap_reason,
        'rework_time_sec': rework_time_sec,
    }
def save_history_row(row):
    df = pd.DataFrame([row])
    file_exists = HISTORY_FILE.exists()
    df.to_csv(HISTORY_FILE, mode='a', header=not file_exists, index=False)
    st.cache_data.clear()
    st.cache_resource.clear()


def build_history_row(best_result):
    actual_time_sec = (
        parse_float_text(st.session_state.actual_time_min, 0.0) * 60
        if str(st.session_state.actual_time_min).strip()
        else None
    )
    rework_time_sec = (
        parse_float_text(st.session_state.rework_time_min, 0.0) * 60
        if str(st.session_state.rework_time_min).strip()
        else 0.0
    )

    return {
        'app_version': APP_VERSION,
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'order_id': st.session_state.order_id,
        'operator': st.session_state.operator,
        'material': st.session_state.material,
        'machine_id': st.session_state.machine_id,
        'shift': st.session_state.shift,
        'thickness_mm': st.session_state.thickness_mm,
        'raw_width_mm': best_result['raw_width_mm'],
        'raw_length_mm': best_result['raw_length_mm'],
        'detail_width_mm': best_result['input_detail_width_mm'],
        'detail_length_mm': best_result['input_detail_length_mm'],
        'detail_count': best_result['detail_count'],
        'blade': best_result['blade']['blade'],
        'rotated': int(best_result.get('rotated', False)),
        'trim_edges': int(best_result['trim_edges']),
        'opened_sheet_count': best_result['opened_sheet_count'],
        'pieces_per_sheet': best_result['pieces_per_sheet'],
        'longitudinal_cut_count': best_result['longitudinal_cut_count'],
        'cross_cut_count': best_result['cross_cut_count'],
        'total_cut_count': best_result['total_cut_count'],
        'kerf_mm': best_result['kerf_mm'],
        'estimated_time_sec': best_result['total_sec'],
        'actual_time_sec': actual_time_sec,
        'usable_offcut_m2': best_result['usable_offcut_area_m2'],
        'non_usable_offcut_m2': best_result['non_usable_offcut_area_m2'],
        'was_scrap': int(st.session_state.was_scrap),
        'scrap_reason': st.session_state.scrap_reason,
        'rework_time_sec': rework_time_sec,
    }


def render_result_card(result, best_blade_name):
    if result is None:
        st.error('Selle kettaga detail ei mahu või ketta max paksus ei luba.')
        return

    is_best = result['blade']['blade'] == best_blade_name

    st.success('Soovitatud variant' if is_best else 'Alternatiiv')
    st.subheader(result['blade']['blade'])

    c1, c2, c3 = st.columns(3)
    c1.metric('Avatud plaate', f"{result['opened_sheet_count']} tk")
    c2.metric('Koguaeg', sec_to_minsec(result['total_sec']))
    c3.metric('Kogukulu', f"{result['total_estimated_cost_eur']:.2f} €")

    c4, c5 = st.columns(2)
    c4.metric('Detailide pind + saetee kadu', f"{result['consumed_area_m2']:.2f} m²")
    c5.metric('Kasutatav jääk', f"{result['usable_offcut_area_m2']:.2f} m²")

    st.caption(result.get('blade_reason', ''))

    rows = [
        ['Sisestatud detail', f"{fmt(result['input_detail_width_mm'])} x {fmt(result['input_detail_length_mm'])} mm"],
        ['Arvutuses kasutatud detail', f"{fmt(result['detail_width_mm'])} x {fmt(result['detail_length_mm'])} mm"],
        ['Pööratud', 'Jah' if result.get('rotated') else 'Ei'],
        ['Ääretrimmi arvestus', 'Jah' if result['trim_edges'] else 'Ei'],
        ['Ühest plaadist', f"{result['pieces_per_sheet']} detaili"],
        ['Laiuses', f"{result['across']} tk"],
        ['Pikkuses', f"{result['along']} tk"],
        ['Täisplaate', f"{result['full_sheet_count']} tk"],
        ['Osalisi plaate', f"{result['partial_sheet_count']} tk"],
        ['Saetee kadu', f"{result['kerf_area_m2']:.2f} m²"],
        ['Mittearvestatav jääk', f"{result['non_usable_offcut_area_m2']:.2f} m²"],
        ['Suurim kasutatav jääk', offcut_label(result['largest_usable_offcut'])],
        ['Pikilõikeid', result['longitudinal_cut_count']],
        ['Ristlõikeid', result['cross_cut_count']],
        ['Lõikeid kokku', result['total_cut_count']],
        ['Pikilõike aeg', sec_to_minsec(result['longitudinal_time_sec'])],
        ['Ristlõike aeg', sec_to_minsec(result['cross_time_sec'])],
        ['Setup aeg', sec_to_minsec(result['setup_sec'])],
        ['Käsitsemisaeg', sec_to_minsec(result['handling_sec'])],
        ['Materjalikulu pind', f"{result['material_billable_area_m2']:.2f} m²"],
        ['Töö maksumus', f"{result['estimated_work_cost_eur']:.2f} €"],
        ['Materjali maksumus', f"{result['material_cost_eur']:.2f} €"],
    ]

    st.table(pd.DataFrame(rows, columns=['Näitaja', 'Väärtus']))

    fig = draw_scheme(result)
    st.pyplot(fig)
    plt.close(fig)

    if result.get('warning'):
        st.warning(result['warning'])


def main():
    st.title('Saetöö kalkulaator')
    st.caption('Täiesti uus nullist koostatud Streamlit-rakendus saetöö planeerimiseks.')

    history_df = load_history()

    with st.sidebar:
        st.header('Sisend')
        thickness_mm = st.selectbox(
            'Paksus (mm)',
            THICKNESS_OPTIONS_MM,
            index=THICKNESS_OPTIONS_MM.index(st.session_state.thickness_mm),
            key='thickness_mm'
        )
        raw_width_mm = st.number_input(
            'Tooriku laius (mm)',
            min_value=1.0,
            max_value=MAX_WIDTH_MM,
            value=float(st.session_state.raw_width_mm),
            key='raw_width_mm'
        )
        raw_length_mm = st.number_input(
            'Tooriku pikkus (mm)',
            min_value=1.0,
            max_value=MAX_LENGTH_MM,
            value=float(st.session_state.raw_length_mm),
            key='raw_length_mm'
        )
        detail_width_mm = st.number_input(
            'Detaili laius (mm)',
            min_value=1.0,
            value=float(st.session_state.detail_width_mm),
            key='detail_width_mm'
        )
        detail_length_mm = st.number_input(
            'Detaili pikkus (mm)',
            min_value=1.0,
            value=float(st.session_state.detail_length_mm),
            key='detail_length_mm'
        )
        detail_count = st.number_input(
            'Detailide arv',
            min_value=1,
            value=int(st.session_state.detail_count),
            key='detail_count'
        )
        trim_edges = st.checkbox(
            'Arvesta ääretrimmi',
            value=st.session_state.trim_edges,
            key='trim_edges'
        )
        st.text_input('Tunnihind (€)', key='hourly_rate_eur')
        st.text_input('Materjali hind €/m²', key='material_price_m2_eur')
        calculate = st.button('Arvuta', type='primary')

    tab1, tab2, tab3 = st.tabs(['Arvutus', 'Töölogi', 'Ajalugu'])

    if calculate:
        error = validate_inputs(
            thickness_mm,
            raw_width_mm,
            raw_length_mm,
            detail_width_mm,
            detail_length_mm,
            detail_count
        )

        if error:
            st.error(error)
        else:
            results = [
                build_best_result_for_blade(
                    blade,
                    thickness_mm,
                    raw_width_mm,
                    raw_length_mm,
                    detail_width_mm,
                    detail_length_mm,
                    detail_count,
                    trim_edges,
                )
                for blade in BLADES
            ]

            best = choose_best_result(results)
            add_blade_reasons(results, best)
            st.session_state.last_results = results
            st.session_state.best_result = best

    with tab1:
        if st.session_state.last_results:
            best_blade_name = (
                st.session_state.best_result['blade']['blade']
                if st.session_state.best_result
                else ''
            )
            cols = st.columns(len(st.session_state.last_results))
            for col, result in zip(cols, st.session_state.last_results):
                with col:
                    render_result_card(result, best_blade_name)
        else:
            st.info('Sisesta andmed ja vajuta Arvuta.')

    with tab2:
        st.subheader('Töölogi')
        st.text_input('Tellimus', key='order_id')
        st.text_input('Operaator', key='operator')
        st.text_input('Materjal', key='material')
        st.text_input('Masin', key='machine_id')
        st.text_input('Vahetus', key='shift')
        st.text_input('Tegelik aeg (min)', key='actual_time_min')
        st.checkbox('Kas praak', key='was_scrap')
        st.text_input('Praagi põhjus', key='scrap_reason')
        st.text_input('Ümbertöö aeg (min)', key='rework_time_min')

        if st.button('Salvesta töölogi'):
            if not st.session_state.best_result:
                st.error('Kõigepealt arvuta tulemus.')
            else:
                row = build_history_row(st.session_state.best_result)
                save_history_row(row)
                st.success('Töölogi salvestatud.')

    with tab3:
        st.subheader('Ajalugu')
        if history_df.empty:
            st.info('Ajalugu puudub.')
        else:
            st.dataframe(history_df, use_container_width=True)


if __name__ == '__main__':
    main()
