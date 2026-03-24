import win32com.client as win32
from collections import defaultdict
import pythoncom
import os

def to_number(val):
    if val is None:
        return 0
    if isinstance(val, str):
        val = val.replace(",", "").strip()
        if val.upper() in ("", "-", "DR", "CR"):
            return 0
        try:
            return float(val)
        except:
            return 0
    return val

def col_letter(col_num):
    """Converts a column number to its Excel letter representation (e.g., 1 -> A, 27 -> AA)."""
    result = ""
    while col_num:
        col_num, rem = divmod(col_num - 1, 26)
        result = chr(65 + rem) + result
    return result

def process_bank_fin_block(master_ws, temp_ws, sheet_name):
    """Processes detail blocks for specialized sheets like BANK FIN, PVT FIN, or RETURN."""
    data = temp_ws.UsedRange.Value
    if not data or len(data) <= 1:
        return

    headers = list(data[0])
    rows = data[1:]
    col_map = {h: i for i, h in enumerate(headers)}
    category_idx = col_map.get("Category")
    dr_idx = col_map.get("DR")
    cr_idx = col_map.get("CR")

    grouped = defaultdict(list)
    for r in rows:
        if r and category_idx is not None and len(r) > category_idx:
            cat = r[category_idx]
            if cat:
                grouped[cat].append(r)

    # Find Append Position
    last_row = master_ws.UsedRange.Rows.Count
    current_row = 2 if last_row <= 1 else last_row + 3

    # Title
    title_range = master_ws.Range(master_ws.Cells(current_row, 3), master_ws.Cells(current_row, 5))
    title_range.Merge()
    title_range.Value = sheet_name
    title_range.HorizontalAlignment = -4108 # xlCenter
    title_range.Font.Color = 255 # Red
    title_range.Font.Bold = True
    title_range.Borders.LineStyle = 1
    current_row += 1

    account_start_row = current_row

    for category, items in grouped.items():
        # Write Category Header
        header_range = master_ws.Range(master_ws.Cells(current_row, 1), master_ws.Cells(current_row, len(headers)))
        header_range.Value = headers
        header_range.Interior.Color = 12611584 # Blue
        header_range.Font.Color = 16777215 # White
        header_range.Font.Bold = True
        current_row += 1

        data_start_row = current_row
        # Bulk write items for this category
        data_range = master_ws.Range(master_ws.Cells(current_row, 1), master_ws.Cells(current_row + len(items) - 1, len(headers)))
        data_range.Value = items
        current_row += len(items)
        data_end_row = current_row - 1

        # Write Total for this category
        master_ws.Cells(current_row, (category_idx if category_idx is not None else 0) + 1).Value = "TOTAL"
        
        dr_col = col_letter(dr_idx + 1) if dr_idx is not None else "A"
        cr_col = col_letter(cr_idx + 1) if cr_idx is not None else "A"
        
        if dr_idx is not None:
            master_ws.Cells(current_row, dr_idx + 1).Formula = f"=SUM({dr_col}{data_start_row}:{dr_col}{data_end_row})"
        if cr_idx is not None:
            master_ws.Cells(current_row, cr_idx + 1).Formula = f"=SUM({cr_col}{data_start_row}:{cr_col}{data_end_row})"

        total_range = master_ws.Range(master_ws.Cells(current_row, 1), master_ws.Cells(current_row, len(headers)))
        total_range.Font.Bold = True
        total_range.Font.Color = 255
        current_row += 2

    # Formatting overall account block
    account_end_row = current_row - 1
    master_ws.Range(master_ws.Cells(account_start_row, 1), master_ws.Cells(account_end_row, len(headers))).Borders.LineStyle = 1
    
    if dr_idx is not None:
        master_ws.Range(master_ws.Cells(account_start_row, dr_idx + 1), master_ws.Cells(account_end_row, dr_idx + 1)).NumberFormat = '_(* #,##,##0_);_(* (#,##,##0);_(* "-"_);_(@_)'
    if cr_idx is not None:
        master_ws.Range(master_ws.Cells(account_start_row, cr_idx + 1), master_ws.Cells(account_end_row, cr_idx + 1)).NumberFormat = '_(* #,##,##0_);_(* (#,##,##0);_(* "-"_);_(@_)'

