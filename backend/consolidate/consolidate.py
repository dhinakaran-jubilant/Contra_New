import win32com.client as win32
from datetime import datetime
import pythoncom
import os
import time
import traceback
import re

def validate_and_find_main(excel, file_paths):
    """
    Validates files and identifies the best base file in one pass.
    To be valid, each file needs:
    - Exactly 1 ANALYSIS sheet
    - Minimum 1 PIVOT-XXX sheet
    - Minimum 1 XNS-XXX sheet
    Returns (is_valid, error_msg, main_file, other_files, last_p_count, last_x_count)
    """
    sheet_counts = []
    last_p = 0
    last_x = 0

    for path in file_paths:
        if not os.path.exists(path):
            continue
        
        try:
            wb = excel.Workbooks.Open(path)
            # Use a fast list comprehension to get all names at once
            sheet_names = [sh.Name.upper() for sh in wb.Worksheets]
            wb.Close(False)

            analysis_count = sheet_names.count("ANALYSIS")
            pivot_count = sum(1 for name in sheet_names if "PIVOT" in name)
            xns_count = sum(1 for name in sheet_names if "XNS" in name)
            
            # Validation
            filename = os.path.basename(path)
            errors = []
            if analysis_count != 1:
                errors.append(f"must have 1 'ANALYSIS' sheet (found {analysis_count})")
            if pivot_count < 1:
                errors.append("must have at least 1 'PIVOT' sheet")
            if xns_count < 1:
                errors.append("must have at least 1 'XNS' sheet")
            
            if errors:
                return False, f"File '{filename}' invalid: {', '.join(errors)}.", None, [], 0, 0

            # Store sheet count for main file selection
            sheet_counts.append((path, pivot_count + xns_count))
            last_p, last_x = pivot_count, xns_count

        except Exception as e:
            return False, f"Error processing {os.path.basename(path)}: {str(e)}", None, [], 0, 0

    if not sheet_counts:
        return False, "No valid files found.", None, [], 0, 0

    main_path = None
    for p, _ in sheet_counts:
        if "final" in os.path.basename(p).lower():
            main_path = p
            break
            
    if not main_path:
        max_c = max(c for _, c in sheet_counts)
        main_path = next(p for p, c in sheet_counts if c == max_c)
        
    others = [p for p, _ in sheet_counts if p != main_path]

    return True, "", main_path, others, last_p, last_x

def validate_excel_files(file_paths):
    """Compatibility wrapper for validate_excel_files."""
    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        is_valid, err, _, _, p_count, x_count = validate_and_find_main(excel, file_paths)
        return is_valid, err, p_count, x_count
    except Exception as e:
        return False, f"Validation error: {str(e)}", 0, 0
    finally:
        if excel:
            try: excel.Quit()
            except: pass
        pythoncom.CoUninitialize()

def find_analysis_last_row(sheet):
    """Finds the last row in the ANALYSIS sheet based on the 'FILE NAME' header."""
    try:
        last_row = sheet.Cells(sheet.Rows.Count, 2).End(-4162).Row
        header_row = None
        for i in range(last_row, 0, -1):
            val = sheet.Cells(i, 2).Value
            if val and "FILE NAME" in str(val).upper():
                header_row = i
                break

        if header_row:
            row = header_row + 1
            while sheet.Cells(row, 2).Value not in (None, ""):
                row += 1
            return row - 1
    except Exception as e:
        print(f"Error finding last row: {e}")
    return None

# find_main_file is now deprecated; use validate_and_find_main instead.

