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
    "mode": "Ribastamine",
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
    st.session_state.mode = "Ribastamine"
    st.session_state.material_type = "Tavaplaat"
    st.session_state.sheet_index = 0
    st.session_state.thickness_mm = 20.0
    st.session_state.use_custom_size = True
    st.session_state.raw_width_mm = 1005.0
    st.session_state.raw_length_mm = 2005.0
    st.session_state.strip_width_mm = 95.0
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
    if length_mm <= 0 or width_mm <= 0 or sheet_count <= 0:
        return 0
    return (length_mm / 1000.0) * (width_mm / 1000.0) * sheet_count


def single_sheet_area_m2(length_mm, width_mm):
    return (length_mm / 1000.0) * (width_mm / 1000.0)


def max_pieces_in_length(total_len_mm, piece_len_mm, kerf_mm):
    if total_len_mm <= 0 or piece_len_mm <= 0:
        return 0
    n = 0
    while True:
        test_n = n + 1
        used_len = test_n * piece_len_mm + (test_n - 1) * kerf_mm
        if used_len <= total_len_mm:
            n = test_n
        else:
            break
    return n


def used_size_mm(piece_count, piece_size_mm, kerf_mm):
    if piece_count <= 0:
        return 0
    return piece_count * piece_size_mm + (piece_count - 1) * kerf_mm


def validate_common(thickness_mm, raw_length_mm, raw_width_mm):
    if thickness_mm <= 0:
        return "Paksus peab olema suurem kui 0 mm."
    if raw_length_mm <= 0 or raw_length_mm > MAX_LENGTH_MM:
        return f"Tooriku pikkus peab olema vahemikus 1 kuni {int(MAX_LENGTH_MM)} mm."
    if raw_width_mm <= 0 or raw_width_mm > MAX_WIDTH_MM:
        return f"Tooriku laius peab olema vahemikus 1 kuni {int(MAX_WIDTH_MM)} mm."
    if get_sec_per_meter(thickness_mm) is None:
        return "Paksuse vahemik peab olema 1 kuni 90 mm."
    return None


def blade_switch_setup_sec(blade):
    return 0 if blade["is_default"] else 5 * 60


def choose_best_blade(option_small, option_large):
    if option_small is None and option_large is None:
        return None, None
    if option_small is None:
        return option_large, None
    if option_large is None:
        return option_small, None
    small_main = option_small.get("pieces_per_sheet", option_small.get("strips_per_sheet", 0))
    large_main = option_large.get("pieces_per_sheet", option_large.get("strips_per_sheet", 0))
    if small_main > large_main:
        option_small["blade_reason"] = "3.5 mm ketas annab ühest toorikust rohkem detaile või ribasid kui 5.6 mm ketas."
        option_large["blade_reason"] = "5.6 mm ketas annab vähem detaile või ribasid kui 3.5 mm ketas."
        return option_small, option_large
    option_large["blade_reason"] = "Detailide või ribade arv on sama või parem suure kettaga. Võrdsuse korral eelistame alati 5.6 mm ketast, sest see on tavaliselt masinas sees."
    option_small["blade_reason"] = "3.5 mm ketast ei soovitata, sest kogus ei ole suurem kui 5.6 mm kettaga ja ketta vahetus lisab 5 min setupi."
    return option_large, option_small


def build_cut_scheme(lines):
    return "\n".join([f"{i}. {line}" for i, line in enumerate(lines, start=1)])