def create_chart_from_pivot(file_path):
    """Extracts pivot table details into specialized summary 'chart' sheets."""
    if not os.path.exists(file_path):
        return

    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.EnableEvents = False
        try:
            excel.Calculation = -4135 # xlManual
        except:
            pass

        wb = excel.Workbooks.Open(file_path)
        chart_list = ['NAMES', 'ODD FIG', 'DOUBT', 'BANK FIN', 'RETURN', 'PVT FIN']
        master_sheets = {}

        # 1. Clean existing chart sheets
        sheets_to_delete = [sh.Name for sh in wb.Worksheets if sh.Name in chart_list]
        for name in sheets_to_delete:
            try:
                wb.Worksheets(name).Delete()
            except:
                pass

        # 2. Collect pivot sheet names first (avoid modifying collection during iteration)
        pivot_sheet_names = [ws.Name for ws in wb.Worksheets if ws.Name.upper().startswith("PIVOT")]

        # 3. Iterate Pivot Sheets
        for pivot_name in pivot_sheet_names:
            ws = wb.Worksheets(pivot_name)
            sheet_suffix = pivot_name.replace("PIVOT-", "").strip()

            for chart_type in chart_list:
                search_term = f"{chart_type} TOTAL"
                found_cell = ws.Columns(1).Find(What=search_term, LookAt=1)  # xlWhole=1

                if not found_cell:
                    continue

                target_row = found_cell.Row
                col_count = ws.UsedRange.Columns.Count

                # --- Attempt 1: ShowDetail drill-down ---
                details_expanded = False
                for c in range(col_count, 1, -1):
                    val = ws.Cells(target_row, c).Value
                    if val is None or val == "":
                        continue
                    try:
                        ws.Cells(target_row, c).ShowDetail = True
                        # Confirm a new sheet was created (ActiveSheet changed away from pivot)
                        if wb.ActiveSheet.Name != pivot_name:
                            details_expanded = True
                            break
                    except:
                        continue

                temp_ws = None

                if details_expanded:
                    temp_ws = wb.ActiveSheet
                else:
                    # --- Attempt 2: Read corresponding XNS sheet directly ---
                    xns_name = pivot_name.replace("PIVOT-", "XNS-", 1)
                    try:
                        xns_ws = wb.Worksheets(xns_name)
                        xns_data = xns_ws.UsedRange.Value
                        if xns_data and len(xns_data) >= 2:
                            headers = list(xns_data[0])
                            # Find the Category column
                            cat_col_idx = next(
                                (i for i, h in enumerate(headers) if h and "CATEG" in str(h).upper()),
                                None
                            )
                            if cat_col_idx is not None:
                                # Filter rows that match chart_type in the Category column
                                filtered = [
                                    row for row in xns_data[1:]
                                    if row
                                    and len(row) > cat_col_idx
                                    and row[cat_col_idx]
                                    and chart_type.upper() in str(row[cat_col_idx]).upper()
                                ]
                                if filtered:
                                    temp_ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
                                    safe_suffix = sheet_suffix[:6].replace("/", "-").replace("\\", "-")
                                    temp_ws.Name = f"__T_{chart_type[:3]}_{safe_suffix}"
                                    h_range = temp_ws.Range(temp_ws.Cells(1, 1), temp_ws.Cells(1, len(headers)))
                                    h_range.Value = headers
                                    d_range = temp_ws.Range(temp_ws.Cells(2, 1), temp_ws.Cells(1 + len(filtered), len(headers)))
                                    d_range.Value = filtered
                                    print(f"  [XNS Fallback] {pivot_name} / {chart_type}: {len(filtered)} rows")
                    except Exception as fallback_err:
                        print(f"  [XNS Fallback failed] {pivot_name} / {chart_type}: {fallback_err}")

                if temp_ws is None:
                    print(f"  [Skip] No expandable data for '{chart_type}' in sheet '{pivot_name}'")
                    continue

                # Pre-process Temp Sheet: remove "Description" column if present
                td_cols = temp_ws.UsedRange.Columns.Count
                for c in range(1, td_cols + 1):
                    if temp_ws.Cells(1, c).Value == "Description":
                        temp_ws.Columns(c).Delete()
                        break

                # Ensure Master Sheet exists
                if chart_type not in master_sheets:
                    master_ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
                    master_ws.Name = chart_type
                    master_sheets[chart_type] = master_ws
                else:
                    master_ws = master_sheets[chart_type]

                if chart_type in {'BANK FIN', 'PVT FIN', 'RETURN'}:
                    process_bank_fin_block(master_ws, temp_ws, sheet_suffix)
                else:
                    # Regular Chart Detail Copy
                    t_range = temp_ws.UsedRange
                    t_rows, t_cols = t_range.Rows.Count, t_range.Columns.Count

                    last_m_row = master_ws.Cells(master_ws.Rows.Count, 1).End(-4162).Row
                    paste_row = 2 if (last_m_row == 1 and master_ws.Cells(1, 1).Value is None) else last_m_row + 3

                    # Title
                    title_range = master_ws.Range(master_ws.Cells(paste_row, 3), master_ws.Cells(paste_row, 5))
                    title_range.Merge()
                    title_range.Value = sheet_suffix
                    title_range.HorizontalAlignment = -4108
                    title_range.Font.Color = 255
                    title_range.Font.Bold = True
                    title_range.Borders.LineStyle = 1

                    # Header
                    header_row = paste_row + 1
                    header_range = master_ws.Range(master_ws.Cells(header_row, 1), master_ws.Cells(header_row, t_cols))
                    header_range.Value = (
                        temp_ws.Rows(1).Value[:t_cols]
                        if isinstance(temp_ws.Rows(1).Value, tuple)
                        else temp_ws.Rows(1).Value
                    )
                    header_range.Interior.Color = 12611584
                    header_range.Font.Color = 16777215
                    header_range.Font.Bold = True

                    # Data (Bulk write)
                    dest_data_range = master_ws.Range(
                        master_ws.Cells(header_row + 1, 1),
                        master_ws.Cells(header_row + t_rows - 1, t_cols)
                    )
                    dest_data_range.Value = temp_ws.Range(
                        temp_ws.Cells(2, 1),
                        temp_ws.Cells(t_rows, t_cols)
                    ).Value

                    # Formatting
                    all_data_range = master_ws.Range(
                        master_ws.Cells(header_row, 1),
                        master_ws.Cells(header_row + t_rows - 1, t_cols)
                    )
                    all_data_range.Borders.LineStyle = 1

                    # Autoformat Date/Numbers
                    h_vals = header_range.Value[0] if isinstance(header_range.Value, tuple) else header_range.Value
                    for i, h in enumerate(h_vals, 1):
                        h_str = str(h).upper().strip()
                        target_col_range = master_ws.Range(
                            master_ws.Cells(header_row + 1, i),
                            master_ws.Cells(header_row + t_rows - 1, i)
                        )
                        if h_str == "DATE":
                            target_col_range.NumberFormat = "dd-mm-yyyy"
                        elif h_str in ("DR", "CR"):
                            target_col_range.NumberFormat = '_(* #,##,##0_);_(* (#,##,##0);_(* "-"_);_(@_)'

                # Cleanup temp sheet
                try:
                    temp_ws.Delete()
                except:
                    pass

        # Final Formatting for all master sheets
        for ws in master_sheets.values():
            try:
                ws.Columns("A:E").AutoFit()
            except:
                pass

        print("Charts created successfully.")
        wb.Save()
    finally:
        if wb:
            try:
                wb.Close()
            except:
                pass
        if excel:
            try:
                excel.Calculation = -4105
                excel.ScreenUpdating = True
                excel.EnableEvents = True
                excel.Quit()
            except:
                pass
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    # Removed raw file paths for production.
    pass