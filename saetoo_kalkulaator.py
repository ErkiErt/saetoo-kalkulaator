from pathlib import Path

SRC = Path('saetoo_kalkulaator_ml_parandatud.py')
OUT = Path('saetoo_kalkulaator_ml_valmis.py')

text = SRC.read_text(encoding='utf-8')

replacements = [
    (
        '"blade": "5.6 mm",\n    "kerf_mm": 5.6,',
        '"blade": "5.5 mm",\n    "kerf_mm": 5.5,',
    ),
    (
        '"detail_count": "",\n    "trim_edges": True,',
        '"detail_count": "",\n    "hourly_rate_eur": "60",\n    "material_price_m2_eur": "25",\n    "trim_edges": True,',
    ),
    (
        '''def clear_calc_inputs():
    st.session_state.thickness_mm = 20
    st.session_state.raw_width_mm = ""
    st.session_state.raw_length_mm = ""
    st.session_state.detail_length_mm = ""
    st.session_state.detail_width_mm = ""
    st.session_state.detail_count = ""
    st.session_state.trim_edges = True
    st.session_state.last_results = None
    st.session_state.best_result = None
    st.session_state.pending_save_row = None
''',
        '''def clear_calc_inputs():
    reset_values = {
        "thickness_mm": 20,
        "raw_width_mm": "",
        "raw_length_mm": "",
        "detail_length_mm": "",
        "detail_width_mm": "",
        "detail_count": "",
        "hourly_rate_eur": "60",
        "material_price_m2_eur": "25",
        "trim_edges": True,
        "last_results": None,
        "best_result": None,
        "pending_save_row": None,
    }
    for key, value in reset_values.items():
        st.session_state[key] = value
''',
    ),
    (
        '''def clear_worklog_inputs():
    st.session_state.order_id = ""
    st.session_state.operator = ""
    st.session_state.material = ""
    st.session_state.machine_id = ""
    st.session_state.shift = ""
    st.session_state.actual_time_min = ""
    st.session_state.was_scrap = False
    st.session_state.scrap_reason = ""
    st.session_state.rework_time_min = ""
    st.session_state.pending_save_row = None
''',
        '''def clear_worklog_inputs():
    reset_values = {
        "order_id": "",
        "operator": "",
        "material": "",
        "machine_id": "",
        "shift": "",
        "actual_time_min": "",
        "was_scrap": False,
        "scrap_reason": "",
        "rework_time_min": "",
        "pending_save_row": None,
    }
    for key, value in reset_values.items():
        st.session_state[key] = value
''',
    ),
    (
        '''def area_m2(width_mm, length_mm):
''',
        '''def calc_cost_eur(seconds, hourly_rate_eur):
    if seconds is None or pd.isna(seconds):
        return None
    return max(0.0, float(seconds)) / 3600.0 * float(hourly_rate_eur)


def calc_material_cost_eur(area_m2, material_price_m2_eur):
    if area_m2 is None or pd.isna(area_m2):
        return None
    return max(0.0, float(area_m2)) * float(material_price_m2_eur)


def enrich_result_with_costs(result, hourly_rate_eur, material_price_m2_eur):
    if result is None:
        return None
    result["hourly_rate_eur"] = hourly_rate_eur
    result["material_price_m2_eur"] = material_price_m2_eur
    result["estimated_work_cost_eur"] = calc_cost_eur(result["total_sec"], hourly_rate_eur)
    result["ml_estimated_work_cost_eur"] = calc_cost_eur(result.get("ml_predicted_actual_time_sec"), hourly_rate_eur)
    result["material_billable_area_m2"] = result["consumed_area_m2"] + result["non_usable_offcut_area_m2"]
    result["material_cost_eur"] = calc_material_cost_eur(result["material_billable_area_m2"], material_price_m2_eur)
    result["total_estimated_cost_eur"] = (result.get("estimated_work_cost_eur") or 0.0) + (result.get("material_cost_eur") or 0.0)
    result["ml_total_estimated_cost_eur"] = (
        (result.get("ml_estimated_work_cost_eur") or 0.0) + (result.get("material_cost_eur") or 0.0)
        if result.get("ml_estimated_work_cost_eur") is not None
        else None
    )
    return result


def area_m2(width_mm, length_mm):
''',
    ),
    (
        '''        detail_count = st.text_input("Detailide arv", value=st.session_state.detail_count, placeholder="Nt 20")
        trim_edges = st.checkbox("Arvesta Ã¤Ã¤retrimmi / vÃ¤liste eralduslÃµigetega", value=st.session_state.trim_edges)
''',
        '''        detail_count = st.text_input("Detailide arv", value=st.session_state.detail_count, placeholder="Nt 20")
        price1, price2 = st.columns(2)
        with price1:
            hourly_rate_eur = st.text_input("Tunnihind â‚¬/h", value=st.session_state.hourly_rate_eur, placeholder="Nt 60")
        with price2:
            material_price_m2_eur = st.text_input("Materjali ruuduhind â‚¬/mÂ²", value=st.session_state.material_price_m2_eur, placeholder="Nt 25")
        trim_edges = st.checkbox("Arvesta Ã¤Ã¤retrimmi / vÃ¤liste eralduslÃµigetega", value=st.session_state.trim_edges)
''',
    ),
    (
        '''            detail_count = int(str(detail_count).strip())
        except ValueError:
''',
        '''            detail_count = int(str(detail_count).strip())
            hourly_rate_eur = parse_float_text(hourly_rate_eur)
            material_price_m2_eur = parse_float_text(material_price_m2_eur)
        except ValueError:
''',
    ),
    (
        '''        st.session_state.detail_count = str(detail_count)
        st.session_state.trim_edges = bool(trim_edges)
''',
        '''        st.session_state.detail_count = str(detail_count)
        st.session_state.hourly_rate_eur = str(hourly_rate_eur)
        st.session_state.material_price_m2_eur = str(material_price_m2_eur)
        st.session_state.trim_edges = bool(trim_edges)
''',
    ),
    (
        '''        if model is not None:
            for r in results:
                if r is not None:
                    r["ml_predicted_actual_time_sec"] = predict_result_time(
                        model, feature_cols, r, thickness_mm
                    )
''',
        '''        if model is not None:
            for r in results:
                if r is not None:
                    r["ml_predicted_actual_time_sec"] = predict_result_time(
                        model, feature_cols, r, thickness_mm
                    )

        for r in results:
            enrich_result_with_costs(r, hourly_rate_eur, material_price_m2_eur)
''',
    ),
    (
        '''    c1, c2, c3 = st.columns(3)
    c1.metric("Avatud plaate", f"{result['opened_sheet_count']} tk")
    c2.metric("Valemi aeg", sec_to_minsec(result["total_sec"]))
    c3.metric("ML tegelik aeg", sec_to_minsec(result.get("ml_predicted_actual_time_sec")))

    c4, c5 = st.columns(2)
    c4.metric("Detailide pind + saetee kadu", f"{result['consumed_area_m2']:.2f} mÂ²")
    c5.metric("Kasutatav jÃ¤Ã¤k", f"{result['usable_offcut_area_m2']:.2f} mÂ²")
''',
        '''    c1, c2, c3 = st.columns(3)
    c1.metric("Avatud plaate", f"{result['opened_sheet_count']} tk")
    c2.metric("Valemi aeg", sec_to_minsec(result["total_sec"]))
    c3.metric("TÃ¤ielik maksumus", f"{result.get('total_estimated_cost_eur', 0):.2f} â‚¬")

    c4, c5, c6 = st.columns(3)
    c4.metric("TÃ¶Ã¶ maksumus", f"{result.get('estimated_work_cost_eur', 0):.2f} â‚¬")
    c5.metric("Materjalikulu", f"{result.get('material_cost_eur', 0):.2f} â‚¬")
    c6.metric("ML kogumaksumus", f"{result['ml_total_estimated_cost_eur']:.2f} â‚¬" if result.get("ml_total_estimated_cost_eur") is not None else "-")
''',
    ),
    (
        '''        ["Mittearvestatav jÃ¤Ã¤k", f"{result['non_usable_offcut_area_m2']:.2f} mÂ²"],
        ["Suurim kasutatav jÃ¤Ã¤k", offcut_label(result["largest_usable_offcut"])],
''',
        '''        ["Mittearvestatav jÃ¤Ã¤k", f"{result['non_usable_offcut_area_m2']:.2f} mÂ²"],
        ["Tunnihind", f"{result.get('hourly_rate_eur', 0):.2f} â‚¬/h"],
        ["Materjali ruuduhind", f"{result.get('material_price_m2_eur', 0):.2f} â‚¬/mÂ²"],
        ["Arvestatav materjalipind", f"{result.get('material_billable_area_m2', 0):.2f} mÂ²"],
        ["TÃ¶Ã¶ maksumus", f"{result.get('estimated_work_cost_eur', 0):.2f} â‚¬"],
        ["Materjalikulu", f"{result.get('material_cost_eur', 0):.2f} â‚¬"],
        ["TÃ¤ielik maksumus", f"{result.get('total_estimated_cost_eur', 0):.2f} â‚¬"],
        ["Suurim kasutatav jÃ¤Ã¤k", offcut_label(result["largest_usable_offcut"])],
''',
    ),
    (
        '''        "estimated_time_sec": best_result["total_sec"],
        "actual_time_sec": actual_time_sec_num,
        "usable_offcut_m2": best_result["usable_offcut_area_m2"],
''',
        '''        "estimated_time_sec": best_result["total_sec"],
        "actual_time_sec": actual_time_sec_num,
        "hourly_rate_eur": best_result.get("hourly_rate_eur"),
        "material_price_m2_eur": best_result.get("material_price_m2_eur"),
        "estimated_work_cost_eur": best_result.get("estimated_work_cost_eur"),
        "ml_estimated_work_cost_eur": best_result.get("ml_estimated_work_cost_eur"),
        "material_billable_area_m2": best_result.get("material_billable_area_m2"),
        "material_cost_eur": best_result.get("material_cost_eur"),
        "total_estimated_cost_eur": best_result.get("total_estimated_cost_eur"),
        "ml_total_estimated_cost_eur": best_result.get("ml_total_estimated_cost_eur"),
        "usable_offcut_m2": best_result["usable_offcut_area_m2"],
''',
    ),
    (
        '''        left, right = st.columns(2)
        with left:
            render_result_card(results[0], best_result["blade"]["blade"])
        with right:
            render_result_card(results[1], best_result["blade"]["blade"])
''',
        '''        ordered_results = [best_result] + [r for r in results if r is not None and r is not best_result]

        if len(ordered_results) == 1:
            render_result_card(ordered_results[0], best_result["blade"]["blade"])
        else:
            left, right = st.columns(2)
            with left:
                render_result_card(ordered_results[0], best_result["blade"]["blade"])
            with right:
                render_result_card(ordered_results[1], best_result["blade"]["blade"])
''',
    ),
]

for old, new in replacements:
    if old not in text:
        print('WARNING: pattern not found:\n', old[:120], '\n')
    else:
        text = text.replace(old, new)

OUT.write_text(text, encoding='utf-8')
print(f'Written: {OUT}')
print('Next step: python -m py_compile saetoo_kalkulaator_ml_valmis.py')
