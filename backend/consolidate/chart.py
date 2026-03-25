import win32com.client as win32
from collections import defaultdict
import pythoncom
import os
import time

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
    try:
        data = temp_ws.UsedRange.Value
    except:
        return

    if not data or len(data) <= 1:
        return

    headers = [str(h).strip() if h is not None else "" for h in data[0]]
    rows = data[1:]
    col_map = {h.upper(): i for i, h in enumerate(headers)}
    
    # Lenient header search
    category_idx = col_map.get("CATEGORY")
    dr_idx = col_map.get("DR")
    cr_idx = col_map.get("CR")

    grouped = defaultdict(list)
    for r in rows:
        if r and category_idx is not None and len(r) > category_idx:
            cat = str(r[category_idx]).strip() if r[category_idx] is not None else ""
            if cat:
                grouped[cat].append(r)

    # Find Append Position
    last_row = master_ws.UsedRange.Rows.Count
    current_row = 2 if (last_row <= 1 and master_ws.Cells(1, 1).Value is None) else last_row + 3

    # Title
    title_range = master_ws.Range(master_ws.Cells(current_row, 3), master_ws.Cells(current_row, 5))
    try:
        title_range.Merge()
        title_range.Value = sheet_name
        title_range.HorizontalAlignment = -4108 # xlCenter
        title_range.Font.Color = 255 # Red
        title_range.Font.Bold = True
        title_range.Borders.LineStyle = 1
    except:
        pass
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
        total_label_cell = master_ws.Cells(current_row, (category_idx if category_idx is not None else 0) + 1)
        total_label_cell.Value = "TOTAL"
        
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
    try:
        master_ws.Range(master_ws.Cells(account_start_row, 1), master_ws.Cells(account_end_row, len(headers))).Borders.LineStyle = 1
        
        if dr_idx is not None:
            master_ws.Range(master_ws.Cells(account_start_row, dr_idx + 1), master_ws.Cells(account_end_row, dr_idx + 1)).NumberFormat = '_(* #,##,##0_);_(* (#,##,##0);_(* "-"_);_(@_)'
        if cr_idx is not None:
            master_ws.Range(master_ws.Cells(account_start_row, cr_idx + 1), master_ws.Cells(account_end_row, cr_idx + 1)).NumberFormat = '_(* #,##,##0_);_(* (#,##,##0);_(* "-"_);_(@_)'
    except:
        pass

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

        # 2. Collect pivot sheet names
        pivot_sheet_names = [ws.Name for ws in wb.Worksheets if "PIVOT" in ws.Name.upper()]

        # 3. Iterate Pivot Sheets
        for pivot_name in pivot_sheet_names:
            ws = wb.Worksheets(pivot_name)
            # Find the unique part of the sheet name (e.g. HDFC-7977-CA)
            match_suffix = pivot_name.upper().split("PIVOT")[-1].strip("- ")
            
            for chart_type in chart_list:
                target_row = None
                # Excel 2007 Compatibility: Search for both "TOTAL" and "GRAND TOTAL"
                search_terms = [f"{chart_type} TOTAL", f"{chart_type} GRAND TOTAL", chart_type]
                
                for term in search_terms:
                    # xlWhole=1 first, then xlPart=2
                    found_cell = ws.Columns(1).Find(What=term, LookAt=1) # xlWhole
                    if not found_cell:
                        found_cell = ws.Columns(1).Find(What=term, LookAt=2) # xlPart
                    
                    if found_cell:
                        target_row = found_cell.Row
                        break
                
                if not target_row:
                    continue

                col_count = ws.UsedRange.Columns.Count

                # --- Attempt 1: ShowDetail (Skipped if User says it's unreliable in 2007) ---
                # But we try once just in case it works for some rows
                details_expanded = False
                for c in range(col_count, 1, -1):
                    val = ws.Cells(target_row, c).Value
                    if val is None or val == "" or val == 0 or val == "-":
                        continue
                    try:
                        ws.Cells(target_row, c).ShowDetail = True
                        if wb.ActiveSheet.Name != pivot_name:
                            details_expanded = True
                            break
                    except:
                        continue

                temp_ws = None
                if details_expanded:
                    temp_ws = wb.ActiveSheet
                else:
                    # --- Attempt 2: XNS Fallback (Optimized for 2007) ---
                    # Find XNS sheet by suffix match
                    xns_ws = None
                    for sh in wb.Worksheets:
                        if "XNS" in sh.Name.upper() and match_suffix in sh.Name.upper():
                            xns_ws = sh; break
                    
                    if xns_ws:
                        try:
                            # Use Range.CurrentRegion for potentially more robust data detection in 2007
                            xns_data = xns_ws.UsedRange.Value
                            if xns_data and len(xns_data) >= 1:
                                # Sometimes header is not in row 1 if there's blank space
                                header_row_idx = 0
                                found_cat_col = None
                                aliases = ["CATEGORY", "CATEG", "CATG", "CAT"]
                                
                                # Scan first 5 rows for headers
                                for r_idx in range(min(5, len(xns_data))):
                                    row_vals = [str(v).strip().upper() if v is not None else "" for v in xns_data[r_idx]]
                                    for i, v in enumerate(row_vals):
                                        if any(a in v for a in aliases):
                                            found_cat_col = i
                                            header_row_idx = r_idx
                                            break
                                    if found_cat_col is not None: break
                                
                                if found_cat_col is not None:
                                    headers = xns_data[header_row_idx]
                                    filtered = []
                                    match_key = chart_type.upper().strip()
                                    for row in xns_data[header_row_idx + 1:]:
                                        if row and len(row) > found_cat_col:
                                            val = str(row[found_cat_col]).strip().upper()
                                            if match_key in val:
                                                filtered.append(row)
                                    
                                    if filtered:
                                        temp_ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
                                        safe_name = f"__T_{chart_type[:3]}_{match_suffix[:5]}".replace("-", "_")
                                        try: temp_ws.Name = safe_name
                                        except: temp_ws.Name = f"T_{int(time.time()) % 10000}"
                                        
                                        # Use Range carefully for 2007
                                        temp_ws.Range(temp_ws.Cells(1, 1), temp_ws.Cells(1, len(headers))).Value = headers
                                        temp_ws.Range(temp_ws.Cells(2, 1), temp_ws.Cells(1 + len(filtered), len(headers))).Value = filtered
                                        print(f"  ✅ [XNS Fallback Success] {pivot_name} / {chart_type}: {len(filtered)} rows")
                        except Exception as e:
                            print(f"  [XNS Fallback Error] {pivot_name}: {e}")

                if temp_ws is None:
                    print(f"  [Skip] No data found for '{chart_type}' in sheet '{pivot_name}'")
                    continue

                # Pre-process Temp Sheet: remove "Description" column
                try:
                    td_cols = temp_ws.UsedRange.Columns.Count
                    for c in range(1, td_cols + 1):
                        h_val = str(temp_ws.Cells(1, c).Value).strip().upper()
                        if "DESCRIPTION" in h_val:
                            temp_ws.Columns(c).Delete()
                            break
                except:
                    pass

                # Ensure Master Sheet exists
                if chart_type not in master_sheets:
                    try:
                        master_ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
                        master_ws.Name = chart_type
                        master_sheets[chart_type] = master_ws
                    except:
                        master_ws = wb.Worksheets(chart_type)
                        master_sheets[chart_type] = master_ws
                else:
                    master_ws = master_sheets[chart_type]

                if chart_type in {'BANK FIN', 'PVT FIN', 'RETURN'}:
                    process_bank_fin_block(master_ws, temp_ws, match_suffix)
                else:
                    # Regular Chart Detail Copy
                    try:
                        t_range = temp_ws.UsedRange
                        t_rows, t_cols = t_range.Rows.Count, t_range.Columns.Count

                        last_m_row = master_ws.Cells(master_ws.Rows.Count, 1).End(-4162).Row
                        # Excel 2007 Check for empty sheet
                        paste_row = 2 if (last_m_row == 1 and master_ws.Cells(1, 1).Value is None) else last_m_row + 3

                        # Title
                        title_range = master_ws.Range(master_ws.Cells(paste_row, 3), master_ws.Cells(paste_row, 5))
                        title_range.Merge()
                        title_range.Value = match_suffix
                        title_range.HorizontalAlignment = -4108
                        title_range.Font.Color = 255
                        title_range.Font.Bold = True
                        title_range.Borders.LineStyle = 1

                        # Header
                        header_row = paste_row + 1
                        header_range = master_ws.Range(master_ws.Cells(header_row, 1), master_ws.Cells(header_row, t_cols))
                        h_vals = temp_ws.Rows(1).Value
                        if isinstance(h_vals, tuple): h_vals = h_vals[0][:t_cols] if len(h_vals) == 1 else h_vals[:t_cols]
                        header_range.Value = h_vals
                        header_range.Interior.Color = 12611584
                        header_range.Font.Color = 16777215
                        header_range.Font.Bold = True

                        # Data
                        dest_data_range = master_ws.Range(master_ws.Cells(header_row + 1, 1), master_ws.Cells(header_row + t_rows - 1, t_cols))
                        dest_data_range.Value = temp_ws.Range(temp_ws.Cells(2, 1), temp_ws.Cells(t_rows, t_cols)).Value

                        # Formatting
                        all_data_range = master_ws.Range(master_ws.Cells(header_row, 1), master_ws.Cells(header_row + t_rows - 1, t_cols))
                        all_data_range.Borders.LineStyle = 1

                        # Autoformat
                        for i, h in enumerate(h_vals, 1):
                            h_str = str(h).upper().strip()
                            target_col_range = master_ws.Range(master_ws.Cells(header_row + 1, i), master_ws.Cells(header_row + t_rows - 1, i))
                            if "DATE" in h_str:
                                target_col_range.NumberFormat = "dd-mm-yyyy"
                            elif h_str in ("DR", "CR"):
                                target_col_range.NumberFormat = '_(* #,##,##0_);_(* (#,##,##0);_(* "-"_);_(@_)'
                    except Exception as e:
                        print(f"  [Chart Error] Failed for {match_suffix}: {e}")

                try:
                    temp_ws.Delete()
                except:
                    pass

        # Final Formatting
        for ws in master_sheets.values():
            try:
                ws.Columns("A:Z").AutoFit()
            except:
                pass

        wb.Save()
        print("Charts created successfully.")
    finally:
        if wb:
            try: wb.Close()
            except: pass
        if excel:
            try:
                excel.Calculation = -4105
                excel.ScreenUpdating = True
                excel.EnableEvents = True
                excel.Quit()
            except: pass
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    pass