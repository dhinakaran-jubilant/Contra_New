from datetime import datetime
import win32com.client as win32
from collections import defaultdict
import pythoncom
import os
import time
import re

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

def process_bank_fin_block(master_ws, temp_ws, sheet_name, global_months=None):
    """Processes detail blocks for specialized sheets like BANK FIN, PVT FIN, or RETURN."""
    try:
        data = temp_ws.UsedRange.Value
    except:
        return

    if not data or len(data) <= 1:
        return

    headers = [str(h).strip() if h is not None else "" for h in data[0]]
    rows = [list(r) for r in data[1:]] if data and len(data) > 1 else []
    col_map = {h.upper(): i for i, h in enumerate(headers)}
    
    # Lenient header search
    category_idx = col_map.get("CATEGORY", col_map.get("TYPE"))
    date_idx = col_map.get("DATE")
    dr_idx = col_map.get("DR")
    cr_idx = col_map.get("CR")
    month_idx = col_map.get("MONTH")

    grouped = defaultdict(list)
    if category_idx is not None:
        for r in rows:
            if r and len(r) > category_idx:
                cat = str(r[category_idx]).strip() if r[category_idx] is not None else ""
                if cat:
                    grouped[cat].append(r)
    else:
        # Fallback if no category column: just one big block
        grouped["DATA"].extend(rows)

    # Find Append Position
    last_row = master_ws.UsedRange.Rows.Count
    
    # Check if this account block already exists in the master sheet
    try:
        found = master_ws.Columns(3).Find(What=sheet_name, LookAt=1) # xlWhole
        if found:
            print(f"  [Skip] Block '{sheet_name}' already exists in {master_ws.Name}")
            return
    except:
        pass

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

    # Sort categories to ensure consistent output order? Optional, 
    # but the items WITHIN categories MUST be sorted by Date.
    for category in sorted(grouped.keys()):
        items = grouped[category]
        
        ordered_items = []
        missing_month_info = [] # stores tuples of (index_in_ordered, global_month_index)
        
        first_cr_global_idx = -1
        
        if global_months and month_idx is not None:
            # Find the chronological index of the first CR value
            cr_idxs = []
            global_months_upper = [str(m).strip().upper() for m in global_months]
            for r in items:
                if cr_idx is not None and len(r) > cr_idx and abs(to_number(r[cr_idx])) > 0:
                    m_val = str(r[month_idx]).strip().upper() if len(r) > month_idx and r[month_idx] is not None else ""
                    if m_val in global_months_upper:
                        cr_idxs.append(global_months_upper.index(m_val))
            if cr_idxs:
                first_cr_global_idx = min(cr_idxs)
                
            items_by_month = defaultdict(list)
            for r in items:
                m_val = str(r[month_idx]).strip() if len(r) > month_idx and r[month_idx] is not None else ""
                items_by_month[m_val.upper()].append(r)
                
            for global_idx, m in enumerate(global_months):
                m_key = m.upper().strip()
                if m_key in items_by_month:
                    m_items = items_by_month.pop(m_key)
                    if date_idx is not None:
                        try:
                            m_items.sort(key=lambda x: (x[date_idx] if (len(x) > date_idx and x[date_idx] is not None) else datetime.min))
                        except: pass
                    ordered_items.extend(m_items)
                else:
                    if first_cr_global_idx != -1 and global_idx < first_cr_global_idx:
                        continue # Skip adding missing months before the loan disbursement
                        
                    dummy = ["" for _ in range(len(headers))]
                    dummy[month_idx] = m
                    ordered_items.append(dummy)
                    missing_month_info.append((len(ordered_items) - 1, global_idx))
                    
            for m_key, m_items in items_by_month.items():
                if date_idx is not None:
                    try:
                        m_items.sort(key=lambda x: (x[date_idx] if (len(x) > date_idx and x[date_idx] is not None) else datetime.min))
                    except: pass
                ordered_items.extend(m_items)
        else:
            ordered_items = items[:]
            if date_idx is not None:
                try:
                    ordered_items.sort(key=lambda x: (x[date_idx] if (len(x) > date_idx and x[date_idx] is not None) else datetime.min))
                except Exception as sort_e:
                    print(f"  [Sort Warning] Could not sort items in {category}: {sort_e}")

        # Write Category Header
        header_range = master_ws.Range(master_ws.Cells(current_row, 1), master_ws.Cells(current_row, len(headers)))
        header_range.Value = headers
        header_range.Interior.Color = 12611584 # Blue
        header_range.Font.Color = 16777215 # White
        header_range.Font.Bold = True
        current_row += 1

        # Bulk write items for this category
        data_start_row = current_row
        
        # Ensure DR/CR values are numbers
        for r in ordered_items:
            if dr_idx is not None and len(r) > dr_idx:
                r[dr_idx] = to_number(r[dr_idx])
            if cr_idx is not None and len(r) > cr_idx:
                r[cr_idx] = to_number(r[cr_idx])

        data_range = master_ws.Range(master_ws.Cells(current_row, 1), master_ws.Cells(current_row + len(ordered_items) - 1, len(headers)))
        data_range.Value = ordered_items
        
        # Color missing month cells and make month text bold
        for offset, global_idx in missing_month_info:
            row_in_sheet = current_row + offset
            
            # Make the Month name bold
            if month_idx is not None:
                master_ws.Cells(row_in_sheet, month_idx + 1).Font.Bold = True
                
            # If a CR value exists, only highlight the DR cell for missing months AFTER it.
            # Otherwise, highlight the DR cell for ALL missing months.
            should_highlight_dr = False
            if first_cr_global_idx != -1:
                # Highlight if chronological month is logically strictly AFTER the CR value
                if global_idx > first_cr_global_idx:
                    should_highlight_dr = True
            else:
                should_highlight_dr = True
                
            if should_highlight_dr and dr_idx is not None:
                cell = master_ws.Cells(row_in_sheet, dr_idx + 1)
                cell.Interior.Color = 255
                cell.Font.Bold = True

        current_row += len(ordered_items)
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
            master_ws.Range(master_ws.Cells(account_start_row, dr_idx + 1), master_ws.Cells(account_end_row, dr_idx + 1)).NumberFormat = '_(* #,##,##0.00_);_(* (#,##,##0.00);_(* "-"_);_(@_)'
        if cr_idx is not None:
            master_ws.Range(master_ws.Cells(account_start_row, cr_idx + 1), master_ws.Cells(account_end_row, cr_idx + 1)).NumberFormat = '_(* #,##,##0.00_);_(* (#,##,##0.00);_(* "-"_);_(@_)'
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

        # 1. DO NOT DELETE existing chart sheets. Just parse them.
        for c_type in chart_list:
            try:
                master_sheets[c_type] = wb.Worksheets(c_type)
            except:
                pass
                
        # 1.5 Read tracked pivots that shouldn't be re-charted
        pivots_with_charts = set()
        try:
            meta_ws = wb.Worksheets("SYSTEM_CHART_META")
            last_r = meta_ws.Cells(meta_ws.Rows.Count, 1).End(-4162).Row
            for r in range(1, last_r + 1):
                val = meta_ws.Cells(r, 1).Value
                if val: pivots_with_charts.add(str(val).upper().strip())
                
            excel.DisplayAlerts = False
            meta_ws.Delete()
            excel.DisplayAlerts = True
        except:
            pass

        # 2. Collect pivot sheet names
        pivot_sheet_names = [ws.Name for ws in wb.Worksheets if "PIVOT" in ws.Name.upper()]

        # 2.5 Extract Global Months from the first Pivot to ensure full timeline coverage
        global_months = []
        if pivot_sheet_names:
            try:
                pt_ws = wb.Worksheets(pivot_sheet_names[0])
                pt = pt_ws.PivotTables(1)
                m_field = pt.PivotFields("MONTH")
                m_items = []
                for idx in range(1, m_field.PivotItems().Count + 1):
                    item = m_field.PivotItems(idx)
                    if item.Visible and "(blank)" not in str(item.Name).lower():
                        m_items.append((item.Position, str(item.Name)))
                m_items.sort(key=lambda x: x[0])
                global_months = [m[1] for m in m_items]
            except Exception as e:
                print(f"  [Global Months Error] {e}")

        # 3. Iterate Pivot Sheets
        for pivot_name in pivot_sheet_names:
            if pivot_name.upper().strip() in pivots_with_charts:
                print(f"  [Skip] {pivot_name} already charted from original file.")
                continue
                
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
                            # 🚀 Optimized XNS Fallback: Read once
                            xns_data = xns_ws.UsedRange.Value
                            if xns_data and len(xns_data) >= 1:
                                found_cat_col = None
                                header_row_idx = 0
                                aliases = ["TYPE", "CATEGORY", "CATEG", "CATG", "CAT", "PARTICULARS", "DESCRIPTION", "DESC"]
                                
                                # Scan first 10 rows for headers
                                for r_idx in range(min(10, len(xns_data))):
                                    row = xns_data[r_idx]
                                    if not row: continue
                                    row_vals = [str(v).strip().upper() if v is not None else "" for v in row]
                                    for i, v in enumerate(row_vals):
                                        if any(a == v for a in aliases): # exact match preferred
                                            found_cat_col = i
                                            header_row_idx = r_idx
                                            break
                                    if found_cat_col is not None: break
                                
                                if found_cat_col is not None:
                                    headers = xns_data[header_row_idx]
                                    match_key = chart_type.upper().strip()
                                    # Filter in Python
                                    filtered = [row for row in xns_data[header_row_idx+1:] 
                                               if row and len(row) > found_cat_col 
                                               and match_key in str(row[found_cat_col]).upper()]
                                    
                                    if filtered:
                                        temp_ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
                                        safe_name = f"__T_{chart_type[:3]}_{match_suffix[:5]}".replace("-", "_")
                                        try: temp_ws.Name = safe_name
                                        except: temp_ws.Name = f"T_{int(time.time()) % 10000}_{chart_type[:2]}"
                                        
                                        temp_ws.Range(temp_ws.Cells(1, 1), temp_ws.Cells(1, len(headers))).Value = headers
                                        temp_ws.Range(temp_ws.Cells(2, 1), temp_ws.Cells(1 + len(filtered), len(headers))).Value = filtered
                                        print(f"  ✅ [XNS Fallback Success] {pivot_name} / {chart_type}: {len(filtered)} rows")
                                        details_expanded = True
                        except Exception as e:
                            print(f"  [XNS Fallback Error] {pivot_name}: {e}")


                if temp_ws is None:
                    print(f"  [Skip] No data found for '{chart_type}' in sheet '{pivot_name}'")
                    continue

                # Pre-process Temp Sheet: remove unwanted columns
                try:
                    td_cols = temp_ws.UsedRange.Columns.Count
                    for c in range(td_cols, 0, -1):
                        h_val = str(temp_ws.Cells(1, c).Value).strip().upper()
                        clean_h = h_val.replace(".", "").replace(" ", "")
                        if "DESCRIPTION" in h_val or "BALANCE" in h_val or clean_h == "SNO" or clean_h == "SLNO":
                            temp_ws.Columns(c).Delete()
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

                if chart_type in {'BANK FIN', 'PVT FIN'}:
                    process_bank_fin_block(master_ws, temp_ws, match_suffix, global_months)
                else:
                    # Regular Chart Detail Copy
                    try:
                        t_range = temp_ws.UsedRange
                        t_rows, t_cols = t_range.Rows.Count, t_range.Columns.Count

                        last_m_row = master_ws.Cells(master_ws.Rows.Count, 1).End(-4162).Row
                        
                        # Check if this account block already exists in the master sheet
                        try:
                            found = master_ws.Columns(3).Find(What=match_suffix, LookAt=1) # xlWhole
                            if found:
                                print(f"  [Skip] Block '{match_suffix}' already exists in {master_ws.Name}")
                                continue
                        except:
                            pass

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
                        # 🚀 Sort: 1st Date (Primary), then Category (Secondary)
                        raw_data = temp_ws.Range(temp_ws.Cells(2, 1), temp_ws.Cells(t_rows, t_cols)).Value
                        if not isinstance(raw_data, (tuple, list)): raw_data = ((raw_data,),)
                        elif not isinstance(raw_data[0], (tuple, list)): raw_data = (raw_data,)
                        rows_data = [list(r) for r in raw_data]
                        
                        # Identify indices from header values
                        date_idx = cat_idx = dr_idx = cr_idx = None
                        if h_vals:
                            for idx, h in enumerate(h_vals):
                                if h:
                                    h_str = str(h).upper().strip()
                                    if "DATE" in h_str: date_idx = idx
                                    if h_str in ("TYPE", "CATEGORY", "CATEG", "CATG", "CAT", "PARTICULARS", "DESCRIPTION", "DESC"): cat_idx = idx
                                    if h_str == "DR": dr_idx = idx
                                    if h_str == "CR": cr_idx = idx
                        
                        for r in rows_data:
                            if dr_idx is not None and len(r) > dr_idx:
                                r[dr_idx] = to_number(r[dr_idx])
                            if cr_idx is not None and len(r) > cr_idx:
                                r[cr_idx] = to_number(r[cr_idx])
                        
                        def robust_sort_key(row):
                            # Normalize Date to float for safe comparison with both datetime and numeric Excel dates
                            d = row[date_idx] if (date_idx is not None and len(row) > date_idx) else None
                            d_val = 0.0
                            if isinstance(d, datetime):
                                # Convert datetime to Excel-style float (days since 1899-12-30)
                                d_val = (d - datetime(1899, 12, 30)).total_seconds() / 86400.0
                            elif isinstance(d, (int, float)):
                                d_val = float(d)
                                
                            # Category sort value (Secondary)
                            c_val = str(row[cat_idx]).upper().strip() if (cat_idx is not None and len(row) > cat_idx and row[cat_idx] is not None) else ""
                            return (d_val, c_val)

                        if date_idx is not None or cat_idx is not None:
                            try:
                                rows_data.sort(key=robust_sort_key)
                            except Exception as sort_e:
                                print(f"  [Sort Error] {match_suffix}: {sort_e}")

                        dest_data_range = master_ws.Range(master_ws.Cells(header_row + 1, 1), master_ws.Cells(header_row + t_rows - 1, t_cols))
                        dest_data_range.Value = rows_data

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
                                target_col_range.NumberFormat = '_(* #,##,##0.00_);_(* (#,##,##0.00);_(* "-"_);_(@_)'
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
                
        # Force all sheet names across the workbook to be UPPERCASE and remove junk sheets
        to_delete = []
        for ws in wb.Worksheets:
            try:
                name_upper = str(ws.Name).upper()
                ws.Name = name_upper
                # Identify empty/junk sheets like SHEET1, SHEET2
                if re.match(r"^SHEET\d+$", name_upper):
                    to_delete.append(ws)
            except:
                pass
        
        if to_delete:
            excel.DisplayAlerts = False
            for ws in to_delete:
                try: ws.Delete()
                except: pass
            excel.DisplayAlerts = True

                
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