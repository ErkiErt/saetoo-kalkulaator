import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
import streamlit as st
from utils import fmt, offcut_label, sec_to_minsec


def render_result_card(result, label="Tulemus"):
    st.subheader(label)
    blade = result["blade"]["blade"]
    kerf  = result["kerf_mm"]
    rot   = " (detailid pooratud)" if result.get("rotated") else ""

    st.markdown(
        "**Ketas:** " + blade + " (karve " + str(kerf) + " mm)" + rot + "  \n"
        "**Avatud plaate:** " + str(result["opened_sheet_count"]) + " tk  \n"
        "**Detaile plaadil:** " + str(result["across"]) + " x " + str(result["along"])
        + " = " + str(result["pieces_per_sheet"]) + " tk  \n"
        "**Loikeid kokku:** " + str(result["total_cut_count"])
        + " (pikk: " + str(result["longitudinal_cut_count"])
        + ", rist: " + str(result["cross_cut_count"]) + ")"
    )

    if result.get("partial_piece_count", 0) > 0:
        st.markdown(
            "**Osaplaat:** " + str(result["partial_piece_count"]) + " tk"
            + " (" + str(result["partial_cols"]) + " x " + str(result["partial_rows"]) + ")"
        )

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Arvutuslik aeg", sec_to_minsec(result["total_sec"]))
    ml_t = result.get("ml_predicted_actual_time_sec")
    if ml_t:
        c2.metric("ML prognoos", sec_to_minsec(ml_t))
    c3.metric("Kogukulu (est)", fmt(result["total_estimated_cost_eur"], 2, "EUR"))

    st.markdown("---")
    st.markdown("##### Materjal ja karved")
    mc1, mc2 = st.columns(2)
    mc1.markdown(
        "- Net detailide pind: **" + fmt(result["net_detail_area_m2"], 3, "m2") + "**\n"
        "- Karved: **" + fmt(result["kerf_area_m2"], 3, "m2") + "**\n"
        "- Kasutus: **" + fmt(result["consumed_area_m2"], 3, "m2") + "**\n"
        "- Avatud plaat: **" + fmt(result["opened_sheet_area_m2"], 3, "m2") + "**"
    )
    mc2.markdown(
        "- Kasutatav jaak: **" + fmt(result["usable_offcut_area_m2"], 3, "m2") + "**\n"
        "- Praak/kadu: **" + fmt(result["non_usable_offcut_area_m2"], 3, "m2") + "**\n"
        "- Arvetav materjal: **" + fmt(result["material_billable_area_m2"], 3, "m2") + "**"
    )

    st.markdown("---")
    st.markdown("##### Kulu")
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Tookulu", fmt(result["estimated_work_cost_eur"], 2, "EUR"))
    cc2.metric("Mat kulu", fmt(result["material_cost_eur"], 2, "EUR"))
    cc3.metric("Kokku", fmt(result["total_estimated_cost_eur"], 2, "EUR"))

    st.markdown("---")
    st.markdown("##### Ajajaotus")
    tc1, tc2, tc3 = st.columns(3)
    tc1.metric("Seadistus",  sec_to_minsec(result["setup_sec"]))
    tc2.metric("Lõikamine",  sec_to_minsec(result["cutting_time_sec"]))
    tc3.metric("Kasitlus",   sec_to_minsec(result["handling_sec"]))

    st.markdown("---")
    st.markdown("##### Jaagid")
    st.markdown("- Suurim kasutatav: **" + offcut_label(result["largest_usable_offcut"]) + "**")
    st.markdown("- Suurim uldse: **" + offcut_label(result["largest_any_offcut"]) + "**")
    for o in result.get("full_offcuts", []):
        qty_txt = (" x " + str(result["full_sheet_count"]) + " taisplaati"
                   if result["full_sheet_count"] > 1 else "")
        st.markdown("  - " + offcut_label(o) + qty_txt)
    for o in result.get("partial_offcuts", []):
        if result.get("partial_sheet_count", 0) > 0:
            st.markdown("  - " + offcut_label(o) + " (osaplaat)")

    if result.get("warning"):
        st.warning(result["warning"])
    if result.get("blade_reason"):
        st.info(result["blade_reason"])


def comparison_table(results):
    rows = []
    for r in results:
        if r is None:
            continue
        ml_t = r.get("ml_predicted_actual_time_sec")
        rows.append({
            "Ketas": r["blade"]["blade"],
            "Pooratud": "Jah" if r.get("rotated") else "Ei",
            "Plaate": r["opened_sheet_count"],
            "Detaile/plaat": r["pieces_per_sheet"],
            "Loikeid": r["total_cut_count"],
            "Arvutuslik aeg": sec_to_minsec(r["total_sec"]),
            "ML prognoos": sec_to_minsec(ml_t) if ml_t else "—",
            "Tookulu EUR": fmt(r["estimated_work_cost_eur"], 2),
            "Mat kulu EUR": fmt(r["material_cost_eur"], 2),
            "Kokku EUR": fmt(r["total_estimated_cost_eur"], 2),
            "Kasutatav jaak m2": fmt(r["usable_offcut_area_m2"], 3),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def draw_scheme(result, title="Loikeskeem"):
    raw_w   = result["raw_width_mm"]
    raw_l   = result["raw_length_mm"]
    used_w  = result["scheme_used_width_mm"]
    used_l  = result["scheme_used_length_mm"]
    piece_n = result["scheme_piece_count"]
    cols    = result.get("partial_cols") or result["across"]
    rows_   = result.get("partial_rows") or result["along"]
    kerf    = result["kerf_mm"]
    pw      = result["detail_width_mm"]
    pl      = result["detail_length_mm"]

    scale   = min(6.0 / raw_w, 4.0 / raw_l)
    fig_w   = max(4, raw_w * scale * 1000 / 100)
    fig_h   = max(3, raw_l * scale * 1000 / 100)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#1e1e1e")
    ax.set_xlim(0, raw_w); ax.set_ylim(0, raw_l)
    ax.set_aspect("equal")
    ax.set_title(title, color="white", fontsize=10)
    ax.tick_params(colors="gray", labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor("#444")

    ax.add_patch(Rectangle((0, 0), raw_w, raw_l,
                            linewidth=1.5, edgecolor="#555", facecolor="#2a2a2a"))
    drawn = 0
    for c in range(cols):
        for r in range(rows_):
            if drawn >= piece_n:
                break
            x = c * (pw + kerf)
            y = r * (pl + kerf)
            ax.add_patch(Rectangle((x, y), pw, pl,
                                    linewidth=0.5, edgecolor="#00bcd4",
                                    facecolor="#004d5a", alpha=0.85))
            drawn += 1

    for offcut in result.get("partial_offcuts", []) + result.get("full_offcuts", []):
        if not offcut["usable"]:
            continue
        if offcut["name"] == "Kuljeriba":
            ox, oy, ow, oh = used_w, 0, raw_w - used_w, raw_l
        else:
            ox, oy, ow, oh = 0, used_l, used_w, raw_l - used_l
        ax.add_patch(Rectangle((ox, oy), ow, oh,
                                linewidth=0.5, edgecolor="#8bc34a",
                                facecolor="#2e4a1a", alpha=0.5))

    ax.text(raw_w * 0.5, -raw_l * 0.04, str(int(raw_w)) + " mm",
            ha="center", va="top", color="gray", fontsize=7)
    ax.text(-raw_w * 0.04, raw_l * 0.5, str(int(raw_l)) + " mm",
            ha="right", va="center", color="gray", fontsize=7, rotation=90)

    plt.tight_layout()
    st.pyplot(fig, use_container_width=False)
    plt.close(fig)
