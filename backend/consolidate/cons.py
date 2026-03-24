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
    """Extracts unique months from all XNS sheets to establish the timeline."""
    months = set()
    for sheet in wb.Worksheets:
        name = sheet.Name
        if name.startswith("XNS"):
            try:
                last_row = sheet.Cells(sheet.Rows.Count, 2).End(-4162).Row  # xlUp
                if last_row < 2:
                    continue
                
                # Read column B (Date) in bulk
                data = sheet.Range(f"B2:B{last_row}").Value
                if data is None:
                    continue
                if not isinstance(data, (tuple, list)):
                    data = ((data,),)

                for row in data:
                    dt = row[0] if isinstance(row, (tuple, list)) else row
                    if isinstance(dt, datetime):
                        months.add((dt.year, dt.month))
            except:
                continue

    if not months:
        return []

    months = sorted(months)
    labels = []
    first_year = months[0][0]

    for y, m in months:
        d = datetime(y, m, 1)
        label = d.strftime("%b").upper()
        if y != first_year:
            label = f"{label}({str(y)[-2:]})"
        labels.append(label)
    return labels

def create_cons_sheet(file_path):
    """Generates the 'CONS' summary sheet using GETPIVOTDATA formulas for consolidated view."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
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
            excel.Calculation = -4135 # xlCalculationManual
        except:
            pass

        wb = excel.Workbooks.Open(file_path)
        months = get_months_from_xns(wb)
        if not months:
            raise ValueError("No months found in XNS sheets. Summary sheet cannot be created.")

        # 1. Parse account details from ANALYSIS
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
        for acc in account_details:
            holder = acc.get("Name of the Account Holder")
            acc_num = acc.get("Account Number")
            if acc_num:
                account_map[str(acc_num)[-4:]] = holder

        # 2. Prep CONS sheet
        try:
            excel.DisplayAlerts = False
            wb.Worksheets("CONS").Delete()
            excel.DisplayAlerts = True
        except:
            pass

        ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
        ws.Name = "CONS"

        pivot_sheets = [s.Name for s in wb.Worksheets if s.Name.startswith("PIVOT")]
        pivot_count = len(pivot_sheets)
        
        # 3. Build Header
        header_vals = ["MONTH"]
        for sheet in pivot_sheets:
            suffix = sheet.replace("PIVOT-", "")
            holder_name = account_map.get(suffix, "")
            if not holder_name:
                holder_name = next((v for k, v in account_map.items() if k in suffix), "")
            header_vals.append(f"{holder_name}\n{suffix}\nPURCHASE")
        header_vals.append("PURCHASE\nTOTAL")
        
        for sheet in pivot_sheets:
            suffix = sheet.replace("PIVOT-", "")
            holder_name = account_map.get(suffix, "")
            if not holder_name:
                holder_name = next((v for k, v in account_map.items() if k in suffix), "")
            header_vals.append(f"{holder_name}\n{suffix}\nSALES")
        header_vals.append("SALES\nTOTAL")

        last_col_idx = START_COL + len(header_vals) - 1
        header_range = ws.Range(ws.Cells(START_ROW, START_COL), ws.Cells(START_ROW, last_col_idx))
        header_range.Value = header_vals

        # Define column indices
        purchase_start_col = START_COL + 1
        purchase_end_col = purchase_start_col + pivot_count - 1
        purchase_total_col = purchase_end_col + 1
        sales_start_col = purchase_total_col + 1
        sales_end_col = sales_start_col + pivot_count - 1
        sales_total_col = sales_end_col + 1

        # 4. Process Data (Build 2D array for bulk write)
        rows_to_paste = []
        for i, month_label in enumerate(months):
            pivot_month = month_label.split("(")[0]
            row_data = [month_label]
            
            r_idx = START_ROW + 2 + (i * 2)
            
            # Purchase formulas
            for sheet in pivot_sheets:
                anchor = wb.Worksheets(sheet).PivotTables(1).TableRange2.Cells(1,1).Address
                formula = f'=IFERROR(GETPIVOTDATA("Sum of DR",\'{sheet}\'!{anchor},"MONTH","{pivot_month}","TYPE","PURCHASE"),"NIL")'
                row_data.append(formula)
            
            p_total_formula = f"=SUM({ws.Cells(r_idx, purchase_start_col).Address}:{ws.Cells(r_idx, purchase_end_col).Address})"
            row_data.append(p_total_formula)
            
            # Sales formulas
            for sheet in pivot_sheets:
                anchor = wb.Worksheets(sheet).PivotTables(1).TableRange2.Cells(1,1).Address
                formula = f'=IFERROR(GETPIVOTDATA("Sum of CR",\'{sheet}\'!{anchor},"MONTH","{pivot_month}","TYPE","SALES"),"NIL")'
                row_data.append(formula)
            
            s_total_formula = f"=SUM({ws.Cells(r_idx, sales_start_col).Address}:{ws.Cells(r_idx, sales_end_col).Address})"
            row_data.append(s_total_formula)
            
            rows_to_paste.append(row_data)
            rows_to_paste.append([None] * len(row_data)) # Spacer row

        if rows_to_paste:
            data_range = ws.Range(ws.Cells(START_ROW + 2, START_COL), ws.Cells(START_ROW + 1 + len(rows_to_paste), last_col_idx))
            data_range.Formula = rows_to_paste

        # 5. Final Row Summary
        last_data_filled_row = START_ROW + 1 + len(rows_to_paste)
        summary_row = last_data_filled_row + 1
        
        ws.Range(ws.Cells(summary_row, START_COL + 1), ws.Cells(summary_row, purchase_end_col)).Merge()
        ws.Cells(summary_row, START_COL + 1).Value = "TOTAL PURCHASE"
        ws.Cells(summary_row, purchase_total_col).Formula = f"=SUM({ws.Cells(START_ROW+1, purchase_total_col).Address}:{ws.Cells(last_data_filled_row, purchase_total_col).Address})"
        
        ws.Range(ws.Cells(summary_row, sales_start_col), ws.Cells(summary_row, sales_end_col)).Merge()
        ws.Cells(summary_row, sales_start_col).Value = "TOTAL SALES"
        ws.Cells(summary_row, sales_total_col).Formula = f"=SUM({ws.Cells(START_ROW+1, sales_total_col).Address}:{ws.Cells(last_data_filled_row, sales_total_col).Address})"

        # Center align the summary row
        summary_row_range = ws.Range(ws.Cells(summary_row, START_COL), ws.Cells(summary_row, sales_total_col))
        summary_row_range.HorizontalAlignment = -4108 # xlCenter
        summary_row_range.VerticalAlignment = -4108   # xlCenter

        # 6. Formatting
        table_range = ws.Range(ws.Cells(START_ROW, START_COL), ws.Cells(summary_row, sales_total_col))
        table_range.Font.Bold = True
        for b_id in [7, 8, 9, 10, 11, 12]:
            table_range.Borders(b_id).LineStyle = 1
            
        numeric_range = ws.Range(ws.Cells(START_ROW + 1, START_COL + 1), ws.Cells(summary_row, sales_total_col))
        numeric_range.NumberFormat = "0.00"
            
        ws.Rows(f"{START_ROW + 1}:{summary_row - 1}").RowHeight = 18
        ws.Rows(summary_row).RowHeight = 40
        for col_idx in range(START_COL, sales_total_col + 1):
            ws.Columns(col_idx).ColumnWidth = 15
            
        p_total_range = ws.Range(ws.Cells(START_ROW, purchase_total_col), ws.Cells(summary_row, purchase_total_col))
        s_total_range = ws.Range(ws.Cells(START_ROW, sales_total_col), ws.Cells(summary_row, sales_total_col))
        p_total_range.Font.ColorIndex = 3
        s_total_range.Font.ColorIndex = 3
        
        header_range.WrapText = True
        header_range.HorizontalAlignment = -4108
        header_range.VerticalAlignment = -4108
        ws.Rows(START_ROW).AutoFit()

        print("CONS sheet created successfully.")
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
