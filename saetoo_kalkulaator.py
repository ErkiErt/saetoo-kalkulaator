import math
import streamlit as st

st.set_page_config(page_title="Saetöö kalkulaator", page_icon="🪚", layout="wide")


def get_sec_per_meter(thickness_mm):
    if 1 <= thickness_mm <= 20:
        return 6
    elif 20 < thickness_mm <= 40:
        return 7.5
    elif 40 < thickness_mm <= 50:
        return 10
    elif 50 < thickness_mm <= 60:
        return 12
    elif 60 < thickness_mm <= 70:
        return 18
    elif 70 < thickness_mm <= 80:
        return 24
    elif 80 < thickness_mm <= 90:
        return 36
    return None


def recommend_blade(thickness_mm):
    if thickness_mm <= 25:
        return {
            "blade": "3.5 mm",
            "kerf_mm": 3.5,
            "max_stack_mm": 30,
            "note": "Soovitus: 3.5 mm ketas, et saada rohkem detaile."
        }
    return {
        "blade": "5.6 mm",
        "kerf_mm": 5.6,
        "max_stack_mm": 80,
        "note": "3.5 mm ketas ei sobi, kasuta 5.6 mm ketast."
    }


def max_pieces_in_length(total_len_mm, piece_len_mm, kerf_mm):
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


def packaging_time(detail_count):
    return detail_count * 5 if detail_count >= 10 else 0


def sec_to_minsec(seconds):
    if seconds is None:
        return "Ei saa arvutada"
    minutes = int(seconds // 60)
    sec = round(seconds % 60, 1)
    return f"{minutes} min {sec} sek"


def tooriku_loikus(thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count):
    blade = recommend_blade(thickness_mm)
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    if sec_per_m is None:
        return None

    across = max_pieces_in_length(raw_width_mm, detail_width_mm, kerf)
    along = max_pieces_in_length(raw_length_mm, detail_length_mm, kerf)
    pieces_per_sheet = across * along

    if pieces_per_sheet <= 0:
        return {"mode": "Tooriku lõikus", "error": "Antud detail ei mahu toorikusse.", "blade": blade}

    sheets_needed = math.ceil(detail_count / pieces_per_sheet)
    used_width = used_size_mm(across, detail_width_mm, kerf)
    used_length = used_size_mm(along, detail_length_mm, kerf)
    waste_width = raw_width_mm - used_width
    waste_length = raw_length_mm - used_length
    cut_cycles_per_sheet = max(0, (across - 1)) + max(0, across * (along - 1))
    total_cut_cycles = cut_cycles_per_sheet * sheets_needed
    cutting_time_sec = (raw_length_mm / 1000) * sec_per_m * 2 * total_cut_cycles
    setup_sec = 20 * 60
    pack_sec = packaging_time(detail_count)

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
        "packaging_sec": pack_sec,
        "total_sec": cutting_time_sec + setup_sec + pack_sec,
        "explanation": (
            f"Ühest toorikust saab {across} detaili laiuses ja {along} detaili pikkuses, kokku {pieces_per_sheet} detaili. "
            f"Tellimuse täitmiseks on vaja umbes {sheets_needed} toorikut."
        ),
    }


def ribastamine(thickness_mm, raw_length_mm, raw_width_mm, strip_width_mm, detail_count):
    blade = recommend_blade(thickness_mm)
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    if sec_per_m is None:
        return None

    strips_per_sheet = max_pieces_in_length(raw_width_mm, strip_width_mm, kerf)
    if strips_per_sheet <= 0:
        return {"mode": "Ribastamine", "error": "Antud riba ei mahu tooriku laiusse.", "blade": blade}

    sheets_needed = math.ceil(detail_count / strips_per_sheet)
    used_width = used_size_mm(strips_per_sheet, strip_width_mm, kerf)
    waste_width = raw_width_mm - used_width
    cut_cycles = max(0, strips_per_sheet - 1) * sheets_needed
    cutting_time_sec = (raw_length_mm / 1000) * sec_per_m * 2 * cut_cycles
    setup_sec = 20 * 60
    pack_sec = packaging_time(detail_count)
    warning = None
    if strip_width_mm < 20:
        warning = "Hoiatus: alla 20 mm ribade puhul võivad masina käpad segada."

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
        "cut_cycles": cut_cycles,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "packaging_sec": pack_sec,
        "total_sec": cutting_time_sec + setup_sec + pack_sec,
        "warning": warning,
        "explanation": (
            f"Ühest toorikust saab {strips_per_sheet} täispikka riba. Tellimuse jaoks on vaja umbes {sheets_needed} toorikut."
        ),
    }


