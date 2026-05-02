from datetime import datetime
import win32com.client as win32
import pandas as pd
import pythoncom
import os

START_ROW = 5
START_COL = 4   # Column D

def get_multiple_sheet_name(df):
    """Parses account holder details from the ANALYSIS sheet dataframe."""
    account_details = []
    details = {}
    flag = False
    ignore_keys = {"Address", "Email", "PAN", "Mobile Number"}

    for _, row in df.iterrows():
        key = row.iloc[1]    # Excel column B
        value = row.iloc[2]  # Excel column C

        if key == "Name of the Account Holder" or flag:
            if key not in ignore_keys:
                details[key] = value
            flag = True
            if key == "Account Type":
                account_details.append(details)
                details = {}
                flag = False
    return account_details

def get_months_from_xns(wb):
    """
    Extracts unique months from all XNS sheets to establish the timeline.
    Optimized to read the entire UsedRange at once.
    """
    months = set()
    for sheet in wb.Worksheets:
        name = sheet.Name
        if not name.upper().startswith("XNS"):
            continue

        try:
            # 🚀 Bulk Read: Get the entire used data at once
            data = sheet.UsedRange.Value
            if not data or len(data) < 2:
                continue

            # Identify the Date column (usually B, which is index 1)
            # We'll check the first 5 rows for a 'DATE' header if possible, 
            # otherwise assume column B.
            date_col_idx = 1
            for r_idx in range(min(5, len(data))):
                row = data[r_idx]
                if any("DATE" in str(cell).upper() for cell in row if cell):
                    for idx, cell in enumerate(row):
                        if "DATE" in str(cell).upper():
                            date_col_idx = idx
                            break
                    break

            for row in data:
                if len(row) > date_col_idx:
                    dt = row[date_col_idx]
                    if isinstance(dt, datetime):
                        months.add((dt.year, dt.month))
                    elif isinstance(dt, (str, float, int)) and dt != "":
                        # Try to parse if it's not already a datetime object
                        # (Excel sometimes returns floats for dates)
                        pass # win32com usually returns datetime or None/Empty
        except Exception as e:
            print(f"Error reading {name}: {e}")
            continue

    if not months:
        return []

    months = sorted(months)
    labels = []
    if not months: return []
    for y, m in months:
        d = datetime(y, m, 1)
        label = d.strftime("%b").upper()
        # Always show year for all months
        label = f"{label}({str(y)[-2:]})"
        labels.append(label)
    return labels

