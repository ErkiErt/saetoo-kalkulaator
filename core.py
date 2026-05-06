import math
from dataclasses import dataclass

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

MIN_SMALL_BLADE_COST_SAVING_EUR = 5.0
MIN_SMALL_BLADE_TIME_SAVING_SEC = 10 * 60
MIN_SMALL_BLADE_USABLE_OFFCUT_GAIN_M2 = 0.15

LARGE_BLADE = {"blade": "5.6 mm", "kerf_mm": 5.6, "max_stack_mm": 80.0, "is_default": True}
SMALL_BLADE = {"blade": "3.1 mm", "kerf_mm": 3.1, "max_stack_mm": 30.0, "is_default": False}
BLADES = [LARGE_BLADE, SMALL_BLADE]
THICKNESS_OPTIONS_MM = list(range(1, 13)) + [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]


@dataclass
class CalcInput:
    thickness_mm: int
    raw_width_mm: float
    raw_length_mm: float
    detail_width_mm: float
    detail_length_mm: float
    detail_count: int
    trim_edges: bool
    hourly_rate_eur: float
    material_price_m2_eur: float


def area_m2(width_mm, length_mm):
    if width_mm <= 0 or length_mm <= 0:
        return 0.0
    return (width_mm * length_mm) / 1_000_000.0

def get_sec_per_meter(thickness_mm):
    if 1 <= thickness_mm <= 20:   return 6.0
    if 20 < thickness_mm <= 40:   return 7.5
    if 40 < thickness_mm <= 50:   return 10.0
    if 50 < thickness_mm <= 60:   return 12.0
    if 60 < thickness_mm <= 70:   return 18.0
    if 70 < thickness_mm <= 80:   return 24.0
    if 80 < thickness_mm <= 90:   return 36.0
    return None

def max_pieces_in_length(total_len, piece_len, kerf):
    if total_len <= 0 or piece_len <= 0:
        return 0
    return max(0, math.floor((total_len + kerf) / (piece_len + kerf)))

def used_size_mm(piece_count, piece_size, kerf):
    if piece_count <= 0:
        return 0.0
    return piece_count * piece_size + (piece_count - 1) * kerf

def needs_cross_cut(raw_length, used_length):
    return used_length < raw_length - 0.001

def offcut_is_usable(width_mm, length_mm):
    short = min(width_mm, length_mm)
    long_ = max(width_mm, length_mm)
    return (short >= MIN_USABLE_OFFCUT_WIDTH_MM
            and long_ >= MIN_USABLE_OFFCUT_LENGTH_MM
            and area_m2(width_mm, length_mm) >= MIN_USABLE_OFFCUT_AREA_M2)

def get_simple_offcuts(raw_w, raw_l, used_w, used_l):
    offcuts = []
    side_w = max(0.0, raw_w - used_w)
    end_l  = max(0.0, raw_l - used_l)
    if side_w > 0:
        offcuts.append({"name": "Kuljeriba", "width_mm": side_w, "length_mm": raw_l,
                        "area_m2": area_m2(side_w, raw_l),
                        "usable": offcut_is_usable(side_w, raw_l)})
    if end_l > 0 and used_w > 0:
        offcuts.append({"name": "Otsajaak", "width_mm": used_w, "length_mm": end_l,
                        "area_m2": area_m2(used_w, end_l),
                        "usable": offcut_is_usable(used_w, end_l)})
    return offcuts

def summarize_offcuts(full_offcuts, partial_offcuts, full_n, partial_n):
    usable_area = 0.0
    all_offcuts = []
    for o in full_offcuts:
        oc = o.copy(); oc["quantity"] = full_n; all_offcuts.append(oc)
        if o["usable"]: usable_area += o["area_m2"] * full_n
    for o in partial_offcuts:
        oc = o.copy(); oc["quantity"] = partial_n; all_offcuts.append(oc)
        if o["usable"]: usable_area += o["area_m2"] * partial_n
    usable = [o for o in all_offcuts if o["usable"] and o["quantity"] > 0]
    existing = [o for o in all_offcuts if o["quantity"] > 0]
    largest_usable = max(usable, key=lambda o: o["area_m2"]) if usable else None
    largest_any = max(existing, key=lambda o: o["area_m2"]) if existing else None
    return usable_area, largest_usable, largest_any