def merge_excel_files(file_paths):
    """Main function to consolidate multiple Excel files into one."""
    if not file_paths:
        return None

    pythoncom.CoInitialize()
    excel = None
    main_wb = None
    
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.EnableEvents = False
        try: excel.Calculation = -4135
        except: pass

        # 1. Validate and Identify main file in ONE pass
        is_valid, err, main_path, other_paths, _, _ = validate_and_find_main(excel, file_paths)
        if not is_valid:
            print(err)
            return None

        print(f"Base file: {os.path.basename(main_path)}")

        # 1.5 Create charts for base file and other files BEFORE merging
        from .chart import create_chart_from_pivot
        print(f"Creating charts for base file: {os.path.basename(main_path)}")
        create_chart_from_pivot(main_path)
        
        for op in other_paths:
            print(f"Creating charts for other file: {os.path.basename(op)}")
            create_chart_from_pivot(op)

        main_wb = excel.Workbooks.Open(main_path)
        main_analysis = None
        try: main_analysis = main_wb.Sheets("ANALYSIS")
        except: pass

        pivots_with_charts = set()
        chart_categories = ['NAMES', 'ODD FIG', 'DOUBT', 'BANK FIN', 'RETURN', 'PVT FIN']
        
        main_has_charts = False
        for s in main_wb.Sheets:
            su = s.Name.upper()
            if any(su == c for c in chart_categories):
                main_has_charts = True
                break
        
        if main_has_charts:
            for s in main_wb.Sheets:
                if "PIVOT" in s.Name.upper():
                    pivots_with_charts.add(s.Name.upper())

        # 2. Merge other files
        for other_path in other_paths:
            print(f"Merging: {os.path.basename(other_path)}")
            other_wb = excel.Workbooks.Open(other_path)
            try:
                # Merge ANALYSIS data
                if main_analysis:
                    try:
                        other_analysis = other_wb.Sheets("ANALYSIS")
                        last_row_main = find_analysis_last_row(main_analysis)
                        last_row_other = find_analysis_last_row(other_analysis)

                        if last_row_main and last_row_other:
                            paste_row = last_row_main + 3
                            last_col_other = other_analysis.Cells(last_row_other, other_analysis.Columns.Count).End(-4159).Column
                            copy_range = other_analysis.Range(other_analysis.Cells(1, 1), other_analysis.Cells(last_row_other, last_col_other))
                            copy_range.Copy(main_analysis.Cells(paste_row, 1))
                    except Exception as e:
                        print(f"Could not merge ANALYSIS from {os.path.basename(other_path)}: {e}")

                # ⚠️ SHEET COPYING: Copy PIVOT/XNS and append Charts
                main_sheet_names = {s.Name.upper() for s in main_wb.Sheets}
                insert_pos = main_wb.Sheets("ANALYSIS").Index + 1 if main_analysis else 1
                
                for sheet in other_wb.Sheets:
                    sn_upper = sheet.Name.upper()
                    
                    if "PIVOT" in sn_upper or "XNS" in sn_upper:
                        if sn_upper not in main_sheet_names:
                            sheet.Copy(Before=main_wb.Sheets(insert_pos))
                            main_sheet_names.add(sn_upper)
                            insert_pos += 1

            finally:
                other_wb.Close(False)

        # 3. Update Pivot Tables Data Source
        for ws in main_wb.Sheets:
            if "PIVOT" in ws.Name.upper():
                # Find companion XNS sheet by suffix match
                pivot_suffix = ws.Name.upper().split("PIVOT")[-1].strip("- ")
                xns_sheet = None
                for sh in main_wb.Sheets:
                    if "XNS" in sh.Name.upper() and pivot_suffix in sh.Name.upper():
                        xns_sheet = sh
                        break
                
                if xns_sheet:
                    try:
                        new_source = f"'{xns_sheet.Name}'!$B:$I"
                        for pt in ws.PivotTables():
                            try:
                                new_cache = main_wb.PivotCaches().Create(SourceType=1, SourceData=new_source)
                                pt.ChangePivotCache(new_cache)
                                pt.RefreshTable()
                            except Exception as pt_e:
                                print(f"Failed to update PivotTable in {ws.Name}: {pt_e}")
                    except Exception as e:
                        print(f"Failed to update range for {ws.Name}: {e}")

        # Pre-save: Write metadata for already charted pivots
        if pivots_with_charts:
            try:
                meta_ws = main_wb.Sheets.Add(After=main_wb.Sheets(main_wb.Sheets.Count))
                meta_ws.Name = "SYSTEM_CHART_META"
                for idx, p_name in enumerate(pivots_with_charts):
                    meta_ws.Cells(idx + 1, 1).Value = p_name
                meta_ws.Visible = 2 # xlSheetVeryHidden
            except: pass

        # 4. Save result
        folder = os.path.dirname(main_path)
        base = os.path.splitext(os.path.basename(main_path))[0]
        new_file = os.path.join(folder, f"{base}-CONSOLIDATED.xlsx")
        
        if os.path.exists(new_file):
            try: os.remove(new_file)
            except: pass

        main_wb.SaveAs(new_file, FileFormat=51)
        print(f"Consolidation complete: {new_file}")
        return new_file

    except Exception as e:
        print(f"Error during merge: {e}")
        traceback.print_exc()
        return None
    finally:
        if main_wb:
            try: main_wb.Close(False)
            except: pass
        if excel:
            try:
                excel.Calculation = -4105
                excel.EnableEvents = True
                excel.Quit()
            except: pass
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    pass