def calc_tooriku_option(blade, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count):
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    across = max_pieces_in_length(raw_width_mm, detail_width_mm, kerf)
    along = max_pieces_in_length(raw_length_mm, detail_length_mm, kerf)
    pieces_per_sheet = across * along
    if pieces_per_sheet <= 0:
        return None
    sheets_needed = math.ceil(detail_count / pieces_per_sheet)
    used_width = used_size_mm(across, detail_width_mm, kerf)
    used_length = used_size_mm(along, detail_length_mm, kerf)
    waste_width = raw_width_mm - used_width
    waste_length = raw_length_mm - used_length
    rip_cuts_per_sheet = max(0, across - 1)
    cross_cuts_per_sheet = across * max(0, along - 1)
    total_cut_cycles = (rip_cuts_per_sheet + cross_cuts_per_sheet) * sheets_needed
    cutting_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * total_cut_cycles
    setup_sec = 20 * 60
    blade_setup_sec = blade_switch_setup_sec(blade)
    total_sec = cutting_time_sec + setup_sec + blade_setup_sec
    explanation = f"Tellimuse täitmiseks on vaja täpselt {sheets_needed} toorikut. Materjalikulu kokku on {material_area_m2(raw_length_mm, raw_width_mm, sheets_needed):.2f} m²."
    calc_steps = [
        f"Laiuses mahub {across} detaili.",
        f"Pikkuses mahub {along} detaili.",
        f"Ühest toorikust tuleb {pieces_per_sheet} detaili.",
        f"Toorikuid vaja = lae({detail_count} / {pieces_per_sheet}) = {sheets_needed}.",
        f"Lõiketsükleid kokku = {total_cut_cycles}.",
    ]
    return {
        "mode": "Tooriku lõikus",
        "blade": blade,
        "raw_length_mm": raw_length_mm,
        "raw_width_mm": raw_width_mm,
        "detail_length_mm": detail_length_mm,
        "detail_width_mm": detail_width_mm,
        "detail_count": detail_count,
        "across": across,
        "along": along,
        "pieces_per_sheet": pieces_per_sheet,
        "sheets_needed": sheets_needed,
        "used_width_mm": used_width,
        "used_length_mm": used_length,
        "waste_width_mm": waste_width,
        "waste_length_mm": waste_length,
        "cut_cycles": total_cut_cycles,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "blade_setup_sec": blade_setup_sec,
        "total_sec": total_sec,
        "material_m2": material_area_m2(raw_length_mm, raw_width_mm, sheets_needed),
        "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
        "scheme": build_cut_scheme([
            f"Võta {sheets_needed} toorikut mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lõika kõigepealt laiusesse {across} rida detaililaiusega {fmt(detail_width_mm)} mm.",
            f"Seejärel lõika pikkusesse {along} jaotust detailipikkusega {fmt(detail_length_mm)} mm.",
            f"Ühest toorikust saad kokku {pieces_per_sheet} detaili.",
            f"Jääk ühe tooriku kohta on {fmt(waste_width)} mm laiuses ja {fmt(waste_length)} mm pikkuses.",
        ]),
        "explanation": explanation,
        "calc_steps": calc_steps,
    }