def validate_input_values(inp):
    errors = []
    if inp.thickness_mm not in THICKNESS_OPTIONS_MM:
        errors.append("Paksus peab olema lubatud valikust.")
    if inp.raw_length_mm <= 0 or inp.raw_length_mm > MAX_LENGTH_MM:
        errors.append(f"Tooriku pikkus peab olema vahemikus 1 kuni {int(MAX_LENGTH_MM)} mm.")
    if inp.raw_width_mm <= 0 or inp.raw_width_mm > MAX_WIDTH_MM:
        errors.append(f"Tooriku laius peab olema vahemikus 1 kuni {int(MAX_WIDTH_MM)} mm.")
    if inp.detail_length_mm <= 0 or inp.detail_width_mm <= 0:
        errors.append("Detaili moodud peavad olema suuremad kui 0 mm.")
    if inp.detail_count < 1:
        errors.append("Detailide arv peab olema vahemalt 1.")
    if inp.hourly_rate_eur < 0:
        errors.append("Tunnihind ei tohi olla negatiivne.")
    if inp.material_price_m2_eur < 0:
        errors.append("Materjali hind ei tohi olla negatiivne.")
    if get_sec_per_meter(inp.thickness_mm) is None:
        errors.append("Paksuse vahemik peab olema 1 kuni 90 mm.")
    return errors

def build_partial_layout_options(partial_n, max_across, max_along,
                                  piece_w, piece_l, kerf, raw_w, raw_l):
    options = []
    for cols in range(1, min(max_across, partial_n) + 1):
        rows = math.ceil(partial_n / cols)
        if rows > max_along:
            continue
        uw = used_size_mm(cols, piece_w, kerf)
        ul = used_size_mm(rows, piece_l, kerf)
        if uw > raw_w or ul > raw_l:
            continue
        offcuts = get_simple_offcuts(raw_w, raw_l, uw, ul)
        usable = sum(o["area_m2"] for o in offcuts if o["usable"])
        theoretical = max(0.0, area_m2(raw_w, raw_l) - area_m2(uw, ul))
        non_usable = max(0.0, theoretical - usable)
        options.append({"cols": cols, "rows": rows,
                        "used_width_mm": uw, "used_length_mm": ul,
                        "usable_offcut_area_m2": usable,
                        "non_usable_offcut_area_m2": non_usable,
                        "offcuts": offcuts})
    if not options:
        return None
    options.sort(key=lambda x: (-x["usable_offcut_area_m2"],
                                  x["non_usable_offcut_area_m2"],
                                  x["used_width_mm"] * x["used_length_mm"]))
    return options[0]

def _cross_cut_count(along, needs, trim_edges):
    if not needs:
        return 0
    if trim_edges:
        return along
    return max(0, along - 1)

