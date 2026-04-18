
import math

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
        return {"blade": "3.5 mm", "kerf_mm": 3.5, "note": "Soovitus: 3.5 mm ketas, et saada rohkem detaile."}
    return {"blade": "5.6 mm", "kerf_mm": 5.6, "note": "3.5 mm ketas ei sobi, kasuta 5.6 mm ketast."}


def max_strips_from_sheet(sheet_width_mm, strip_width_mm, kerf_mm):
    n = 0
    while True:
        test_n = n + 1
        used_width = test_n * strip_width_mm + (test_n - 1) * kerf_mm
        if used_width <= sheet_width_mm:
            n = test_n
        else:
            break
    return n


def suggest_sheets_at_once(thickness_mm):
    if thickness_mm <= 0:
        return 1, "Paksus peab olema suurem kui 0."
    max_sheets = max(1, int(80 // thickness_mm))
    if max_sheets == 1:
        reason = "Paksuse tõttu on mõistlik lõigata üks plaat korraga."
    else:
        reason = f"Kogupaksus lubab korraga lõigata kuni {max_sheets} plaati."
    return max_sheets, reason


def simple_cut_time(length_m, thickness_mm, cut_cycles):
    sec_per_m = get_sec_per_meter(thickness_mm)
    if sec_per_m is None:
        return None
    return length_m * sec_per_m * 2 * cut_cycles


def packaging_time(detail_count):
    return detail_count * 5 if detail_count >= 10 else 0


def simple_job(thickness_mm, length_m, detail_count, cuts_per_detail, add_setup=True):
    cut_cycles = detail_count * cuts_per_detail
    cutting_time_sec = simple_cut_time(length_m, thickness_mm, cut_cycles)
    setup_sec = 20 * 60 if add_setup else 0
    explanation = (
        f"Tellitud detailid: {detail_count} tk. "
        f"Iga detail vajab {cuts_per_detail} lõikust, "
        f"seega tegelikud lõiketsüklid on {cut_cycles}."
    )
    return {
        "mode": "Lihtlõikus",
        "detail_count": detail_count,
        "cuts_per_detail": cuts_per_detail,
        "cut_cycles": cut_cycles,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "total_sec": cutting_time_sec + setup_sec if cutting_time_sec is not None else None,
        "explanation": explanation,
    }


def strip_job(thickness_mm, length_m, detail_count, sheet_width_mm, strip_width_mm):
    blade = recommend_blade(thickness_mm)
    kerf_mm = blade["kerf_mm"]
    max_strips = max_strips_from_sheet(sheet_width_mm, strip_width_mm, kerf_mm)
    sec_per_m = get_sec_per_meter(thickness_mm)
    if sec_per_m is None:
        return None
    sheets_at_once, sheets_reason = suggest_sheets_at_once(thickness_mm)
    if thickness_mm * sheets_at_once > 80:
        sheets_at_once = 1
        sheets_reason = "Paksuse tõttu valiti 1 plaat korraga."
    actual_cut_cycles = math.ceil(detail_count / sheets_at_once)
    cutting_time_sec = length_m * sec_per_m * 2 * actual_cut_cycles
    setup_sec = 20 * 60
    pack_sec = packaging_time(detail_count)
    explanation = (
        f"Tellitud detailid: {detail_count} tk. "
        f"Süsteem soovitab {sheets_at_once} plaati korraga, sest {sheets_reason.lower()} "
        f"Seetõttu on tegelikke lõiketsükleid {actual_cut_cycles}. "
        f"Viimane detail arvestatakse samuti sisse."
    )
    return {
        "mode": "Ribastamine",
        "detail_count": detail_count,
        "blade": blade["blade"],
        "kerf_mm": kerf_mm,
        "blade_note": blade["note"],
        "max_strips_per_sheet": max_strips,
        "sheets_at_once": sheets_at_once,
        "sheets_reason": sheets_reason,
        "allowed": True,
        "cut_cycles": actual_cut_cycles,
        "cutting_time_sec": cutting_time_sec,
        "setup_sec": setup_sec,
        "packaging_sec": pack_sec,
        "total_sec": cutting_time_sec + setup_sec + pack_sec,
        "explanation": explanation,
    }


def sec_to_minsec(seconds):
    if seconds is None:
        return "Ei saa arvutada"
    minutes = int(seconds // 60)
    sec = round(seconds % 60, 1)
    return f"{minutes} min {sec} sek"


def show_result(result):
    if result is None:
        print("Arvutust ei saanud teha.")
        return
    print("\n" + "=" * 60)
    print(f" TÖÖ TÜÜP: {result['mode']}")
    print("=" * 60)
    if result["mode"] == "Lihtlõikus":
        rows = [
            ("Tellitud detailid", f"{result['detail_count']} tk"),
            ("Lõikusi ühe detaili kohta", f"{result['cuts_per_detail']}"),
            ("Tegelikud lõiketsüklid", f"{result['cut_cycles']}"),
            ("Lõikeaeg", sec_to_minsec(result['cutting_time_sec'])),
            ("Setup", sec_to_minsec(result['setup_sec'])),
            ("Koguaeg", sec_to_minsec(result['total_sec'])),
        ]
    else:
        rows = [
            ("Tellitud detailid", f"{result['detail_count']} tk"),
            ("Ketas", result['blade']),
            ("Saetee", f"{result['kerf_mm']} mm"),
            ("Maks. ribad toorikust", f"{result['max_strips_per_sheet']} tk"),
            ("Soovitatud plaate korraga", f"{result['sheets_at_once']} tk"),
            ("Soovituse põhjus", result['sheets_reason']),
            ("Tegelikud lõiketsüklid", f"{result['cut_cycles']}"),
            ("Lõikeaeg", sec_to_minsec(result['cutting_time_sec'])),
            ("Setup", sec_to_minsec(result['setup_sec'])),
            ("Pakkimine", sec_to_minsec(result['packaging_sec'])),
            ("Koguaeg", sec_to_minsec(result['total_sec'])),
        ]
    width = max(len(k) for k, _ in rows) + 2
    for k, v in rows:
        print(f"{k:<{width}}: {v}")
    print("\nSelgitus:")
    print(result["explanation"])
    if result["mode"] == "Ribastamine":
        print(result["blade_note"])
    print("=" * 60 + "\n")


def run_demo():
    job1 = simple_job(10, 1.5, 1, 2, True)
    show_result(job1)
    job2 = strip_job(10, 2.0, 50, 1000, 94)
    show_result(job2)

if __name__ == "__main__":
    run_demo()