def calc_ribastamine_option(blade, thickness_mm, raw_length_mm, raw_width_mm, strip_width_mm, detail_count):
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    strips_per_sheet = max_pieces_in_length(raw_width_mm, strip_width_mm, kerf)
    if strips_per_sheet <= 0:
        return None
    sheets_needed = math.ceil(detail_count / strips_per_sheet)
    used_width = used_size_mm(strips_per_sheet, strip_width_mm, kerf)
    waste_width = raw_width_mm - used_width
    max_stack_sheets = max(1, int(blade["max_stack_mm"] // thickness_mm))
    stack_runs = math.ceil(sheets_needed / max_stack_sheets)
    cut_cycles_per_run = max(0, strips_per_sheet - 1)
    total_cut_cycles = stack_runs * cut_cycles_per_run
    cutting_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * total_cut_cycles
    setup_sec = 20 * 60
    blade_setup_sec = blade_switch_setup_sec(blade)
    total_sec = cutting_time_sec + setup_sec + blade_setup_sec
    warning = "Hoiatus: alla 20 mm ribade puhul võivad masina käpad segada." if strip_width_mm < 20 else None
    explanation = f"Tellimuse täitmiseks on vaja täpselt {sheets_needed} plaati. Materjalikulu kokku on {material_area_m2(raw_length_mm, raw_width_mm, sheets_needed):.2f} m²."
    calc_steps = [
        f"Ühest plaadist tuleb {strips_per_sheet} riba.",
        f"Plaate vaja = lae({detail_count} / {strips_per_sheet}) = {sheets_needed}.",
        f"Korraga saab virna panna {max_stack_sheets} plaati.",
        f"Ribastamise seeriaid = lae({sheets_needed} / {max_stack_sheets}) = {stack_runs}.",
        f"Lõiketsükleid kokku = {total_cut_cycles}.",
    ]
    return {
        "mode": "Ribastamine",
        "blade": blade,
        "raw_length_mm": raw_length_mm,
        "raw_width_mm": raw_width_mm,
        "strip_width_mm": strip_width_mm,
        "detail_count": detail_count,
        "strips_per_sheet": strips_per_sheet,
        "sheets_needed": sheets_needed,
        "used_width_mm": used_width,
        "waste_width_mm": waste_width,
        "max_stack_sheets": max_stack_sheets,
        "stack_runs": stack_runs,
        "cut_cycles": total_cut_cycles,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "blade_setup_sec": blade_setup_sec,
        "total_sec": total_sec,
        "material_m2": material_area_m2(raw_length_mm, raw_width_mm, sheets_needed),
        "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
        "warning": warning,
        "scheme": build_cut_scheme([
            f"Võta {sheets_needed} täisplaati mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lao korraga virna kuni {max_stack_sheets} plaati, selle töö jaoks on vaja {stack_runs} ribastamise seeriat.",
            f"Lõika igast virnast välja {strips_per_sheet} täispikka riba laiusega {fmt(strip_width_mm)} mm.",
            f"Ribalõikeid ühes seerias on {cut_cycles_per_run}.",
            f"Jääk ühe plaadi laiuses on {fmt(waste_width)} mm.",
        ]),
        "explanation": explanation,
        "calc_steps": calc_steps,
    }


def calc_ribastamine_tykeldamine_option(blade, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count):
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    strips_per_sheet = max_pieces_in_length(raw_width_mm, detail_width_mm, kerf)
    pieces_per_strip = max_pieces_in_length(raw_length_mm, detail_length_mm, kerf)
    if strips_per_sheet <= 0 or pieces_per_strip <= 0:
        return None
    pieces_per_sheet = strips_per_sheet * pieces_per_strip
    sheets_needed = math.ceil(detail_count / pieces_per_sheet)
    used_width = used_size_mm(strips_per_sheet, detail_width_mm, kerf)
    used_length = used_size_mm(pieces_per_strip, detail_length_mm, kerf)
    waste_width = raw_width_mm - used_width
    waste_length = raw_length_mm - used_length
    max_stack_sheets = max(1, int(blade["max_stack_mm"] // thickness_mm))
    stack_runs = math.ceil(sheets_needed / max_stack_sheets)
    strip_cut_cycles = stack_runs * max(0, strips_per_sheet - 1)
    total_strips = sheets_needed * strips_per_sheet
    max_stack_strips = max(1, int(blade["max_stack_mm"] // thickness_mm))
    crosscut_runs = math.ceil(total_strips / max_stack_strips)
    crosscut_cycles = crosscut_runs * max(0, pieces_per_strip - 1)
    strip_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * strip_cut_cycles
    crosscut_time_sec = (used_width / 1000.0) * sec_per_m * 2 * crosscut_cycles
    setup_sec = 20 * 60
    blade_setup_sec = blade_switch_setup_sec(blade)
    total_sec = strip_time_sec + crosscut_time_sec + setup_sec + blade_setup_sec
    warning = "Hoiatus: alla 20 mm ribade puhul võivad masina käpad segada." if detail_width_mm < 20 else None
    explanation = f"Tellimuse täitmiseks on vaja täpselt {sheets_needed} toorikut. Materjalikulu kokku on {material_area_m2(raw_length_mm, raw_width_mm, sheets_needed):.2f} m²."
    calc_steps = [
        f"Ühest plaadist tuleb {strips_per_sheet} riba.",
        f"Ühest ribast tuleb {pieces_per_strip} detaili.",
        f"Ühest toorikust tuleb {pieces_per_sheet} detaili.",
        f"Toorikuid vaja = lae({detail_count} / {pieces_per_sheet}) = {sheets_needed}.",
        f"Ribalõiketsükleid = {strip_cut_cycles}, tükelduslõiketsükleid = {crosscut_cycles}.",
    ]
    return {
        "mode": "Ribastamine + tükeldamine",
        "blade": blade,
        "raw_length_mm": raw_length_mm,
        "raw_width_mm": raw_width_mm,
        "detail_length_mm": detail_length_mm,
        "detail_width_mm": detail_width_mm,
        "detail_count": detail_count,
        "strips_per_sheet": strips_per_sheet,
        "pieces_per_strip": pieces_per_strip,
        "pieces_per_sheet": pieces_per_sheet,
        "sheets_needed": sheets_needed,
        "used_width_mm": used_width,
        "used_length_mm": used_length,
        "waste_width_mm": waste_width,
        "waste_length_mm": waste_length,
        "max_stack_sheets": max_stack_sheets,
        "stack_runs": stack_runs,
        "strip_cut_cycles": strip_cut_cycles,
        "crosscut_cycles": crosscut_cycles,
        "strip_time_sec": strip_time_sec,
        "crosscut_time_sec": crosscut_time_sec,
        "setup_sec": setup_sec,
        "blade_setup_sec": blade_setup_sec,
        "total_sec": total_sec,
        "material_m2": material_area_m2(raw_length_mm, raw_width_mm, sheets_needed),
        "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
        "warning": warning,
        "scheme": build_cut_scheme([
            f"Võta {sheets_needed} täisplaati mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lao korraga virna kuni {max_stack_sheets} plaati. Ribastamise jaoks on vaja {stack_runs} seeriat.",
            f"Ribasta igast plaadist {strips_per_sheet} riba laiusega {fmt(detail_width_mm)} mm.",
            f"Seejärel tükelda ribad detailipikkuseks {fmt(detail_length_mm)} mm, ühest ribast saab {pieces_per_strip} detaili.",
            f"Kokku saad ühest toorikust {pieces_per_sheet} detaili.",
            f"Jääk ühe tooriku kohta on {fmt(waste_width)} mm laiuses ja {fmt(waste_length)} mm pikkuses.",
        ]),
        "explanation": explanation,
        "calc_steps": calc_steps,
    }


def compare_blades(mode, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm=None, detail_width_mm=None, detail_count=None, strip_width_mm=None):
    if mode == "Tooriku lõikus":
        small = calc_tooriku_option(SMALL_BLADE, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count)
        large = calc_tooriku_option(LARGE_BLADE, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count)
    elif mode == "Ribastamine":
        small = calc_ribastamine_option(SMALL_BLADE, thickness_mm, raw_length_mm, raw_width_mm, strip_width_mm, detail_count)
        large = calc_ribastamine_option(LARGE_BLADE, thickness_mm, raw_length_mm, raw_width_mm, strip_width_mm, detail_count)
    else:
        small = calc_ribastamine_tykeldamine_option(SMALL_BLADE, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count)
        large = calc_ribastamine_tykeldamine_option(LARGE_BLADE, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count)
    return choose_best_blade(small, large)


def result_rows(result):
    rows = [
        ["Tooriku mõõt", f"{fmt(result['raw_width_mm'])} x {fmt(result['raw_length_mm'])} mm"],
        ["Toorikuid vaja", f"{result['sheets_needed']} tk"],
        ["Ühe tooriku pindala", f"{result['single_sheet_m2']:.2f} m²"],
        ["Materjalikulu kokku", f"{result['material_m2']:.2f} m²"],
        ["Ketas", result["blade"]["blade"]],
        ["Ketta vahetuse setup", sec_to_minsec(result["blade_setup_sec"])],
    ]
    if result["mode"] == "Tooriku lõikus":
        rows += [
            ["Detail", f"{fmt(result['detail_length_mm'])} x {fmt(result['detail_width_mm'])} mm"],
            ["Tellitud kogus", f"{result['detail_count']} tk"],
            ["Ühest toorikust", f"{result['pieces_per_sheet']} tk"],
            ["Laiuses", f"{result['across']} tk"],
            ["Pikkuses", f"{result['along']} tk"],
            ["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"],
            ["Jääk pikkusest", f"{fmt(result['waste_length_mm'])} mm"],
        ]
    elif result["mode"] == "Ribastamine":
        rows += [
            ["Riba laius", f"{fmt(result['strip_width_mm'])} mm"],
            ["Tellitud kogus", f"{result['detail_count']} tk"],
            ["Ribasid ühest plaadist", f"{result['strips_per_sheet']} tk"],
            ["Virna suurus", f"{result['max_stack_sheets']} plaati"],
            ["Ribastamise seeriaid", f"{result['stack_runs']}"],
            ["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"],
        ]
    else:
        rows += [
            ["Detail", f"{fmt(result['detail_length_mm'])} x {fmt(result['detail_width_mm'])} mm"],
            ["Tellitud kogus", f"{result['detail_count']} tk"],
            ["Ühest toorikust", f"{result['pieces_per_sheet']} tk"],
            ["Ribasid ühest plaadist", f"{result['strips_per_sheet']} tk"],
            ["Tükke ühest ribast", f"{result['pieces_per_strip']} tk"],
            ["Virna suurus", f"{result['max_stack_sheets']} plaati/riba"],
            ["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"],
            ["Jääk pikkusest", f"{fmt(result['waste_length_mm'])} mm"],
        ]
    return rows


st.title("🪚 Saetöö kalkulaator")
st.caption("Täpne materjalikulu, ketta soovitus, tööjärjekord ja usaldusväärne arvutuskäik")

head1, head2 = st.columns([3, 1])
with head1:
    st.markdown("Kasuta vormi, et sisestada töö andmed. Arvutus käib ainult nupust **Arvuta**.")
with head2:
    if st.button("Proovi näitega", use_container_width=True):
        load_example()
        st.rerun()

mode = st.radio(
    "Vali töö tüüp",
    ["Tooriku lõikus", "Ribastamine", "Ribastamine + tükeldamine"],
    horizontal=True,
    key="mode",
)

with st.form("calc_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        material_type = st.selectbox("Materjali tüüp", ["Tavaplaat", "PC", "PMMA"], index=["Tavaplaat", "PC", "PMMA"].index(st.session_state.material_type))
    with c2:
        standard_options = STANDARD_SHEETS[material_type]
        safe_index = min(st.session_state.sheet_index, len(standard_options) - 1)
        standard_choice = st.selectbox(
            "Standard täisplaadi mõõt",
            standard_options,
            index=safe_index,
            format_func=lambda x: f"{int(x[0])} x {int(x[1])} mm"
        )
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

    if st.session_state.mode == "Tooriku lõikus":
        i1, i2, i3 = st.columns(3)
        with i1:
            detail_length_mm = st.number_input("Detaili pikkus mm", min_value=1.0, value=float(st.session_state.detail_length_mm), step=1.0)
        with i2:
            detail_width_mm = st.number_input("Detaili laius mm", min_value=1.0, value=float(st.session_state.detail_width_mm), step=1.0)
        with i3:
            detail_count = st.number_input("Detailide arv", min_value=1, value=int(st.session_state.detail_count), step=1)
        strip_width_mm = None
    elif st.session_state.mode == "Ribastamine":
        i1, i2 = st.columns(2)
        with i1:
            strip_width_mm = st.number_input("Riba laius mm", min_value=1.0, value=float(st.session_state.strip_width_mm), step=1.0)
        with i2:
            detail_count = st.number_input("Ribade arv", min_value=1, value=int(st.session_state.detail_count), step=1)
        detail_length_mm = None
        detail_width_mm = None
    else:
        i1, i2, i3 = st.columns(3)
        with i1:
            detail_length_mm = st.number_input("Detaili pikkus mm", min_value=1.0, value=float(st.session_state.detail_length_mm), step=1.0)
        with i2:
            detail_width_mm = st.number_input("Detaili laius mm", min_value=1.0, value=float(st.session_state.detail_width_mm), step=1.0)
        with i3:
            detail_count = st.number_input("Detailide arv", min_value=1, value=int(st.session_state.detail_count), step=1)
        strip_width_mm = None

    show_details = st.checkbox("Näita detailset arvutuskäiku", value=st.session_state.show_details)
    submitted = st.form_submit_button("Arvuta", use_container_width=True)

if submitted:
    st.session_state.material_type = material_type
    st.session_state.sheet_index = standard_options.index(standard_choice)
    st.session_state.thickness_mm = thickness_mm
    st.session_state.use_custom_size = use_custom_size
    st.session_state.raw_width_mm = raw_width_mm
    st.session_state.raw_length_mm = raw_length_mm
    st.session_state.show_details = show_details

    if detail_length_mm is not None:
        st.session_state.detail_length_mm = detail_length_mm
    if detail_width_mm is not None:
        st.session_state.detail_width_mm = detail_width_mm
    if strip_width_mm is not None:
        st.session_state.strip_width_mm = strip_width_mm
    st.session_state.detail_count = int(detail_count)

    common_error = validate_common(thickness_mm, raw_length_mm, raw_width_mm)
    if common_error:
        st.error(common_error)
        st.stop()

    if st.session_state.mode == "Tooriku lõikus":
        if detail_length_mm > raw_length_mm or detail_width_mm > raw_width_mm:
            st.error("Detail ei mahu antud toorikusse.")
            st.stop()
        result, alternative = compare_blades(st.session_state.mode, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm=detail_length_mm, detail_width_mm=detail_width_mm, detail_count=int(detail_count))
    elif st.session_state.mode == "Ribastamine":
        if strip_width_mm > raw_width_mm:
            st.error("Riba laius ei mahu antud toorikusse.")
            st.stop()
        result, alternative = compare_blades(st.session_state.mode, thickness_mm, raw_length_mm, raw_width_mm, strip_width_mm=strip_width_mm, detail_count=int(detail_count))
    else:
        if detail_length_mm > raw_length_mm or detail_width_mm > raw_width_mm:
            st.error("Detail ei mahu antud toorikusse.")
            st.stop()
        result, alternative = compare_blades(st.session_state.mode, thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm=detail_length_mm, detail_width_mm=detail_width_mm, detail_count=int(detail_count))

    if result is None:
        st.error("Arvutust ei saanud teha. Kontrolli sisendeid.")
        st.stop()

    st.session_state.last_result = result
    st.session_state.last_alternative = alternative

result = st.session_state.last_result
alternative = st.session_state.last_alternative

if result:
    st.subheader("Tulemus")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Toorikuid vaja", f"{result['sheets_needed']} tk")
    m2.metric("Materjalikulu", f"{result['material_m2']:.2f} m²")
    m3.metric("Koguaeg", sec_to_minsec(result['total_sec']))
    m4.metric("Soovitatud ketas", result['blade']['blade'])

    st.table(result_rows(result))

    st.subheader("Mida see tähendab?")
    st.info(result["explanation"])

    st.subheader("Ketta soovitus")
    st.write(result["blade_reason"])

    st.subheader("Tööjärjekord ja lõikeskeem")
    st.code(result["scheme"])

    if st.session_state.show_details:
        with st.expander("Detailne arvutuskäik", expanded=True):
            for step in result.get("calc_steps", []):
                st.write(f"- {step}")
            st.write(f"Setup aeg kokku: {sec_to_minsec(result['setup_sec'] + result['blade_setup_sec'])}.")

    if result.get("warning"):
        st.warning(result["warning"])

    assumptions = [
        "Võrdsuse korral eelistatakse alati 5.6 mm ketast.",
        "3.5 mm ketta valimisel lisatakse 5 min ketta vahetuse setup.",
        "Ribastamisel pikkusesse lisalõiget ei arvestata; setup on 20 min (10 min materjali toomine, 5 min sae ettevalmistus, 5 min pakkimine või äraviimine).",
        "Alla 100 mm jääk ei ole otsustamisel määrav.",
        "Paksusepõhine lõikekiirus põhineb teie kasutataval sisemisel tabelil.",
    ]

    with st.expander("Eeldused ja usaldusinfo"):
        for item in assumptions:
            st.write(f"- {item}")
        st.write(f"Viimane uuendus: {LAST_UPDATED}")
        st.write("Ümardamisreegel: toorikute arv ümardatakse alati üles täisarvuni.")
        st.write("Veast teavitamine: kui näed ebaloogilist tulemust, kontrolli kõigepealt tooriku ja detaili mõõte ning ketta loogikat.")

    if alternative is not None:
        alt_main = alternative.get("pieces_per_sheet", alternative.get("strips_per_sheet", 0))
        res_main = result.get("pieces_per_sheet", result.get("strips_per_sheet", 0))
        if alt_main != res_main or alternative['blade']['blade'] != result['blade']['blade']:
            with st.expander("Võrdlus teise kettaga"):
                st.write(f"Teine variant: {alternative['blade']['blade']}")
                st.write(alternative["blade_reason"])
                st.table(result_rows(alternative))
                st.code(alternative["scheme"])
else:
    st.info("Sisesta andmed või vajuta 'Proovi näitega', seejärel 'Arvuta'.")
