import math
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Saetöö kalkulaator", page_icon="🪚", layout="wide")

MAX_LENGTH_MM = 3000.0
MAX_WIDTH_MM = 2050.0
LAST_UPDATED = "2026-04-23"

LARGE_BLADE = {"blade": "5.6 mm", "kerf_mm": 5.6, "max_stack_mm": 80.0, "is_default": True}
SMALL_BLADE = {"blade": "3.5 mm", "kerf_mm": 3.5, "max_stack_mm": 30.0, "is_default": False}
BLADES = [LARGE_BLADE, SMALL_BLADE]

THICKNESS_OPTIONS_MM = list(range(1, 13)) + [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 85]

DEFAULTS = {
    "thickness_mm": 20,
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


def single_sheet_area_m2(length_mm, width_mm):
    return (length_mm * width_mm) / 1_000_000.0


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
    if thickness_mm not in THICKNESS_OPTIONS_MM:
        return "Lubatud paksused on 1 kuni 12 mm sammuga 1 ning edasi 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75 ja 85 mm."
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
    return "
".join([f"{i}. {line}" for i, line in enumerate(lines, start=1)])


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
        waste_width = max(0, raw_width_mm - used_width)
        max_stack_sheets = max(1, int(blade["max_stack_mm"] // thickness_mm))
        stack_runs = math.ceil(sheets_needed / max_stack_sheets)
        cut_cycles = stack_runs * max(0, across - 1)
        cutting_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * cut_cycles
        kerf_area_mm2 = max(0, across - 1) * raw_length_mm * kerf * sheets_needed
        used_area_mm2 = raw_length_mm * used_width * sheets_needed
        actual_material_m2 = (used_area_mm2 + kerf_area_mm2) / 1_000_000.0
        total_sec = cutting_time_sec + setup_sec + blade_setup_sec
        explanation = f"Süsteem valis ribastamise, sest detail mahub laiusesse {across} ribana ja pikkusesse tükeldust ei ole vaja. Materjalikulu arvestab ainult detailide tegemiseks kulunud materjali koos saeteega: {actual_material_m2:.2f} m²."
        calc_steps = [
            f"Automaatne töörežiim: {mode}.",
            f"Orientatsioon {'pööratud' if rotated else 'algne'}.",
            f"Ribasid ühest plaadist = {across}.",
            f"Plaate vaja = lae({detail_count} / {across}) = {sheets_needed}.",
            f"Materjalikulu arvestab ainult kasutatud osa ja saeteed.",
        ]
        scheme = build_cut_scheme([
            f"Võta {sheets_needed} täisplaati mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lao korraga virna kuni {max_stack_sheets} plaati, selle töö jaoks on vaja {stack_runs} ribastamise seeriat.",
            f"Lõika igast virnast välja {across} täispikka riba laiusega {fmt(d_wid)} mm.",
            f"Ribalõikeid ühes seerias on {max(0, across - 1)}.",
            f"Alles jääv kasutamata täisriba ühe plaadi kohta on {fmt(waste_width)} mm.",
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
            "used_length_mm": raw_length_mm,
            "waste_width_mm": waste_width,
            "waste_length_mm": 0.0,
            "cutting_time_sec": cutting_time_sec,
            "setup_sec": setup_sec,
            "blade_setup_sec": blade_setup_sec,
            "total_sec": total_sec,
            "material_m2": actual_material_m2,
            "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
            "warning": warning,
            "scheme": scheme,
            "calc_steps": calc_steps,
            "explanation": explanation,
            "across": across,
            "along": 1,
            "kerf_area_m2": kerf_area_mm2 / 1_000_000.0,
            "used_area_m2": used_area_mm2 / 1_000_000.0,
            "valuable_remainder_m2": (waste_width * raw_length_mm * sheets_needed) / 1_000_000.0,
            "waste_value_penalty": sheets_needed * 1000 + waste_width,
        }

    sheets_needed = math.ceil(detail_count / pieces_per_sheet)
    used_width = used_size_mm(across, d_wid, kerf)
    used_length = used_size_mm(along, d_len, kerf)
    waste_width = max(0, raw_width_mm - used_width)
    waste_length = max(0, raw_length_mm - used_length)

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
        kerf_area_mm2 = (
            max(0, across - 1) * raw_length_mm * kerf * sheets_needed
            + max(0, along - 1) * used_width * kerf * sheets_needed
        )
        used_area_mm2 = used_width * used_length * sheets_needed
        actual_material_m2 = (used_area_mm2 + kerf_area_mm2) / 1_000_000.0
        total_sec = strip_time_sec + crosscut_time_sec + setup_sec + blade_setup_sec
        explanation = f"Süsteem valis ribastamise + tükeldamise, sest detailist saab teha esmalt ribad ja siis lõigata need pikkusesse. Materjalikulu arvestab ainult detailide tegemiseks kulunud materjali koos saeteega: {actual_material_m2:.2f} m²."
        calc_steps = [
            f"Automaatne töörežiim: {mode}.",
            f"Orientatsioon {'pööratud' if rotated else 'algne'}.",
            f"Ribasid ühest plaadist = {across}.",
            f"Tükke ühest ribast = {along}.",
            f"Ühest toorikust tuleb {pieces_per_sheet} detaili.",
            f"Toorikuid vaja = lae({detail_count} / {pieces_per_sheet}) = {sheets_needed}.",
            f"Materjalikulu arvestab ainult kasutatud osa ja saeteed.",
        ]
        scheme = build_cut_scheme([
            f"Võta {sheets_needed} täisplaati mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
            f"Lao korraga virna kuni {max_stack_sheets} plaati. Ribastamise jaoks on vaja {stack_runs} seeriat.",
            f"Ribasta igast plaadist {across} riba laiusega {fmt(d_wid)} mm.",
            f"Seejärel tükelda ribad detailipikkuseks {fmt(d_len)} mm, ühest ribast saab {along} detaili.",
            f"Kokku saad ühest toorikust {pieces_per_sheet} detaili.",
            f"Alles jääb kasutamata {fmt(waste_width)} mm laiuses ja {fmt(waste_length)} mm pikkuses.",
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
            "material_m2": actual_material_m2,
            "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
            "warning": warning,
            "scheme": scheme,
            "calc_steps": calc_steps,
            "explanation": explanation,
            "across": across,
            "along": along,
            "kerf_area_m2": kerf_area_mm2 / 1_000_000.0,
            "used_area_m2": used_area_mm2 / 1_000_000.0,
            "valuable_remainder_m2": ((waste_width * raw_length_mm) + (used_width * waste_length)) * sheets_needed / 1_000_000.0,
            "waste_value_penalty": sheets_needed * 1000 + waste_width + waste_length,
        }

    total_cut_cycles = (max(0, across - 1) + across * max(0, along - 1)) * sheets_needed
    cutting_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * total_cut_cycles
    kerf_area_mm2 = (
        max(0, across - 1) * raw_length_mm * kerf * sheets_needed
        + max(0, along - 1) * (across * d_wid) * kerf * sheets_needed
    )
    used_area_mm2 = used_width * used_length * sheets_needed
    actual_material_m2 = (used_area_mm2 + kerf_area_mm2) / 1_000_000.0
    total_sec = cutting_time_sec + setup_sec + blade_setup_sec
    explanation = f"Süsteem valis tooriku lõikuse, sest detaili paigutus nõuab jaotust nii laiusesse kui pikkusesse otse plaadist. Materjalikulu arvestab ainult detailide tegemiseks kulunud materjali koos saeteega: {actual_material_m2:.2f} m²."
    calc_steps = [
        "Automaatne töörežiim: Tooriku lõikus.",
        f"Orientatsioon {'pööratud' if rotated else 'algne'}.",
        f"Laiuses mahub {across} detaili.",
        f"Pikkuses mahub {along} detaili.",
        f"Ühest toorikust tuleb {pieces_per_sheet} detaili.",
        f"Toorikuid vaja = lae({detail_count} / {pieces_per_sheet}) = {sheets_needed}.",
        "Materjalikulu arvestab ainult kasutatud osa ja saeteed.",
    ]
    scheme = build_cut_scheme([
        f"Võta {sheets_needed} toorikut mõõdus {fmt(raw_width_mm)} x {fmt(raw_length_mm)} mm.",
        f"Lõika kõigepealt laiusesse {across} rida detaililaiusega {fmt(d_wid)} mm.",
        f"Seejärel lõika pikkusesse {along} jaotust detailipikkusega {fmt(d_len)} mm.",
        f"Ühest toorikust saad kokku {pieces_per_sheet} detaili.",
        f"Alles jääb kasutamata {fmt(waste_width)} mm laiuses ja {fmt(waste_length)} mm pikkuses.",
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
        "material_m2": actual_material_m2,
        "single_sheet_m2": single_sheet_area_m2(raw_length_mm, raw_width_mm),
        "warning": warning,
        "scheme": scheme,
        "calc_steps": calc_steps,
        "explanation": explanation,
        "across": across,
        "along": along,
        "kerf_area_m2": kerf_area_mm2 / 1_000_000.0,
        "used_area_m2": used_area_mm2 / 1_000_000.0,
        "valuable_remainder_m2": ((waste_width * raw_length_mm) + (used_width * waste_length)) * sheets_needed / 1_000_000.0,
        "waste_value_penalty": sheets_needed * 1000 + waste_width + waste_length,
    }


def choose_best_result(results):
    valid = [r for r in results if r is not None]
    if not valid:
        return None
    return min(
        valid,
        key=lambda r: (
            r["material_m2"],
            r["sheets_needed"],
            r["waste_value_penalty"],
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
                f"Soovitatud variant, sest see kulutab detailide tegemiseks kõige vähem materjali, "
                f"hoiab täisplaadi väärtust paremini alles ja vähendab jääkide teket. "
                f"Materjalikulu koos saeteega on {r['material_m2']:.2f} m², toorikuid kulub {r['sheets_needed']} tk ja koguaeg on {sec_to_minsec(r['total_sec'])}."
            )
        else:
            other = "3.5 mm ketas" if r["blade"]["blade"] == "5.6 mm" else "5.6 mm ketas"
            r["blade_reason"] = (
                f"Alternatiiv. See variant kasutab {other}, kuid jätab väiksema väärtusega jääke või kulutab rohkem täisplaati. "
                f"Materjalikulu on {r['material_m2']:.2f} m², toorikuid {r['sheets_needed']} tk ja aeg {sec_to_minsec(r['total_sec'])}."
            )


def draw_scheme(result):
    raw_w = result["raw_width_mm"]
    raw_l = result["raw_length_mm"]
    fig_ratio = max(1.0, raw_l / max(raw_w, 1))
    fig, ax = plt.subplots(figsize=(7, min(12, 5 + fig_ratio * 2.2)))

    pad_x = raw_w * 0.08
    pad_y = raw_l * 0.08
    ax.set_xlim(0, raw_w + pad_x)
    ax.set_ylim(raw_l + pad_y, 0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"{result['blade']['blade']} | {result['mode']} | Pööratud: {'Jah' if result.get('orientation_rotated') else 'Ei'}")
    ax.set_xlabel("Laius (mm)")
    ax.set_ylabel("Pikkus (mm)")

    ax.add_patch(plt.Rectangle((0, 0), raw_w, raw_l, facecolor="#dddddd", edgecolor="black", linewidth=2))

    piece_w = result["detail_width_mm"]
    piece_h = result["detail_length_mm"]
    kerf = result["blade"]["kerf_mm"]
    across = result.get("across", 1)
    along = result.get("along", 1)

    shown_x = min(across, 12)
    shown_y = min(along, 12)

    for i in range(shown_x):
        for j in range(shown_y):
            x = i * (piece_w + kerf)
            y = j * (piece_h + kerf)
            if x + piece_w <= raw_w and y + piece_h <= raw_l:
                ax.add_patch(plt.Rectangle((x, y), piece_w, piece_h, facecolor="#b7d7ff", edgecolor="#1f4e79", alpha=0.9))

    used_w = result.get("used_width_mm", 0)
    used_l = result.get("used_length_mm", 0)

    if result.get("waste_width_mm", 0) > 0:
        ax.add_patch(plt.Rectangle((used_w, 0), result["waste_width_mm"], raw_l, facecolor="#fff2b2", edgecolor="#c49b00", alpha=0.7))

    if result.get("waste_length_mm", 0) > 0 and used_w > 0:
        ax.add_patch(plt.Rectangle((0, used_l), used_w, result["waste_length_mm"], facecolor="#ffe0b2", edgecolor="#c77700", alpha=0.65))

    ax.text(raw_w / 2, -raw_l * 0.04, f"Toorik: {fmt(raw_w)} x {fmt(raw_l)} mm", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.text(min(raw_w * 0.03, 30), min(raw_l * 0.06, 120), f"Detail: {fmt(piece_w)} x {fmt(piece_h)} mm", ha="left", va="top", fontsize=9)
    ax.annotate("", xy=(raw_w, raw_l + pad_y * 0.3), xytext=(0, raw_l + pad_y * 0.3), arrowprops=dict(arrowstyle="<->", lw=1.2, color="#444"))
    ax.text(raw_w / 2, raw_l + pad_y * 0.34, f"{fmt(raw_w)} mm", ha="center", va="bottom", fontsize=9)
    ax.annotate("", xy=(raw_w + pad_x * 0.3, raw_l), xytext=(raw_w + pad_x * 0.3, 0), arrowprops=dict(arrowstyle="<->", lw=1.2, color="#444"))
    ax.text(raw_w + pad_x * 0.34, raw_l / 2, f"{fmt(raw_l)} mm", ha="left", va="center", rotation=90, fontsize=9)

    if across > shown_x or along > shown_y:
        ax.text(raw_w * 0.02, raw_l * 0.98, f"Skeemil kuvatakse kuni 12 x 12 detaili, tegelik paigutus: {across} x {along}", ha="left", va="top", fontsize=8, color="#444444")

    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    return fig


def result_rows(result):
    rows = [
        ["Töörežiim", result["mode"]],
        ["Tooriku mõõt", f"{fmt(result['raw_width_mm'])} x {fmt(result['raw_length_mm'])} mm"],
        ["Detail", f"{fmt(result['detail_width_mm'])} x {fmt(result['detail_length_mm'])} mm"],
        ["Tellitud kogus", f"{result['detail_count']} tk"],
        ["Toorikuid vaja", f"{result['sheets_needed']} tk"],
        ["Kulunud materjal", f"{result['material_m2']:.2f} m²"],
        ["Detailide ala", f"{result['used_area_m2']:.2f} m²"],
        ["Saetee kulu", f"{result['kerf_area_m2']:.2f} m²"],
        ["Alles jääv väärtuslik jääk", f"{result['valuable_remainder_m2']:.2f} m²"],
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
    m2.metric("Kulunud materjal", f"{result['material_m2']:.2f} m²")
    m3, m4 = st.columns(2)
    m3.metric("Koguaeg", sec_to_minsec(result["total_sec"]))
    m4.metric("Töörežiim", result["mode"])
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

with st.form("calc_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        thickness_mm = st.selectbox("Paksus mm", THICKNESS_OPTIONS_MM, index=THICKNESS_OPTIONS_MM.index(int(st.session_state.thickness_mm)) if int(st.session_state.thickness_mm) in THICKNESS_OPTIONS_MM else 19)
    with c2:
        raw_width_mm = st.number_input("Tooriku laius mm", min_value=1.0, max_value=MAX_WIDTH_MM, value=float(st.session_state.raw_width_mm), step=1.0)
    with c3:
        raw_length_mm = st.number_input("Tooriku pikkus mm", min_value=1.0, max_value=MAX_LENGTH_MM, value=float(st.session_state.raw_length_mm), step=1.0)

    x1, x2 = st.columns(2)
    with x1:
        detail_width_mm = st.number_input("Detaili laius mm", min_value=1.0, value=float(st.session_state.detail_width_mm), step=1.0)
    with x2:
        detail_length_mm = st.number_input("Detaili pikkus mm", min_value=1.0, value=float(st.session_state.detail_length_mm), step=1.0)

    detail_count = st.number_input("Detailide arv", min_value=1, value=int(st.session_state.detail_count), step=1)
    show_details = st.checkbox("Näita detailset arvutuskäiku", value=st.session_state.show_details)
    submitted = st.form_submit_button("Arvuta", use_container_width=True)

if submitted:
    st.session_state.thickness_mm = int(thickness_mm)
    st.session_state.raw_width_mm = raw_width_mm
    st.session_state.raw_length_mm = raw_length_mm
    st.session_state.detail_width_mm = detail_width_mm
    st.session_state.detail_length_mm = detail_length_mm
    st.session_state.detail_count = int(detail_count)
    st.session_state.show_details = show_details

    error = validate_common(int(thickness_mm), raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, int(detail_count))
    if error:
        st.error(error)
        st.stop()

    results = [make_result(blade, int(thickness_mm), raw_length_mm, raw_width_mm, detail_length_mm, detail_width_mm, int(detail_count)) for blade in BLADES]
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
        f"toorikuid: {best_result['sheets_needed']} tk | kulunud materjal: {best_result['material_m2']:.2f} m² | "
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
        st.write("- Materjalikulu tähendab ainult detailide tegemiseks kulunud materjali koos saeteega.")
        st.write("- Täisplaadi väärtuse hoidmiseks eelistatakse lahendust, mis jätab parema alles jääva osa.")
        st.write("- Ketta soovitus võrdleb kulunud materjali, toorikute arvu, jäägi väärtust ja koguaega.")
        st.write("- 3.5 mm ketas eelistub, kui see säästab materjali või vähendab kogukulu.")
        st.write("- 5.6 mm ketas eelistub, kui ta annab parema töökiiruse või väiksema toorikute arvu ilma materjalikulu oluliselt kasvatamata.")
        st.write(f"- Viimane uuendus: {LAST_UPDATED}")
else:
    st.info("Sisesta andmed ja vajuta Arvuta.")
