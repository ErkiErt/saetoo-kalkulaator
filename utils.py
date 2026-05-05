def parse_float_text(text, default=0.0):
    try:
        return float(str(text).strip().replace(",", "."))
    except (ValueError, TypeError):
        return default

def parse_optional_float_text(text):
    t = str(text).strip().replace(",", ".") if text else ""
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None

def sec_to_minsec(seconds):
    if seconds is None:
        return "—"
    total = int(round(seconds))
    m, s = divmod(abs(total), 60)
    sign = "-" if seconds < 0 else ""
    return f"{sign}{m} min {s:02d} sek"

def fmt(value, decimals=2, unit=""):
    if value is None:
        return "—"
    formatted = f"{value:,.{decimals}f}".replace(",", " ")
    return (formatted + " " + unit).strip()

def offcut_label(offcut):
    if offcut is None:
        return "—"
    usable_txt = "kasutatav" if offcut["usable"] else "praak"
    qty = offcut.get("quantity", 1)
    qty_txt = f" x {qty} tk" if qty > 1 else ""
    return (
        f"{offcut['name']}{qty_txt}: "
        f"{int(offcut['width_mm'])} x {int(offcut['length_mm'])} mm "
        f"({offcut['area_m2']:.3f} m2) — {usable_txt}"
    )