def ribastamine_tukeldamine(thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, detail_count):
    blade = recommend_blade(thickness_mm)
    kerf = blade["kerf_mm"]
    sec_per_m = get_sec_per_meter(thickness_mm)
    if sec_per_m is None:
        return None

    strips_per_sheet = max_pieces_in_length(raw_width_mm, detail_width_mm, kerf)
    pieces_per_strip = max_pieces_in_length(raw_length_mm, detail_length_mm, kerf)
    if strips_per_sheet <= 0 or pieces_per_strip <= 0:
        return {"mode": "Ribastamine + tükeldamine", "error": "Detaili mõõt ei mahu antud toorikust välja.", "blade": blade}

    pieces_per_sheet = strips_per_sheet * pieces_per_strip
    sheets_needed = math.ceil(detail_count / pieces_per_sheet)
    used_width = used_size_mm(strips_per_sheet, detail_width_mm, kerf)
    used_length = used_size_mm(pieces_per_strip, detail_length_mm, kerf)
    waste_width = raw_width_mm - used_width
    waste_length = raw_length_mm - used_length
    max_stack_pieces = max(1, int(blade["max_stack_mm"] // thickness_mm))
    strip_cut_cycles_per_sheet = max(0, strips_per_sheet - 1)
    total_strip_cut_cycles = strip_cut_cycles_per_sheet * sheets_needed
    total_strips = strips_per_sheet * sheets_needed
    crosscut_cycles = math.ceil(total_strips / max_stack_pieces) * max(0, pieces_per_strip - 1)
    strip_time_sec = (raw_length_mm / 1000) * sec_per_m * 2 * total_strip_cut_cycles
    crosscut_time_sec = (used_width / 1000) * sec_per_m * 2 * crosscut_cycles
    setup_sec = 20 * 60
    pack_sec = packaging_time(detail_count)
    warning = None
    if detail_width_mm < 20:
        warning = "Hoiatus: alla 20 mm ribade puhul võivad masina käpad segada."

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
        "max_stack_pieces": max_stack_pieces,
        "used_width_mm": used_width,
        "used_length_mm": used_length,
        "waste_width_mm": waste_width,
        "waste_length_mm": waste_length,
        "strip_cut_cycles": total_strip_cut_cycles,
        "crosscut_cycles": crosscut_cycles,
        "strip_time_sec": strip_time_sec,
        "crosscut_time_sec": crosscut_time_sec,
        "setup_sec": setup_sec,
        "packaging_sec": pack_sec,
        "total_sec": strip_time_sec + crosscut_time_sec + setup_sec + pack_sec,
        "warning": warning,
        "explanation": (
            f"Kõigepealt lõigatakse ühest toorikust {strips_per_sheet} täispikka riba. Seejärel saab ühest ribast {pieces_per_strip} detaili, "
            f"kokku {pieces_per_sheet} detaili tooriku kohta. Tükeldamisel saab korraga kokku panna kuni {max_stack_pieces} riba."
        ),
    }


def fmt(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


st.title("🪚 Saetöö kalkulaator")
st.caption("3 valikut: Tooriku lõikus, Ribastamine, Ribastamine + tükeldamine")

mode = st.radio("Vali töö tüüp", ["Tooriku lõikus", "Ribastamine", "Ribastamine + tükeldamine"], horizontal=True)

with st.form("calc_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        thickness_mm = st.number_input("Paksus mm", min_value=1.0, value=20.0, step=1.0)
    with c2:
        raw_length_mm = st.number_input("Tooriku pikkus mm", min_value=1.0, value=2000.0, step=1.0)
    with c3:
        raw_width_mm = st.number_input("Tooriku laius mm", min_value=1.0, value=1000.0, step=1.0)

    if mode == "Tooriku lõikus":
        d1, d2, d3 = st.columns(3)
        with d1:
            detail_length_mm = st.number_input("Detaili pikkus mm", min_value=1.0, value=100.0, step=1.0)
        with d2:
            detail_width_mm = st.number_input("Detaili laius mm", min_value=1.0, value=100.0, step=1.0)
        with d3:
            detail_count = st.number_input("Detailide arv", min_value=1, value=100, step=1)
    elif mode == "Ribastamine":
        d1, d2 = st.columns(2)
        with d1:
            strip_width_mm = st.number_input("Riba laius mm", min_value=1.0, value=94.0, step=1.0)
        with d2:
            detail_count = st.number_input("Ribade arv / detailide arv", min_value=1, value=10, step=1)
    else:
        d1, d2, d3 = st.columns(3)
        with d1:
            detail_length_mm = st.number_input("Detaili pikkus mm", min_value=1.0, value=100.0, step=1.0)
        with d2:
            detail_width_mm = st.number_input("Detaili laius mm", min_value=1.0, value=100.0, step=1.0)
        with d3:
            detail_count = st.number_input("Detailide arv", min_value=1, value=100, step=1)

    submitted = st.form_submit_button("Arvuta", use_container_width=True)

if submitted:
    if mode == "Tooriku lõikus":
        result = tooriku_loikus(thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, int(detail_count))
    elif mode == "Ribastamine":
        result = ribastamine(thickness_mm, raw_length_mm, raw_width_mm, strip_width_mm, int(detail_count))
    else:
        result = ribastamine_tukeldamine(thickness_mm, raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, int(detail_count))

    if result is None:
        st.error("Arvutust ei saanud teha. Kontrolli paksuse vahemikku.")
    elif "error" in result:
        st.error(result["error"])
        st.info(result["blade"]["note"])
    else:
        st.subheader("Tulemus")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Toorikuid vaja", f"{result.get('sheets_needed', '-')}")
        m2.metric("Lõiketsüklid", f"{result.get('cut_cycles', result.get('strip_cut_cycles', '-'))}")
        m3.metric("Koguaeg", sec_to_minsec(result.get('total_sec')))
        m4.metric("Ketas", result["blade"]["blade"])

        rows = []
        if result["mode"] == "Tooriku lõikus":
            rows = [
                ["Toorik", f"{fmt(result['raw_length_mm'])} x {fmt(result['raw_width_mm'])} mm"],
                ["Detail", f"{fmt(result['detail_length_mm'])} x {fmt(result['detail_width_mm'])} mm"],
                ["Tellitud kogus", f"{result['detail_count']} tk"],
                ["Ühest toorikust", f"{result['pieces_per_sheet']} tk"],
                ["Laiuses", f"{result['across']} tk"],
                ["Pikkuses", f"{result['along']} tk"],
                ["Kasutatud laius", f"{fmt(result['used_width_mm'])} mm"],
                ["Kasutatud pikkus", f"{fmt(result['used_length_mm'])} mm"],
                ["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"],
                ["Jääk pikkusest", f"{fmt(result['waste_length_mm'])} mm"],
            ]
        elif result["mode"] == "Ribastamine":
            rows = [
                ["Toorik", f"{fmt(result['raw_length_mm'])} x {fmt(result['raw_width_mm'])} mm"],
                ["Riba laius", f"{fmt(result['strip_width_mm'])} mm"],
                ["Tellitud kogus", f"{result['detail_count']} tk"],
                ["Ribasid ühest toorikust", f"{result['strips_per_sheet']} tk"],
                ["Kasutatud laius", f"{fmt(result['used_width_mm'])} mm"],
                ["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"],
            ]
        else:
            rows = [
                ["Toorik", f"{fmt(result['raw_length_mm'])} x {fmt(result['raw_width_mm'])} mm"],
                ["Detail", f"{fmt(result['detail_length_mm'])} x {fmt(result['detail_width_mm'])} mm"],
                ["Tellitud kogus", f"{result['detail_count']} tk"],
                ["Ribasid ühest toorikust", f"{result['strips_per_sheet']} tk"],
                ["Tükke ühest ribast", f"{result['pieces_per_strip']} tk"],
                ["Ühest toorikust kokku", f"{result['pieces_per_sheet']} tk"],
                ["Ribasid korraga tükeldusse", f"{result['max_stack_pieces']} tk"],
                ["Kasutatud laius", f"{fmt(result['used_width_mm'])} mm"],
                ["Kasutatud pikkus", f"{fmt(result['used_length_mm'])} mm"],
                ["Jääk laiusest", f"{fmt(result['waste_width_mm'])} mm"],
                ["Jääk pikkusest", f"{fmt(result['waste_length_mm'])} mm"],
            ]

        st.table(rows)
        st.markdown("### Selgitus")
        st.write(result["explanation"])
        st.info(result["blade"]["note"])
        if result.get("warning"):
            st.warning(result["warning"])