def build_orientation_result(blade, inp, dw, dl):
    if inp.thickness_mm > blade["max_stack_mm"]:
        return None
    kerf = blade["kerf_mm"]
    spm = get_sec_per_meter(inp.thickness_mm)

    across = max_pieces_in_length(inp.raw_width_mm, dw, kerf)
    along  = max_pieces_in_length(inp.raw_length_mm, dl, kerf)
    pps    = across * along
    if pps <= 0:
        return None

    full_n    = inp.detail_count // pps
    partial_n = inp.detail_count % pps
    partial_sheet = 1 if partial_n > 0 else 0
    opened    = full_n + partial_sheet

    full_uw = used_size_mm(across, dw, kerf)
    full_ul = used_size_mm(along,  dl, kerf)

    long_full  = across if inp.trim_edges else max(0, across - 1)
    cross_full = _cross_cut_count(along, needs_cross_cut(inp.raw_length_mm, full_ul), inp.trim_edges)
    kerf_area_full = (long_full * inp.raw_length_mm * kerf
                      + cross_full * full_uw * kerf)

    partial_uw = partial_ul = 0.0
    partial_cols = partial_rows = 0
    partial_offcuts = []
    kerf_area_partial = 0.0
    long_partial = cross_partial = 0

    if partial_n > 0:
        pl = build_partial_layout_options(partial_n, across, along,
                                          dw, dl, kerf, inp.raw_width_mm, inp.raw_length_mm)
        if pl is None:
            return None
        partial_cols = pl["cols"]; partial_rows = pl["rows"]
        partial_uw   = pl["used_width_mm"]; partial_ul = pl["used_length_mm"]
        partial_offcuts = pl["offcuts"]
        long_partial  = partial_cols if inp.trim_edges else max(0, partial_cols - 1)
        cross_partial = _cross_cut_count(partial_rows, needs_cross_cut(inp.raw_length_mm, partial_ul), inp.trim_edges)
        kerf_area_partial = (long_partial * inp.raw_length_mm * kerf
                             + cross_partial * partial_uw * kerf)

    net_area   = (inp.detail_count * dw * dl) / 1_000_000.0
    kerf_area  = (full_n * kerf_area_full + partial_sheet * kerf_area_partial) / 1_000_000.0
    consumed   = net_area + kerf_area
    sheet_area = area_m2(inp.raw_width_mm, inp.raw_length_mm)
    opened_area = opened * sheet_area
    theoretical_offcut = max(0.0, opened_area - consumed)

    full_offcuts = get_simple_offcuts(inp.raw_width_mm, inp.raw_length_mm, full_uw, full_ul)
    usable_offcut, largest_usable, largest_any = summarize_offcuts(
        full_offcuts, partial_offcuts, full_n, partial_sheet)
    non_usable_offcut = max(0.0, theoretical_offcut - usable_offcut)

    scheme_uw  = partial_uw  if partial_n > 0 else full_uw
    scheme_ul  = partial_ul  if partial_n > 0 else full_ul
    scheme_pcs = partial_n   if partial_n > 0 else pps

    long_total  = full_n * long_full  + partial_sheet * long_partial
    cross_total = full_n * cross_full + partial_sheet * cross_partial
    cuts_total  = long_total + cross_total

    fwd_long  = (full_n * (inp.raw_length_mm / 1000) * spm * long_full
                 + partial_sheet * (inp.raw_length_mm / 1000) * spm * long_partial)
    fwd_cross = (full_n * (full_uw / 1000) * spm * cross_full
                 + partial_sheet * (partial_uw / 1000) * spm * cross_partial)
    fwd_time  = fwd_long + fwd_cross
    ret_time  = fwd_time * CUT_RETURN_FACTOR
    cut_time  = fwd_time + ret_time

    setup_sec   = BASE_SETUP_SEC + (SMALL_BLADE_SWITCH_SEC if not blade["is_default"] else 0)
    hps         = BASE_HANDLING_PER_SHEET_SEC + sheet_area * HANDLING_PER_M2_SEC
    hfactor     = THIN_MATERIAL_HANDLING_FACTOR if inp.thickness_mm < 10 else 1.0
    handling_sec = (opened * hps
                    + long_total * RIP_HANDLING_PER_CUT_SEC
                    + (PARTIAL_SHEET_EXTRA_SEC if partial_sheet else 0)) * hfactor
    total_sec   = cut_time + setup_sec + handling_sec

    bill_area   = consumed + non_usable_offcut
    work_cost   = (total_sec / 3600) * inp.hourly_rate_eur
    mat_cost    = bill_area * inp.material_price_m2_eur
    total_cost  = work_cost + mat_cost

    warning = None
    if dw < 20:
        warning = "Hoiatus: alla 20 mm detaili/riba puhul voivad masina kapad segada."

    return {
        "blade": blade, "trim_edges": inp.trim_edges,
        "raw_width_mm": inp.raw_width_mm, "raw_length_mm": inp.raw_length_mm,
        "input_detail_width_mm": dw, "input_detail_length_mm": dl,
        "detail_width_mm": dw, "detail_length_mm": dl,
        "detail_count": inp.detail_count,
        "across": across, "along": along, "pieces_per_sheet": pps,
        "opened_sheet_count": opened,
        "full_sheet_count": full_n, "partial_sheet_count": partial_sheet,
        "partial_piece_count": partial_n,
        "partial_cols": partial_cols, "partial_rows": partial_rows,
        "net_detail_area_m2": net_area, "kerf_area_m2": kerf_area,
        "consumed_area_m2": consumed, "opened_sheet_area_m2": opened_area,
        "theoretical_offcut_area_m2": theoretical_offcut,
        "usable_offcut_area_m2": usable_offcut,
        "non_usable_offcut_area_m2": non_usable_offcut,
        "largest_usable_offcut": largest_usable, "largest_any_offcut": largest_any,
        "full_offcuts": full_offcuts, "partial_offcuts": partial_offcuts,
        "longitudinal_cut_count": long_total, "cross_cut_count": cross_total,
        "total_cut_count": cuts_total,
        "longitudinal_time_sec": fwd_long, "cross_time_sec": fwd_cross,
        "forward_cutting_time_sec": fwd_time, "return_travel_time_sec": ret_time,
        "cutting_time_sec": cut_time, "setup_sec": setup_sec,
        "handling_sec": handling_sec, "handling_per_sheet_sec": hps,
        "handling_factor": hfactor, "total_sec": total_sec,
        "scheme_used_width_mm": scheme_uw, "scheme_used_length_mm": scheme_ul,
        "scheme_piece_count": scheme_pcs, "kerf_mm": kerf, "warning": warning,
        "ml_predicted_actual_time_sec": None,
        "hourly_rate_eur": inp.hourly_rate_eur,
        "material_price_m2_eur": inp.material_price_m2_eur,
        "material_billable_area_m2": bill_area,
        "estimated_work_cost_eur": work_cost,
        "material_cost_eur": mat_cost,
        "total_estimated_cost_eur": total_cost,
    }