def _build_cons_sheet_logic(ws, months, pivot_sheets, account_map, start_row, start_col, type1="PURCHASE", type2="SALES", label1="PURCHASE", label2="SALES"):
    """Encapsulates the core logic for building a consolidation sheet."""
    pivot_count = len(pivot_sheets)
    if pivot_count == 0:
        ws.Cells(start_row, start_col).Value = "No accounts found for this category."
        return

    # 1. Build Header
    header_vals = ["MONTH"]
    for sheet in pivot_sheets:
        suffix = sheet.split("PIVOT-")[-1].strip()
        holder_name = account_map.get(suffix, "")
        if not holder_name:
            holder_name = next((v for k, v in account_map.items() if k in suffix), "")
        header_vals.append(f"{holder_name}\n{suffix}\n{label1}")
    header_vals.append(f"{label1}\nTOTAL")
    
    for sheet in pivot_sheets:
        suffix = sheet.split("PIVOT-")[-1].strip()
        holder_name = account_map.get(suffix, "")
        if not holder_name:
            holder_name = next((v for k, v in account_map.items() if k in suffix), "")
        header_vals.append(f"{holder_name}\n{suffix}\n{label2}")
    header_vals.append(f"{label2}\nTOTAL")

    last_col_idx = start_col + len(header_vals) - 1
    header_range = ws.Range(ws.Cells(start_row, start_col), ws.Cells(start_row, last_col_idx))
    header_range.Value = header_vals

    # Define column indices
    purchase_start_col = start_col + 1
    purchase_end_col = purchase_start_col + pivot_count - 1
    purchase_total_col = purchase_end_col + 1
    sales_start_col = purchase_total_col + 1
    sales_end_col = sales_start_col + pivot_count - 1
    sales_total_col = sales_end_col + 1

    # 2. Process Data
    wb = ws.Parent
    rows_to_paste = []
    for i, month_label in enumerate(months):
        row_data = [month_label]
        r_idx = start_row + 2 + (i * 2)
        
        # First Type Section (e.g. Purchase or Bank Fin Debit)
        for sheet in pivot_sheets:
            try:
                anchor = wb.Worksheets(sheet).PivotTables(1).TableRange2.Cells(1,1).Address
                # Formula: If value is 0 or error, show NIL. (Simplified)
                get_pivot_args = f'"Sum of DR",\'{sheet}\'!{anchor},"MONTH","{month_label}","TYPE","{type1}"'
                formula = f'=IFERROR(IF(GETPIVOTDATA({get_pivot_args})=0, "NIL", GETPIVOTDATA({get_pivot_args})), "NIL")'
                row_data.append(formula)
            except:
                row_data.append("NIL")
        
        p_total_formula = f"=SUM({ws.Cells(r_idx, purchase_start_col).Address}:{ws.Cells(r_idx, purchase_end_col).Address})"
        row_data.append(p_total_formula)
        
        # Second Type Section (e.g. Sales or Bank Fin Credit)
        for sheet in pivot_sheets:
            try:
                anchor = wb.Worksheets(sheet).PivotTables(1).TableRange2.Cells(1,1).Address
                # Formula: If value is 0 or error, show NIL. (Simplified)
                get_pivot_args = f'"Sum of CR",\'{sheet}\'!{anchor},"MONTH","{month_label}","TYPE","{type2}"'
                formula = f'=IFERROR(IF(GETPIVOTDATA({get_pivot_args})=0, "NIL", GETPIVOTDATA({get_pivot_args})), "NIL")'
                row_data.append(formula)
            except:
                row_data.append("NIL")
        
        s_total_formula = f"=SUM({ws.Cells(r_idx, sales_start_col).Address}:{ws.Cells(r_idx, sales_end_col).Address})"
        row_data.append(s_total_formula)
        
        rows_to_paste.append(row_data)
        rows_to_paste.append([None] * len(row_data)) # Spacer row

    if rows_to_paste:
        data_range = ws.Range(ws.Cells(start_row + 2, start_col), ws.Cells(start_row + 1 + len(rows_to_paste), last_col_idx))
        data_range.Formula = rows_to_paste

    # 3. Final Row Summary
    last_data_filled_row = start_row + 1 + len(rows_to_paste)
    summary_row = last_data_filled_row + 1
    
    ws.Range(ws.Cells(summary_row, start_col + 1), ws.Cells(summary_row, purchase_end_col)).Merge()
    ws.Cells(summary_row, start_col + 1).Value = f"TOTAL {label1}"
    ws.Cells(summary_row, purchase_total_col).Formula = f"=SUM({ws.Cells(start_row+1, purchase_total_col).Address}:{ws.Cells(last_data_filled_row, purchase_total_col).Address})"
    
    ws.Range(ws.Cells(summary_row, sales_start_col), ws.Cells(summary_row, sales_end_col)).Merge()
    ws.Cells(summary_row, sales_start_col).Value = f"TOTAL {label2}"
    ws.Cells(summary_row, sales_total_col).Formula = f"=SUM({ws.Cells(start_row+1, sales_total_col).Address}:{ws.Cells(last_data_filled_row, sales_total_col).Address})"

    # 4. Formatting
    summary_row_range = ws.Range(ws.Cells(summary_row, start_col), ws.Cells(summary_row, sales_total_col))
    summary_row_range.HorizontalAlignment = -4108
    summary_row_range.VerticalAlignment = -4108
    summary_row_range.Font.Bold = True
    summary_row_range.Font.Color = 255 # Red

    table_range = ws.Range(ws.Cells(start_row, start_col), ws.Cells(summary_row, sales_total_col))
    table_range.Font.Bold = True
    for b_id in [7, 8, 9, 10, 11, 12]:
        table_range.Borders(b_id).LineStyle = 1
        
    numeric_range = ws.Range(ws.Cells(start_row + 1, start_col + 1), ws.Cells(summary_row, sales_total_col))
    numeric_range.NumberFormat = "0.00"
    
    values_range = ws.Range(ws.Cells(start_row + 1, start_col + 1), ws.Cells(summary_row - 1, sales_total_col))
    values_range.HorizontalAlignment = -4152 # xlRight
        
    ws.Rows(f"{start_row + 1}:{summary_row - 1}").RowHeight = 18
    ws.Rows(summary_row).RowHeight = 40
    for col_idx in range(start_col, sales_total_col + 1):
        ws.Columns(col_idx).ColumnWidth = 15
        
    ws.Range(ws.Cells(start_row, purchase_total_col), ws.Cells(summary_row, purchase_total_col)).Font.ColorIndex = 3
    ws.Range(ws.Cells(start_row, sales_total_col), ws.Cells(summary_row, sales_total_col)).Font.ColorIndex = 3
    
    header_range.WrapText = True
    header_range.HorizontalAlignment = -4108
    header_range.VerticalAlignment = -4108
    ws.Rows(start_row).AutoFit()

