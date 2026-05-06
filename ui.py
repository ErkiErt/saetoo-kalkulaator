import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
import streamlit as st
from utils import fmt, offcut_label, sec_to_minsec


def render_result_card(result, label='Tulemus'):
    st.subheader(label)
    blade = result['blade']['blade']
    kerf = result['kerf_mm']
    rot = ' (detailid pööratud)' if result.get('rotated') else ''
    lines = [
        f"**Ketas:** {blade} (karve {kerf} mm){rot}",
        f"**Avatud plaate:** {result['opened_sheet_count']} tk",
        f"**Detaile plaadil:** {result['across']} x {result['along']} = {result['pieces_per_sheet']} tk",
        f"**Lõikeid kokku:** {result['total_cut_count']} (pikk: {result['longitudinal_cut_count']}, rist: {result['cross_cut_count']})",
    ]
    st.markdown('  \n'.join(lines))
    if result.get('partial_piece_count', 0) > 0:
        st.markdown(f"**Osaplaat:** {result['partial_piece_count']} tk ({result['partial_cols']} x {result['partial_rows']})")
    st.markdown('---')
    c1, c2, c3 = st.columns(3)
    c1.metric('Arvutuslik aeg', sec_to_minsec(result['total_sec']))
    ml_t = result.get('ml_predicted_actual_time_sec')
    if ml_t:
        c2.metric('ML prognoos', sec_to_minsec(ml_t))
    c3.metric('Kogukulu (est)', fmt(result['total_estimated_cost_eur'], 2, 'EUR'))
    st.markdown('---')
    st.markdown('##### Materjal ja karved')
    mc1, mc2 = st.columns(2)
    mc1.markdown(
        f"- Net detailide pind: **{fmt(result['net_detail_area_m2'], 3, 'm2')}**\n"
        f"- Karved: **{fmt(result['kerf_area_m2'], 3, 'm2')}**\n"
        f"- Kasutus: **{fmt(result['consumed_area_m2'], 3, 'm2')}**\n"
        f"- Avatud plaat: **{fmt(result['opened_sheet_area_m2'], 3, 'm2')}**"
    )
    mc2.markdown(
        f"- Kasutatav jääk: **{fmt(result['usable_offcut_area_m2'], 3, 'm2')}**\n"
        f"- Praak/kadu: **{fmt(result['non_usable_offcut_area_m2'], 3, 'm2')}**\n"
        f"- Arvestatav materjal: **{fmt(result['material_billable_area_m2'], 3, 'm2')}**"
    )
    st.markdown('---')
    st.markdown('##### Kulu')
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric('Töökulu', fmt(result['estimated_work_cost_eur'], 2, 'EUR'))
    cc2.metric('Mat kulu', fmt(result['material_cost_eur'], 2, 'EUR'))
    cc3.metric('Kokku', fmt(result['total_estimated_cost_eur'], 2, 'EUR'))
    st.markdown('---')
    st.markdown('##### Ajajaotus')
    tc1, tc2, tc3 = st.columns(3)
    tc1.metric('Seadistus', sec_to_minsec(result['setup_sec']))
    tc2.metric('Lõikamine', sec_to_minsec(result['cutting_time_sec']))
    tc3.metric('Käsitlus', sec_to_minsec(result['handling_sec']))
    st.markdown('---')
    st.markdown('##### Jäägid')
    st.markdown(f"- Suurim kasutatav: **{offcut_label(result['largest_usable_offcut'])}**")
    st.markdown(f"- Suurim üldse: **{offcut_label(result['largest_any_offcut'])}**")
    for o in result.get('full_offcuts', []):
        qty_txt = f" x {result['full_sheet_count']} täisplaati" if result['full_sheet_count'] > 1 else ''
        st.markdown(f"- {offcut_label(o)}{qty_txt}")
    for o in result.get('partial_offcuts', []):
        if result.get('partial_sheet_count', 0) > 0:
            st.markdown(f"- {offcut_label(o)} (osaplaat)")
    if result.get('warning'):
        st.warning(result['warning'])
    if result.get('blade_reason'):
        st.info(result['blade_reason'])


def comparison_table(results):
    rows = []
    for r in results:
        if r is None:
            continue
        ml_t = r.get('ml_predicted_actual_time_sec')
        rows.append({
            'Ketas': r['blade']['blade'],
            'Pööratud': 'Jah' if r.get('rotated') else 'Ei',
            'Plaate': r['opened_sheet_count'],
            'Detaile/plaat': r['pieces_per_sheet'],
            'Lõikeid': r['total_cut_count'],
            'Arvutuslik aeg': sec_to_minsec(r['total_sec']),
            'ML prognoos': sec_to_minsec(ml_t) if ml_t else '—',
            'Töökulu EUR': fmt(r['estimated_work_cost_eur'], 2),
            'Mat kulu EUR': fmt(r['material_cost_eur'], 2),
            'Kokku EUR': fmt(r['total_estimated_cost_eur'], 2),
            'Kasutatav jääk m2': fmt(r['usable_offcut_area_m2'], 3),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def draw_scheme(result, title='Lõikeskeem'):
    raw_w = result['raw_width_mm']
    raw_l = result['raw_length_mm']
    used_w = result['scheme_used_width_mm']
    used_l = result['scheme_used_length_mm']
    piece_n = result['scheme_piece_count']
    cols = result.get('partial_cols') or result['across']
    rows_ = result.get('partial_rows') or result['along']
    kerf = result['kerf_mm']
    pw = result['detail_width_mm']
    pl = result['detail_length_mm']
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_xlim(0, raw_w)
    ax.set_ylim(0, raw_l)
    ax.set_aspect('equal')
    ax.set_title(title)
    ax.add_patch(Rectangle((0, 0), raw_w, raw_l, linewidth=1.2, edgecolor='#555', facecolor='#efefef'))
    drawn = 0
    for c in range(cols):
        for r in range(rows_):
            if drawn >= piece_n:
                break
            x = c * (pw + kerf)
            y = r * (pl + kerf)
            ax.add_patch(Rectangle((x, y), pw, pl, linewidth=0.5, edgecolor='#0d47a1', facecolor='#90caf9', alpha=0.85))
            drawn += 1
    for offcut in result.get('partial_offcuts', []) + result.get('full_offcuts', []):
        if not offcut.get('usable'):
            continue
        if offcut.get('name') == 'Kuljeriba':
            ox, oy, ow, oh = used_w, 0, raw_w - used_w, raw_l
        else:
            ox, oy, ow, oh = 0, used_l, used_w, raw_l - used_l
        ax.add_patch(Rectangle((ox, oy), ow, oh, linewidth=0.5, edgecolor='#558b2f', facecolor='#c5e1a5', alpha=0.6))
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
