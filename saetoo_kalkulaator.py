def build_beam_result(
    raw_width_mm,
    raw_length_mm,
    detail_width_mm,
    detail_length_mm,
    detail_count,
    kerf_mm,
    sec_per_m,
):
    across = max_pieces_in_length(raw_width_mm, detail_width_mm, kerf_mm)
    along = max_pieces_in_length(raw_length_mm, detail_length_mm, kerf_mm)

    if across <= 0 or along <= 0:
        return None

    pieces_per_sheet = across * along
    full_pattern_count = detail_count // pieces_per_sheet
    partial_piece_count = detail_count % pieces_per_sheet
    partial_pattern_count = 1 if partial_piece_count > 0 else 0
    opened_sheet_count = full_pattern_count + partial_pattern_count

    full_used_width_mm = used_size_mm(across, detail_width_mm, kerf_mm)
    full_used_length_mm = used_size_mm(along, detail_length_mm, kerf_mm)

    rip_cut_count_full = max(0, across - 1)
    cross_cut_count_full = across * max(0, along - 1)

    rip_kerf_area_full_mm2 = rip_cut_count_full * raw_length_mm * kerf_mm
    cross_kerf_area_full_mm2 = cross_cut_count_full * detail_width_mm * kerf_mm
    kerf_area_full_mm2 = rip_kerf_area_full_mm2 + cross_kerf_area_full_mm2

    net_detail_area_full_mm2 = pieces_per_sheet * detail_width_mm * detail_length_mm
    consumed_area_full_mm2 = net_detail_area_full_mm2 + kerf_area_full_mm2

    partial_used_width_mm = 0.0
    partial_used_length_mm = 0.0
    rip_cut_count_partial = 0
    cross_cut_count_partial = 0
    kerf_area_partial_mm2 = 0.0
    net_detail_area_partial_mm2 = partial_piece_count * detail_width_mm * detail_length_mm

    if partial_piece_count > 0:
        full_columns_partial = partial_piece_count // along
        remainder_in_last_column = partial_piece_count % along

        if remainder_in_last_column == 0:
            partial_columns = full_columns_partial
            partial_rows_last = 0
        else:
            partial_columns = full_columns_partial + 1
            partial_rows_last = remainder_in_last_column

        partial_used_width_mm = used_size_mm(partial_columns, detail_width_mm, kerf_mm)

        if full_columns_partial > 0:
            partial_used_length_mm = used_size_mm(along, detail_length_mm, kerf_mm)

        if partial_rows_last > 0:
            last_col_length_mm = used_size_mm(partial_rows_last, detail_length_mm, kerf_mm)
            partial_used_length_mm = max(partial_used_length_mm, last_col_length_mm)

        rip_cut_count_partial = max(0, partial_columns - 1)
        cross_cut_count_partial = full_columns_partial * max(0, along - 1) + max(0, partial_rows_last - 1)

        rip_kerf_area_partial_mm2 = rip_cut_count_partial * raw_length_mm * kerf_mm
        cross_kerf_area_partial_mm2 = (
            full_columns_partial * max(0, along - 1) * detail_width_mm * kerf_mm
            + max(0, partial_rows_last - 1) * detail_width_mm * kerf_mm
        )
        kerf_area_partial_mm2 = rip_kerf_area_partial_mm2 + cross_kerf_area_partial_mm2

    net_detail_area_m2 = (
        full_pattern_count * net_detail_area_full_mm2 + net_detail_area_partial_mm2
    ) / 1_000_000.0

    kerf_area_m2 = (
        full_pattern_count * kerf_area_full_mm2 + kerf_area_partial_mm2
    ) / 1_000_000.0

    consumed_area_m2 = net_detail_area_m2 + kerf_area_m2

    sheet_area_m2 = (raw_width_mm * raw_length_mm) / 1_000_000.0
    opened_sheet_area_m2 = opened_sheet_count * sheet_area_m2
    reusable_offcut_area_m2 = max(0.0, opened_sheet_area_m2 - consumed_area_m2)

    if partial_piece_count > 0:
        reusable_offcut_width_mm = max(0.0, raw_width_mm - partial_used_width_mm)
        reusable_offcut_length_mm = max(0.0, raw_length_mm - partial_used_length_mm)
        scheme_used_width_mm = partial_used_width_mm
        scheme_used_length_mm = partial_used_length_mm
        scheme_piece_count = partial_piece_count
        scheme_across = partial_columns
        scheme_last_column_rows = partial_rows_last
        scheme_full_columns = full_columns_partial
    else:
        reusable_offcut_width_mm = max(0.0, raw_width_mm - full_used_width_mm)
        reusable_offcut_length_mm = max(0.0, raw_length_mm - full_used_length_mm)
        scheme_used_width_mm = full_used_width_mm
        scheme_used_length_mm = full_used_length_mm
        scheme_piece_count = pieces_per_sheet
        scheme_across = across
        scheme_last_column_rows = along
        scheme_full_columns = across

    rip_cut_count = full_pattern_count * rip_cut_count_full + rip_cut_count_partial
    cross_cut_count = full_pattern_count * cross_cut_count_full + cross_cut_count_partial
    total_cut_count = rip_cut_count + cross_cut_count

    rip_time_sec = (raw_length_mm / 1000.0) * sec_per_m * 2 * rip_cut_count
    cross_time_sec = (detail_width_mm / 1000.0) * sec_per_m * 2 * cross_cut_count
    total_sec = rip_time_sec + cross_time_sec

    return {
        "opened_sheet_count": opened_sheet_count,
        "full_pattern_count": full_pattern_count,
        "partial_pattern_count": partial_pattern_count,
        "pieces_per_sheet": pieces_per_sheet,
        "net_detail_area_m2": net_detail_area_m2,
        "kerf_area_m2": kerf_area_m2,
        "consumed_area_m2": consumed_area_m2,
        "opened_sheet_area_m2": opened_sheet_area_m2,
        "reusable_offcut_area_m2": reusable_offcut_area_m2,
        "reusable_offcut_width_mm": reusable_offcut_width_mm,
        "reusable_offcut_length_mm": reusable_offcut_length_mm,
        "rip_cut_count": rip_cut_count,
        "cross_cut_count": cross_cut_count,
        "total_cut_count": total_cut_count,
        "total_sec": total_sec,
        "scheme_used_width_mm": scheme_used_width_mm,
        "scheme_used_length_mm": scheme_used_length_mm,
        "scheme_piece_count": scheme_piece_count,
        "scheme_across": scheme_across,
        "scheme_full_columns": scheme_full_columns,
        "scheme_last_column_rows": scheme_last_column_rows,
        "detail_width_mm": detail_width_mm,
        "detail_length_mm": detail_length_mm,
        "raw_width_mm": raw_width_mm,
        "raw_length_mm": raw_length_mm,
        "detail_count": detail_count,
        "kerf_mm": kerf_mm,
    }