def create_cons_sheet(file_path):
    """Generates the 'CONS' summary sheets (Main, Bank Fin, Pvt Fin)."""
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
        try: excel.Calculation = -4135
        except: pass

        wb = excel.Workbooks.Open(file_path)
        # 1. Identify Pivot Sheets and Specialized Accounts
        all_pivots = [s.Name for s in wb.Worksheets if s.Name.startswith("PIVOT")]
        if not all_pivots:
            return

        # 2. Extract Month Labels from ALL Pivot sheets to ensure the union is captured
        months = []
        for p_name in all_pivots:
            try:
                ws_ref = wb.Worksheets(p_name)
                pt = ws_ref.PivotTables(1)
                month_field = pt.PivotFields("MONTH")
                for item in month_field.PivotItems():
                    # Only include visible items that are not (blank)
                    if item.Visible and "(blank)" not in str(item.Name).lower():
                        m_name = str(item.Name)
                        if m_name not in months:
                            months.append(m_name)
            except:
                continue
        
        if not months:
            # Fallback to scanning XNS sheets directly if pivots are empty or missing MONTH field
            months = get_months_from_xns(wb)

        if not months:
            return

        # 3. Parse account details from ANALYSIS (for names and metadata)
        account_details = []
        try:
            analysis_ws = wb.Worksheets("ANALYSIS")
            last_row_analysis = analysis_ws.Cells(analysis_ws.Rows.Count, 2).End(-4162).Row
            analysis_data = analysis_ws.Range(f"A1:C{last_row_analysis}").Value
            analysis_df = pd.DataFrame(analysis_data)
            account_details = get_multiple_sheet_name(analysis_df)
        except Exception as e:
            print(f"Error parsing ANALYSIS sheet: {e}")

        account_map = {}
        bank_fin_accounts = []
        pvt_fin_accounts = []
        
        for acc in account_details:
            holder = acc.get("Name of the Account Holder")
            acc_num = str(acc.get("Account Number", ""))[-4:]
            acc_type = str(acc.get("Account Type", "")).upper().strip()
            
            if acc_num:
                account_map[acc_num] = holder
                if "BANK FIN" in acc_type:
                    bank_fin_accounts.append(acc_num)
                elif "PVT FIN" in acc_type:
                    pvt_fin_accounts.append(acc_num)

        # 4. Specialized Accounts Detection
        # Pre-scan pivots to identify which accounts have BANK FIN or PVT FIN transactions
        # This acts as a more robust fallback if the ANALYSIS sheet 'Account Type' is generic.
        detected_bank_fin = set()
        detected_pvt_fin = set()
        
        for p_name in all_pivots:
            try:
                # Find the suffix (e.g. 96706-CA)
                suffix = p_name.split("PIVOT-")[-1].strip()
                ws_pivot = wb.Worksheets(p_name)
                # Check for PivotTable items
                pt = ws_pivot.PivotTables(1)
                type_field = pt.PivotFields("TYPE")
                for item in type_field.PivotItems():
                    item_name = str(item.Name).upper().strip()
                    if item_name == "BANK FIN":
                        detected_bank_fin.add(suffix)
                    if item_name == "PVT FIN":
                        detected_pvt_fin.add(suffix)
            except:
                continue

        # Combine ANALYSIS metadata with detected transaction types
        bank_fin_suffixes = set(bank_fin_accounts) | detected_bank_fin
        pvt_fin_suffixes = set(pvt_fin_accounts) | detected_pvt_fin

        targets = [
            ("CONS", all_pivots),
            ("BANK FIN CONS", [p for p in all_pivots if any(suf in p for suf in bank_fin_suffixes)]),
            ("PVT FIN CONS", [p for p in all_pivots if any(suf in p for suf in pvt_fin_suffixes)])
        ]

        for s_name, pivot_list in targets:
            try:
                excel.DisplayAlerts = False
                wb.Worksheets(s_name).Delete()
                excel.DisplayAlerts = True
            except: pass
            
            # Skip specialized sheets if fewer than 1 account found for them
            if s_name != "CONS" and len(pivot_list) < 1:
                continue

            ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
            ws.Name = s_name
            
            # Use dynamic types and labels based on the sheet name
            if s_name == "BANK FIN CONS":
                _build_cons_sheet_logic(ws, months, pivot_list, account_map, START_ROW, START_COL, 
                                      type1="BANK FIN", type2="BANK FIN", 
                                      label1="BANK FIN DEBIT", label2="BANK FIN CREDIT")
            elif s_name == "PVT FIN CONS":
                _build_cons_sheet_logic(ws, months, pivot_list, account_map, START_ROW, START_COL, 
                                      type1="PVT FIN", type2="PVT FIN", 
                                      label1="PVT FIN DEBIT", label2="PVT FIN CREDIT")
            else:
                _build_cons_sheet_logic(ws, months, pivot_list, account_map, START_ROW, START_COL,
                                      type1="PURCHASE", type2="SALES", 
                                      label1="PURCHASE", label2="SALES")

        wb.Save()
        print("Consolidation sheets created successfully.")
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
