import streamlit as st
from core import BLADES, THICKNESS_OPTIONS_MM, CalcInput, add_blade_reasons, build_best_result_for_blade, choose_best_result, choose_best_result_ml, validate_input_values
from history import HISTORY_FILE, build_pending_save_row, load_history, normalize_history_df, save_history_row
from ml import ML_MAX_ACCEPTABLE_MAE_SEC, ML_MIN_ROWS_TO_DECIDE, ML_MIN_ROWS_TO_TRAIN, SKLEARN_AVAILABLE, get_trained_model, predict_result_time
from ui import comparison_table, draw_scheme, render_result_card
from utils import parse_float_text, parse_optional_float_text, sec_to_minsec

st.set_page_config(page_title='Saetöö kalkulaator', layout='wide', page_icon='🪚')

DEFAULTS = {
    'thickness_mm': 18,
    'raw_width_mm': '1220',
    'raw_length_mm': '2440',
    'detail_width_mm': '100',
    'detail_length_mm': '500',
    'detail_count': 10,
    'trim_edges': True,
    'hourly_rate_eur': 45.0,
    'material_price_m2_eur': 0.0,
    'notes': '',
    'best_result': None,
    'all_results': [],
    'calc_done': False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.title('🪚 Saetöö kalkulaator')
tab_calc, tab_log, tab_history, tab_ml = st.tabs(['Arvutus', 'Töölogi', 'Ajalugu', 'ML mudel'])

with tab_calc:
    with st.form('calc_form'):
        st.subheader('Sisesta mõõdud')
        col_a, col_b = st.columns(2)
        with col_a:
            default_thickness = st.session_state.thickness_mm if st.session_state.thickness_mm in THICKNESS_OPTIONS_MM else 18
            st.selectbox('Paksus mm', THICKNESS_OPTIONS_MM, index=THICKNESS_OPTIONS_MM.index(default_thickness), key='thickness_mm')
            st.text_input('Tooriku laius mm', value=str(st.session_state.raw_width_mm), key='raw_width_mm')
            st.text_input('Tooriku pikkus mm', value=str(st.session_state.raw_length_mm), key='raw_length_mm')
        with col_b:
            st.text_input('Detaili laius mm', value=str(st.session_state.detail_width_mm), key='detail_width_mm')
            st.text_input('Detaili pikkus mm', value=str(st.session_state.detail_length_mm), key='detail_length_mm')
            st.number_input('Detailide arv', min_value=1, step=1, value=int(st.session_state.detail_count), key='detail_count')
        col_c, col_d = st.columns(2)
        with col_c:
            st.checkbox('Arvesta ääretrimmi', value=bool(st.session_state.trim_edges), key='trim_edges')
            st.number_input('Tunnihind EUR/h', min_value=0.0, step=1.0, value=float(st.session_state.hourly_rate_eur), key='hourly_rate_eur')
        with col_d:
            st.number_input('Materjali hind EUR/m2', min_value=0.0, step=0.5, value=float(st.session_state.material_price_m2_eur), key='material_price_m2_eur')
        submitted = st.form_submit_button('Arvuta', use_container_width=True, type='primary')

    if submitted:
        try:
            inp = CalcInput(
                thickness_mm=int(st.session_state.thickness_mm),
                raw_width_mm=parse_float_text(st.session_state.raw_width_mm),
                raw_length_mm=parse_float_text(st.session_state.raw_length_mm),
                detail_width_mm=parse_float_text(st.session_state.detail_width_mm),
                detail_length_mm=parse_float_text(st.session_state.detail_length_mm),
                detail_count=int(st.session_state.detail_count),
                trim_edges=bool(st.session_state.trim_edges),
                hourly_rate_eur=float(st.session_state.hourly_rate_eur),
                material_price_m2_eur=float(st.session_state.material_price_m2_eur),
            )
            errors = validate_input_values(inp)
            if errors:
                for e in errors:
                    st.error(e)
            else:
                all_results = [build_best_result_for_blade(b, inp) for b in BLADES]
                all_results = [r for r in all_results if r is not None]
                model, mae, n_rows = get_trained_model()
                use_ml = SKLEARN_AVAILABLE and model is not None and n_rows is not None and n_rows >= ML_MIN_ROWS_TO_DECIDE and (mae is None or mae <= ML_MAX_ACCEPTABLE_MAE_SEC)
                for r in all_results:
                    r['ml_predicted_actual_time_sec'] = predict_result_time(r) if use_ml else None
                best = choose_best_result_ml(all_results) if use_ml else choose_best_result(all_results)
                add_blade_reasons(all_results, best)
                st.session_state.best_result = best
                st.session_state.all_results = all_results
                st.session_state.calc_done = True
        except Exception as ex:
            st.error('Arvutusviga: ' + str(ex))

    if st.session_state.calc_done and st.session_state.best_result:
        best = st.session_state.best_result
        visible = [r for r in st.session_state.all_results if r is not None]
        st.markdown('---')
        render_result_card(best, label='Soovitatud variant')
        if len(visible) > 1:
            with st.expander('Variantide võrdlus'):
                comparison_table(visible)
        with st.expander('Lõikeskeem'):
            draw_scheme(best, title='Lõikeskeem – ' + best['blade']['blade'])
        st.markdown('---')
        st.subheader('Salvesta tehtud töö')
        with st.form('save_form'):
            blade_options = [r['blade']['blade'] for r in visible]
            default_idx = next((i for i, r in enumerate(visible) if r is best), 0)
            actual_blade = st.selectbox('Tegelikult kasutatud ketas', blade_options, index=default_idx)
            actual_rotated = st.checkbox('Detailid olid pööratud', value=bool(best.get('rotated', False)))
            actual_time_str = st.text_input('Tegelik aeg (min)', value='')
            rework_time_str = st.text_input('Ümbertöötluse aeg lisaks (min, vabatahtlik)', value='')
            notes_input = st.text_area('Märkused', value=st.session_state.notes)
            save_btn = st.form_submit_button('Salvesta ajalukku', use_container_width=True)
        if save_btn:
            try:
                actual_time_sec = parse_float_text(actual_time_str) * 60 if actual_time_str.strip() else None
                rework_minutes = parse_optional_float_text(rework_time_str)
                rework_time_sec = rework_minutes * 60 if rework_minutes is not None else None
                st.session_state.notes = notes_input
                selected = next((r for r in visible if r['blade']['blade'] == actual_blade), best)
                row = build_pending_save_row(st.session_state, selected, actual_blade, actual_rotated, actual_time_sec, rework_time_sec)
                save_history_row(row)
                st.cache_resource.clear()
                st.success('Töö salvestati. ML mudel uuendatakse järgmisel arvutusel.')
                st.rerun()
            except Exception as ex:
                st.error('Salvestusviga: ' + str(ex))

with tab_log:
    st.subheader('Praeguse seansi töölogi')
    if st.session_state.calc_done and st.session_state.best_result:
        best = st.session_state.best_result
        st.markdown(
            '- **Ketas:** ' + best['blade']['blade'] + '\n' +
            '- **Avatud plaate:** ' + str(best['opened_sheet_count']) + '\n' +
            '- **Detaile plaadil:** ' + str(best['pieces_per_sheet']) + '\n' +
            '- **Lõikeid kokku:** ' + str(best['total_cut_count']) + '\n' +
            '- **Arvutuslik aeg:** ' + sec_to_minsec(best['total_sec']) + '\n' +
            '- **Kogukulu (est):** ' + str(round(best['total_estimated_cost_eur'], 2)) + ' EUR'
        )
    else:
        st.info('Arvutust pole veel tehtud.')

with tab_history:
    st.subheader('Salvestatud tööde ajalugu')
    df_hist = load_history()
    if df_hist.empty:
        st.info('Ajalugu on tühi. Salvesta töid Arvutus vahekaardilt.')
    else:
        st.dataframe(normalize_history_df(df_hist), use_container_width=True)
        if st.button('Kustuta kogu ajalugu'):
            if HISTORY_FILE.exists():
                HISTORY_FILE.unlink()
            st.cache_resource.clear()
            st.success('Ajalugu kustutatud.')
            st.rerun()

with tab_ml:
    st.subheader('ML mudeli olek')
    if not SKLEARN_AVAILABLE:
        st.warning('scikit-learn pole paigaldatud. Käivita: pip install scikit-learn')
    else:
        model, mae, n_rows = get_trained_model()
        st.markdown('- **Ajalookirjeid:** ' + str(n_rows if n_rows else 0))
        st.markdown('- **Minimum treenimiseks:** ' + str(ML_MIN_ROWS_TO_TRAIN))
        st.markdown('- **Minimum otsustamiseks:** ' + str(ML_MIN_ROWS_TO_DECIDE))
        if model is None:
            st.warning('Mudel pole treenitud - vaja vähemalt ' + str(ML_MIN_ROWS_TO_TRAIN) + ' salvestatud kirjet.')
        else:
            if mae is not None:
                mae_txt = str(round(mae)) + ' sek (' + sec_to_minsec(mae) + ')'
                quality = 'Hea' if mae <= ML_MAX_ACCEPTABLE_MAE_SEC else 'Ebatäpne'
            else:
                mae_txt = 'N/A'
                quality = 'N/A'
            st.success('Mudel on treenitud ' + str(n_rows) + ' kirje põhjal.')
            st.markdown('- **MAE (keskmine viga):** ' + mae_txt)
            st.markdown('- **Mudeli kvaliteet:** ' + quality)
            st.markdown('- **Max aktsepteeritav viga:** ' + str(ML_MAX_ACCEPTABLE_MAE_SEC) + ' sek')
