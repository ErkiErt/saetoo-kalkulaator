from pathlib import Path
code = r'''import math
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Saetöö kalkulaator", page_icon="🪚", layout="wide")

MAX_LENGTH_MM = 3050.0
MAX_WIDTH_MM = 2050.0
LAST_UPDATED = "2026-04-22"

LARGE_BLADE = {"blade": "5.6 mm", "kerf_mm": 5.6, "max_stack_mm": 80.0, "is_default": True}
SMALL_BLADE = {"blade": "3.5 mm", "kerf_mm": 3.5, "max_stack_mm": 30.0, "is_default": False}
BLADES = [LARGE_BLADE, SMALL_BLADE]

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
    "show_details": True,
    "last_results": None,
    "best_result": None,
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
    minutes = int(seconds // 60)
    sec = round(seconds % 60, 1)
    return f"{minutes} min {sec} sek"


def fmt(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(round(v, 2))


def material_area_m2(length_mm, width_mm, sheet_count):
    return 0 if sheet_count <= 0 else (length_mm / 1000.0) * (width_mm / 1000.0) * sheet_count


def single_sheet_area_m2(length_mm, width_mm):
    return (length_mm / 1000.0) * (width_mm / 1000.0)


def max_pieces_in_length(total_len_mm, piece_len_mm, kerf_mm):
    if total_len_mm <= 0 or piece_len_mm <= 0:
        return 0
    return max(0, math.floor((total_len_mm + kerf_mm) / (piece_len_mm + kerf_mm)))


def used_size_mm(piece_count, piece_size_mm, kerf_mm):
    if piece_count <= 0:
        return 0
    return piece_count * piece_size_mm + (piece_count - 1) * kerf_mm


def blade_switch_setup_sec(blade):
    return 0 if blade["is_default"] else 5 * 60


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
    if get_sec_per_meter(thickness_mm) is None:
        return "Paksuse vahemik peab olema 1 kuni 90 mm."
    return None


def evaluate_orientation(raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, kerf_mm):
    normal = {
        "detail_length_mm": detail_length_mm,
        "detail_width_mm": detail_width_mm,
        "rotated": False,
        "across": max_pieces_in_length(raw_width_mm, detail_width_mm, kerf_mm),
        "along": max_pieces_in_length(raw_length_mm, detail_length_mm, kerf_mm),
    }
    rotated = {
        "detail_length_mm": detail_width_mm,
        "detail_width_mm": detail_length_mm,
        "rotated": True,
        "across": max_pieces_in_length(raw_width_mm, detail_length_mm, kerf_mm),
        "along": max_pieces_in_length(raw_length_mm, detail_width_mm, kerf_mm),
    }
    normal["pieces_per_sheet"] = normal["across"] * normal["along"]
    rotated["pieces_per_sheet"] = rotated["across"] * rotated["along"]
    if rotated["pieces_per_sheet"] > normal["pieces_per_sheet"]:
        return rotated
    return normal


def choose_mode(raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, blade):
    orientation = evaluate_orientation(raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, blade["kerf_mm"])
    if orientation["pieces_per_sheet"] <= 0:
        return None
    if orientation["along"] == 1 and orientation["across"] >= 1:
        mode = "Ribastamine"
    elif orientation["along"] > 1 and orientation["across"] >= 1:
        mode = "Ribastamine + tükeldamine"
    else:
        mode = "Tooriku lõikus"
    orientation["mode"] = mode
    return orientation


def build_cut_scheme(lines):
    return "\n".join([f"{i}. {line}" for i, line in enumerate(lines, start=1)])


def make_result(blade, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count):
    decision = choose_mode(raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, blade)
    if decision is None:
        return None

    mode = decision["mode"]
    d_len = decision["detail_length_mm"]
    d_wid = decision["detail_width_mm"]
    rotated = decision["rotated"]
    across = decision["across"]
    along = decision["along"]
    pieces_per_sheet = decision["pieces_per_sheet"]
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    setup_sec = 20 * 60
    blade_setup_sec = blade_switch_setup_sec(blade)
    warning = "Hoiatus: alla 20 mm ribade puhul võivad masina käpad segada." if d_wid < 20 else None

    if mode == "Ribastamine":
        sheets_needed = math.ceil(detail_count / across)
        used_width = used_size_mm(across, d_wid, kerf)
        waste_width = raw_width_mm - used_width
        max_stack_sheets = max(1, int(blade["max_stack_mm"] // thickness_mm))
        stack_runs = math.ceil(sheets_needed / max_stack_sheets)
        cut_cycles = stack_runs * max(0, across - 1)
        cutting_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * cut_cycles
        total_sec = cutting_time_sec + setup_sec + blade_setup_sec
        explanation = f"Süsteem valis ribastamise, sest detail mahub laiusesse {across} ribana ja pikkusesse tükeldust ei ole vaja. Plaate on vaja {sheets_needed} tk ja materjalikulu on {material_area_m2(raw_length_mm, raw_width_mm, sheets_needed):.2f} m²."
        calc_steps = [
            f"Automaatne töörežiim: {mode}.",
            f"Orientatsioon {'pööratud' if rotated else 'algne'}.",
            f"Ribasid ühest plaadist = {across}.",
            f"Plaate vaja = lae({detail_count} / {across}) = {sheets_needed}.",
            f"Ribastamise seeriaid = {stack_runs}.",
        ]
        scheme = build_cut_scheme([
            f"Võta {sheets_needed} täisplaati mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lao korraga virna kuni {max_stack_sheets} plaati, selle töö jaoks on vaja {stack_runs} ribastamise seeriat.",
            f"Lõika igast virnast välja {across} täispikka riba laiusega {fmt(d_wid)} mm.",
            f"Ribalõikeid ühes seerias on {max(0, across - 1)}.",
            f"Jääk ühe plaadi laiuses on {fmt(waste_width)} mm.",
        ])
        return {
            "mode": mode,
            "orientation_rotated": rotated,
            "blade": blade,
            "raw_length_mm": raw_length_mm,
            "raw_width_mm": raw_width_mm,
            "detail_length_mm": d_len,
            "detail_width_mm": d_wid,
            "detail_count": detail_count,
            "pieces_per_sheet": across,
            "sheets_needed": sheets_needed,
            "used_width_mm": used_width,
            "waste_width_mm": waste_width,
            "cutting_time_sec": cutting_time_sec,
            "setup_sec": setup_sec,
            "blade_setup_sec": blade_setup_sec,
            "total_sec": total_sec,
            "material_m2": material_area_m2(raw_length_mm, raw_width_mm, sheets_needed),
            "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
            "warning": warning,
            "scheme": scheme,
            "calc_steps": calc_steps,
            "explanation": explanation,
        }

    sheets_needed = math.ceil(detail_count / pieces_per_sheet)
    used_width = used_size_mm(across, d_wid, kerf)
    used_length = used_size_mm(along, d_len, kerf)
    waste_width = raw_width_mm - used_width
    waste_length = raw_length_mm - used_length

    if mode == "Ribastamine + tükeldamine":
        max_stack_sheets = max(1, int(blade["max_stack_mm"] // thickness_mm))
        stack_runs = math.ceil(sheets_needed / max_stack_sheets)
        strip_cut_cycles = stack_runs * max(0, across - 1)
        total_strips = sheets_needed * across
        max_stack_strips = max(1, int(blade["max_stack_mm"] // thickness_mm))
        crosscut_runs = math.ceil(total_strips / max_stack_strips)
        crosscut_cycles = crosscut_runs * max(0, along - 1)
        strip_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * strip_cut_cycles
        crosscut_time_sec = (used_width / 1000.0) * sec_per_m * 2 * crosscut_cycles
        total_sec = strip_time_sec + crosscut_time_sec + setup_sec + blade_setup_sec
        explanation = f"Süsteem valis ribastamise + tükeldamise, sest detailist saab teha esmalt ribad ja siis lõigata need pikkusesse. Ühest toorikust saab {pieces_per_sheet} detaili, toorikuid on vaja {sheets_needed} tk."
        calc_steps = [
            f"Automaatne töörežiim: {mode}.",
            f"Orientatsioon {'pööratud' if rotated else 'algne'}.",
            f"Ribasid ühest plaadist = {across}.",
            f"Tükke ühest ribast = {along}.",
            f"Ühest toorikust tuleb {pieces_per_sheet} detaili.",
            f"Toorikuid vaja = lae({detail_count} / {pieces_per_sheet}) = {sheets_needed}.",
        ]
        scheme = build_cut_scheme([
            f"Võta {sheets_needed} täisplaati mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lao korraga virna kuni {max_stack_sheets} plaati. Ribastamise jaoks on vaja {stack_runs} seeriat.",
            f"Ribasta igast plaadist {across} riba laiusega {fmt(d_wid)} mm.",
            f"Seejärel tükelda ribad detailipikkuseks {fmt(d_len)} mm, ühest ribast saab {along} detaili.",
            f"Kokku saad ühest toorikust {pieces_per_sheet} detaili.",
            f"Jääk ühe tooriku kohta on {fmt(waste_width)} mm laiuses ja {fmt(waste_length)} mm pikkuses.",
        ])
        return {
            "mode": mode,
            "orientation_rotated": rotated,
            "blade": blade,
            "raw_length_mm": raw_length_mm,
            "raw_width_mm": raw_width_mm,
            "detail_length_mm": d_len,
            "detail_width_mm": d_wid,
            "detail_count": detail_count,
            "pieces_per_sheet": pieces_per_sheet,
            "sheets_needed": sheets_needed,
            "used_width_mm": used_width,
            "used_length_mm": used_length,
            "waste_width_mm": waste_width,
            "waste_length_mm": waste_length,
            "cutting_time_sec": strip_time_sec + crosscut_time_sec,
            "setup_sec": setup_sec,
            "blade_setup_sec": blade_setup_sec,
            "total_sec": total_sec,
            "material_m2": material_area_m2(raw_length_mm, raw_width_mm, sheets_needed),
            "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
            "warning": warning,
            "scheme": scheme,
            "calc_steps": calc_steps,
            "explanation": explanation,
        }

    total_cut_cycles = (max(0, across - 1) + across * max(0, along - 1)) * sheets_needed
    cutting_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * total_cut_cycles
    total_sec = cutting_time_sec + setup_sec + blade_setup_sec
    explanation = f"Süsteem valis tooriku lõikuse, sest detaili paigutus nõuab jaotust nii laiusesse kui pikkusesse otse plaadist. Ühest toorikust saab {pieces_per_sheet} detaili."
    calc_steps = [
        f"Automaatne töörežiim: Tooriku lõikus.",
        f"Orientatsioon {'pööratud' if rotated else 'algne'}.",
        f"Laiuses mahub {across} detaili.",
        f"Pikkuses mahub {along} detaili.",
        f"Ühest toorikust tuleb {pieces_per_sheet} detaili.",
        f"Toorikuid vaja = lae({detail_count} / {pieces_per_sheet}) = {sheets_needed}.",
    ]
    scheme = build_cut_scheme([
        f"Võta {sheets_needed} toorikut mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
        f"Lõika kõigepealt laiusesse {across} rida detaililaiusega {fmt(d_wid)} mm.",
        f"Seejärel lõika pikkusesse {along} jaotust detailipikkusega {fmt(d_len)} mm.",
        f"Ühest toorikust saad kokku {pieces_per_sheet} detaili.",
        f"Jääk ühe tooriku kohta on {fmt(waste_width)} mm laiuses ja {fmt(waste_length)} mm pikkuses.",
    ])
    return {
        "mode": "Tooriku lõikus",
        "orientation_rotated": rotated,
        "blade": blade,
        "raw_length_mm": raw_length_mm,
        "raw_width_mm": raw_width_mm,
        "detail_length_mm": d_len,
        "detail_width_mm": d_wid,
        "detail_count": detail_count,
        "pieces_per_sheet": pieces_per_sheet,
        "sheets_needed": sheets_needed,
        "used_width_mm": used_width,
        "used_length_mm": used_length,
        "waste_width_mm": waste_width,
        "waste_length_mm": waste_length,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "blade_setup_sec": blade_setup_sec,
        "total_sec": total_sec,
        "material_m2": material_area_m2(raw_length_mm, raw_width_mm, sheets_needed),
        "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
        "warning": warning,
        "scheme": scheme,
        "calc_steps": calc_steps,
        "explanation": explanation,
    }


def choose_best_result(results):
    valid = [r for r in results if r is not None]
    if not valid:
        return None
    return min(
        valid,
        key=lambda r: (
            r["sheets_needed"],
            r["material_m2"],
            r["total_sec"],
            0 if r["blade"]["is_default"] else 1,
        ),
    )


def add_blade_reasons(results, best):
    for r in results:
        if r is None:
            continue
        if r is best:
            r["blade_reason"] = (
                f"Soovitatud variant, sest vaja on {r['sheets_needed']} toorikut, materjalikulu on {r['material_m2']:.2f} m² "
                f"ja koguaeg on {sec_to_minsec(r['total_sec'])}."
            )
        else:
            r["blade_reason"] = (
                f"Alternatiiv. Selle variandi tulemus on {r['sheets_needed']} toorikut, {r['material_m2']:.2f} m² "
                f"ja {sec_to_minsec(r['total_sec'])}."
            )


def draw_scheme(result):
    fig, ax = plt.subplots(figsize=(7, 6))
    scale = 10
    ax.set_xlim(0, result["raw_width_mm"] / scale)
    ax.set_ylim(0, result["raw_length_mm"] / scale)
    ax.set_aspect("equal")
    ax.set_title(f"{result['blade']['blade']} | {result['mode']} | Pööratud: {'Jah' if result.get('orientation_rotated') else 'Ei'}")
    ax.set_xlabel("Laius (mm)")
    ax.set_ylabel("Pikkus (mm)")
    ax.add_patch(plt.Rectangle((0, 0), result["raw_width_mm"] / scale, result["raw_length_mm"] / scale, facecolor="#dddddd", edgecolor="black", linewidth=2))

    piece_w = result["detail_width_mm"] / scale
    piece_h = result["detail_length_mm"] / scale
    kerf = result["blade"]["kerf_mm"] / scale

    max_x = min(result.get("across", result.get("pieces_per_sheet", 0)), 12)
    max_y = min(result.get("along", 1), 12)
    for i in range(max_x):
        for j in range(max_y):
            x = i * (piece_w + kerf)
            y = j * (piece_h + kerf)
            if x + piece_w <= result["raw_width_mm"] / scale and y + piece_h <= result["raw_length_mm"] / scale:
                ax.add_patch(plt.Rectangle((x, y), piece_w, piece_h, facecolor="#b7d7ff", edgecolor="#1f4e79", alpha=0.85))

    if result.get("waste_width_mm", 0) > 0:
        xw = result.get("used_width_mm", 0) / scale
        ax.add_patch(plt.Rectangle((xw, 0), result["waste_width_mm"] / scale, result["raw_length_mm"] / scale, facecolor="#fff2b2", edgecolor="#c49b00", alpha=0.7))

    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    return fig


def result_rows(result):
    rows = [
        ["Töörežiim", result["mode"]],
        ["Tooriku mõõt", f"{fmt(result['raw_width_mm'])} x {fmt(result['raw_length_mm'])} mm"],
        ["Detail", f"{fmt(result['detail_width_mm'])} x {fmt(result['detail_length_mm'])} mm"],
        ["Tellitud kogus", f"{result['detail_count']} tk"],
        ["Toorikuid vaja", f"{result['sheets_needed']} tk"],
        ["Materjalikulu", f"{result['material_m2']:.2f} m²"],
        ["Koguaeg", sec_to_minsec(result["total_sec"])],
        ["Lõikeaeg", sec_to_minsec(result["cutting_time_sec"])],
        ["Setup aeg", sec_to_minsec(result["setup_sec"] + result["blade_setup_sec"])],
        ["Pööratud", "Jah" if result["orientation_rotated"] else "Ei"],
    ]
    if "pieces_per_sheet" in result:
        rows.append(["Ühest toorikust", f"{result['pieces_per_sheet']} tk"])
    if "waste_width_mm" in result:
        rows.append(["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"])
    if "waste_length_mm" in result:
        rows.append(["Jääk pikkusest", f"{fmt(result['waste_length_mm'])} mm"])
    return rows


def render_result_card(result, best_blade_name):
    if result is None:
        st.error("Selle kettaga detail ei mahu.")
        return
    if result["blade"]["blade"] == best_blade_name:
        st.success("Soovitatud variant")
    else:
        st.info("Alternatiiv")
    st.subheader(result["blade"]["blade"])
    m1, m2 = st.columns(2)
    m1.metric("Toorikuid", f"{result['sheets_needed']} tk")
    m2.metric("Materjalikulu", f"{result['material_m2']:.2f} m²")
    m3, m4 = st.columns(2)
    m3.metric("Koguaeg", sec_to_minsec(result['total_sec']))
    m4.metric("Töörežiim", result['mode'])
    st.caption(result["blade_reason"])
    st.table(result_rows(result))
    st.pyplot(draw_scheme(result))
    if st.session_state.show_details:
        with st.expander(f"Detailne arvutuskäik – {result['blade']['blade']}"):
            for step in result.get("calc_steps", []):
                st.write(f"- {step}")
    if result.get("warning"):
        st.warning(result["warning"])


st.title("🪚 Saetöö kalkulaator")
st.caption("Sisesta mida ja millest lõigata vaja — süsteem tuvastab töörežiimi automaatselt ja näitab mõlemad kettad kõrvuti.")

h1, h2 = st.columns([3, 1])
with h1:
    st.markdown("Arvutus käib alles nupust **Arvuta**. Töörežiim valitakse automaatselt detaili ja tooriku mõõtude järgi.")
with h2:
    if st.button("Proovi näitega", use_container_width=True):
        load_example()
        st.rerun()

with st.form("calc_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        material_type = st.selectbox("Materjali tüüp", ["Tavaplaat", "PC", "PMMA"], index=["Tavaplaat", "PC", "PMMA"].index(st.session_state.material_type))
    with c2:
        standard_options = STANDARD_SHEETS[material_type]
        safe_index = min(st.session_state.sheet_index, len(standard_options) - 1)
        standard_choice = st.selectbox("Standard täisplaadi mõõt", standard_options, index=safe_index, format_func=lambda x: f"{int(x[0])} x {int(x[1])} mm")
    with c3:
        thickness_mm = st.number_input("Paksus mm", min_value=1.0, max_value=90.0, value=float(st.session_state.thickness_mm), step=1.0)

    use_custom_size = st.checkbox("Sisestan mõõdud käsitsi", value=st.session_state.use_custom_size)
    d1, d2 = st.columns(2)
    with d1:
        raw_width_mm = st.number_input("Tooriku laius mm", min_value=1.0, max_value=MAX_WIDTH_MM, value=float(st.session_state.raw_width_mm if use_custom_size else standard_choice[0]), step=1.0, disabled=not use_custom_size)
    with d2:
        raw_length_mm = st.number_input("Tooriku pikkus mm", min_value=1.0, max_value=MAX_LENGTH_MM, value=float(st.session_state.raw_length_mm if use_custom_size else standard_choice[1]), step=1.0, disabled=not use_custom_size)

    if not use_custom_size:
        raw_width_mm = float(standard_choice[0])
        raw_length_mm = float(standard_choice[1])

    x1, x2 = st.columns(2)
    with x1:
        detail_width_mm = st.number_input("Detaili laius mm", min_value=1.0, value=float(st.session_state.detail_width_mm), step=1.0)
    with x2:
        detail_length_mm = st.number_input("Detaili pikkus mm", min_value=1.0, value=float(st.session_state.detail_length_mm), step=1.0)

    detail_count = st.number_input("Detailide arv", min_value=1, value=int(st.session_state.detail_count), step=1)
    show_details = st.checkbox("Näita detailset arvutuskäiku", value=st.session_state.show_details)
    submitted = st.form_submit_button("Arvuta", use_container_width=True)

if submitted:
    st.session_state.material_type = material_type
    st.session_state.sheet_index = standard_options.index(standard_choice)
    st.session_state.thickness_mm = thickness_mm
    st.session_state.use_custom_size = use_custom_size
    st.session_state.raw_width_mm = raw_width_mm
    st.session_state.raw_length_mm = raw_length_mm
    st.session_state.detail_width_mm = detail_width_mm
    st.session_state.detail_length_mm = detail_length_mm
    st.session_state.detail_count = int(detail_count)
    st.session_state.show_details = show_details

    error = validate_common(thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, int(detail_count))
    if error:
        st.error(error)
        st.stop()

    results = [make_result(blade, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, int(detail_count)) for blade in BLADES]
    best_result = choose_best_result(results)
    if best_result is None:
        st.error("Detail ei mahu antud toorikusse kummagi kettaga.")
        st.stop()
    add_blade_reasons(results, best_result)
    st.session_state.last_results = results
    st.session_state.best_result = best_result

results = st.session_state.last_results
best_result = st.session_state.best_result

if results and best_result:
    st.subheader("Soovitus")
    st.success(
        f"Süsteemi soovitus on {best_result['blade']['blade']} | töörežiim: {best_result['mode']} | "
        f"toorikuid: {best_result['sheets_needed']} tk | materjalikulu: {best_result['material_m2']:.2f} m² | "
        f"koguaeg: {sec_to_minsec(best_result['total_sec'])}."
    )

    col1, col2 = st.columns(2)
    with col1:
        render_result_card(results[0], best_result["blade"]["blade"])
    with col2:
        render_result_card(results[1], best_result["blade"]["blade"])

    with st.expander("Eeldused ja usaldusinfo"):
        st.write("- Töörežiim tuvastatakse automaatselt detaili ja tooriku mõõtude järgi.")
        st.write("- Detaili pööramine arvestatakse automaatselt.")
        st.write("- Ketta soovitus võrdleb toorikute arvu, materjalikulu ja koguaega.")
        st.write("- Võrdsuse korral eelistatakse 5.6 mm ketast, sest see on tavaliselt masinas sees.")
        st.write("- 3.5 mm ketta valimisel lisatakse 5 min ketta vahetuse setup.")
        st.write("- Ümardamisreegel: toorikute arv ümardatakse alati üles täisarvuni.")
        st.write(f"Viimane uuendus: {LAST_UPDATED}")
else:
    st.info("Sisesta andmed või vajuta 'Proovi näitega', seejärel 'Arvuta'.")
'''
Path('/home/user/saetoo_kalkulaator.py').write_text(code)
print('saved full code', len(code.splitlines()), 'lines')
