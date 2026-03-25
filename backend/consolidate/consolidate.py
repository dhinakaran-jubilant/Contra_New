import win32com.client as win32
from datetime import datetime
import pythoncom
import os
import time
import traceback
import re

def validate_excel_files(file_paths):
    """
    Validates that each Excel file has:
    - Exactly 1 ANALYSIS sheet
    - Minimum 1 PIVOT-XXX sheet
    - Minimum 1 XNS-XXX sheet
    """
    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        last_pivot_count = 0
        last_xns_count = 0

        for path in file_paths:
            if not os.path.exists(path):
                continue
            
            wb = excel.Workbooks.Open(path)
            sheet_names = [sh.Name.upper() for sh in wb.Worksheets]
            wb.Close(False)
            
            analysis_count = sheet_names.count("ANALYSIS")
            # Lenient count for validation too
            pivot_count = sum(1 for name in sheet_names if "PIVOT" in name)
            xns_count = sum(1 for name in sheet_names if "XNS" in name)
            
            last_pivot_count = pivot_count
            last_xns_count = xns_count

            filename = os.path.basename(path)
            errors = []
            if analysis_count != 1:
                errors.append(f"must have exactly 1 'ANALYSIS' sheet (found {analysis_count})")
            if pivot_count < 1:
                errors.append("must have at least 1 'PIVOT' sheet")
            if xns_count < 1:
                errors.append("must have at least 1 'XNS' sheet")
            
            if errors:
                return False, f"File '{filename}' is invalid: {', '.join(errors)}.", 0, 0
        
        return True, "", last_pivot_count, last_xns_count
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

def find_main_file(excel, file_paths):
    """Identifies the file with the most PIVOT and XNS sheets to act as the base."""
    sheet_counts = []
    for path in file_paths:
        try:
            wb = excel.Workbooks.Open(path)
            # Lenient count
            count = sum(1 for s in wb.Sheets if "XNS" in s.Name.upper() or "PIVOT" in s.Name.upper())
            sheet_counts.append((path, count))
            wb.Close(False)
        except Exception as e:
            print(f"Error checking {path}: {e}")
            sheet_counts.append((path, 0))

    if not sheet_counts:
        return None, []

    max_count = max(c for _, c in sheet_counts)
    main_file = next(p for p, c in sheet_counts if c == max_count)
    other_files = [p for p, _ in sheet_counts if p != main_file]
    return main_file, other_files

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

        # 1. Identify main file
        main_path, other_paths = find_main_file(excel, file_paths)
        if not main_path:
            return None

        print(f"Base file: {os.path.basename(main_path)}")
        main_wb = excel.Workbooks.Open(main_path)
        main_analysis = None
        try: main_analysis = main_wb.Sheets("ANALYSIS")
        except: pass

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

                # ⚠️ LENTIENT SHEET COPYING: Copy all PIVOT/XNS sheets regardless of prefix
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