def result_sort_key(r):
    return (r["opened_sheet_count"], r["total_estimated_cost_eur"],
            r["total_sec"], r["total_cut_count"],
            -r["usable_offcut_area_m2"], r["non_usable_offcut_area_m2"],
            0 if r["blade"]["is_default"] else 1)

def result_sort_key_ml(r):
    pred = r.get("ml_predicted_actual_time_sec") or r["total_sec"]
    return (r["opened_sheet_count"], r["total_estimated_cost_eur"],
            pred, r["total_cut_count"],
            -r["usable_offcut_area_m2"], r["non_usable_offcut_area_m2"],
            0 if r["blade"]["is_default"] else 1)

def choose_best_orientation_result(results):
    valid = [r for r in results if r is not None]
    return min(valid, key=result_sort_key) if valid else None

def choose_best_result(results):
    valid = [r for r in results if r is not None]
    if not valid: return None
    large = next((r for r in valid if r["blade"]["is_default"]), None)
    small = next((r for r in valid if not r["blade"]["is_default"]), None)
    if large is None: return small
    if small is None: return large
    if small["opened_sheet_count"] < large["opened_sheet_count"]: return small
    if large["opened_sheet_count"] < small["opened_sheet_count"]: return large
    cost_save   = large["total_estimated_cost_eur"] - small["total_estimated_cost_eur"]
    time_save   = large["total_sec"] - small["total_sec"]
    offcut_gain = small["usable_offcut_area_m2"] - large["usable_offcut_area_m2"]
    has_benefit = (cost_save   >= MIN_SMALL_BLADE_COST_SAVING_EUR
                   or time_save   >= MIN_SMALL_BLADE_TIME_SAVING_SEC
                   or offcut_gain >= MIN_SMALL_BLADE_USABLE_OFFCUT_GAIN_M2)
    return small if has_benefit else large

def choose_best_result_ml(results):
    valid = [r for r in results if r is not None]
    return min(valid, key=result_sort_key_ml) if valid else None

def build_best_result_for_blade(blade, inp):
    normal  = build_orientation_result(blade, inp, inp.detail_width_mm,  inp.detail_length_mm)
    rotated = build_orientation_result(blade, inp, inp.detail_length_mm, inp.detail_width_mm)
    if normal  is not None: normal["rotated"]  = False
    if rotated is not None: rotated["rotated"] = True
    return choose_best_orientation_result([normal, rotated])

def add_blade_reasons(results, best):
    from utils import sec_to_minsec
    for r in results:
        if r is None:
            continue
        orient = "pooratud detailiga" if r.get("rotated") else "pooramata detailiga"
        trim   = "aaretrimmi arvestusega" if r["trim_edges"] else "ilma aaretrimmi arvestuseta"
        prefix = "Soovitatud variant" if r is best else "Alternatiiv"
        ml_t   = r.get("ml_predicted_actual_time_sec")
        ml_part = (f", ML prognoos {sec_to_minsec(ml_t)}") if ml_t else ""
        r["blade_reason"] = (
            f"{prefix}: {orient}, {trim}, avatud plaate {r['opened_sheet_count']} tk, "
            f"kogukulu {r['total_estimated_cost_eur']:.2f} EUR, "
            f"loikeid {r['total_cut_count']}{ml_part}."
        )
