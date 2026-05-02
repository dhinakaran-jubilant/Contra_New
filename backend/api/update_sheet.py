from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from django.conf import settings
from datetime import datetime
import traceback
import gspread
import os
import re

# ── Constants ─────────────────────────────────────────────────────────────────
_KEY_FILE        = r"../robust-shadow-471605-k1-6152c9ae90ff.json"
_SPREADSHEET     = 'Software Testing Report'
_SCOPE           = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]
_BORDERS         = {
    "top":    {"style": "SOLID"},
    "bottom": {"style": "SOLID"},
    "left":   {"style": "SOLID"},
    "right":  {"style": "SOLID"},
}
_GREY_BG         = {"red": 0.90, "green": 0.90, "blue": 0.90}
_WHITE_BG        = {"red": 1.0,  "green": 1.0,  "blue": 1.0}

# ── Private helpers ────────────────────────────────────────────────────────────

def _fallback_has_bg(last_row_num: int) -> bool:
    """Fallback: use row-parity to guess background alternation."""
    return (last_row_num - 2) % 2 == 1


def _build_existing_entries(all_data: list, is_master: bool, is_live: bool) -> set:
    """
    Return a set of fingerprints (tuples) from existing rows.
    We ignore S.No (col 0) and Date (col 1).
    Master/Live: Compare cols 2 through 8 (User, Bank, File, Stats).
    Regular: Compare cols 2 through 7 (Bank, File, Stats).
    """
    entries = set()
    col_start = 2
    col_end   = 9 if (is_master or is_live) else 8

    for row in all_data[1:]: # skip header
        if len(row) < col_end: continue
        # Create a fingerprint tuple of the data columns
        fingerprint = tuple(str(val).strip().lower() for val in row[col_start:col_end])
        entries.add(fingerprint)
    
    return entries


def _get_item_fingerprint(item: dict, is_master: bool, is_live: bool) -> tuple:
    """
    Build a fingerprint tuple from the item dictionary to match _build_existing_entries.
    """
    if is_master or is_live:
        return (
            str(item.get("User Name", "")).strip().lower(),
            str(item.get("Bank Name", "")).strip().lower(),
            str(item.get("File Name", "")).strip().lower(),
            str(item.get("Total Entries (Before)", 0)).strip().lower(),
            str(item.get("Contra Matches (Before)", 0)).strip().lower(),
            str(item.get("Return (Before)", 0)).strip().lower(),
            str(item.get("Total S/W Categorized", 0)).strip().lower()
        )
    else:
        # Regular
        return (
            str(item.get("Bank Name", "")).strip().lower(),
            str(item.get("File Name", "")).strip().lower(),
            str(item.get("Total Entries (Before)", item.get("Total Entries (Manual)", 0))).strip().lower(),
            str(item.get("Contra Matches (Before)", item.get("Total Entries (Software)", 0))).strip().lower(),
            str(item.get("Return (Before)", item.get("Manual Matched", 0))).strip().lower(),
            str(item.get("Total S/W Categorized", item.get("Software Matched", 0))).strip().lower()
        )


def _build_row_data(item: dict, is_live: bool, serial: int, is_master: bool = False) -> list:
    """Build the list of cell values to append for a single report item."""
    today = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    if is_master:
        # Master Log: 14 Columns
        # A:SNo, B:Date, C:User, D:Bank, E:File, F:Total(B), G:Contra(B), H:Return(B), I:SWCat
        # J:Total(F), K:Contra(F), L:Return(F), M:Contra%, N:Return%
        return [
            serial,
            today,
            item.get("User Name", ""),
            item.get("Bank Name", ""),
            item.get("File Name", "").strip(),
            item.get("Total Entries (Before)", 0),
            item.get("Contra Matches (Before)", 0),
            item.get("Return (Before)", 0),
            item.get("Total S/W Categorized", 0),
            "", "", "", "", ""  # Remaining 5 columns for 'Final' update
        ]

    if is_live:
        # Live Report: 9 Columns
        return [
            serial,
            today,
            item.get("User Name", ""),
            item.get("Bank Name", ""),
            item.get("File Name", "").strip(),
            item.get("Total Entries (Before)", 0),
            item.get("Contra Matches (Before)", 0),
            item.get("Total S/W Categorized", 0),
            item.get("Empty TYPE Count", 0), # Fallback/Legacy
        ]

    # Regular Report: 9 Columns
    return [
        serial,
        today,
        item.get("Bank Name", ""),
        item.get("File Name", "").strip(),
        # For regular mode, we might still be using legacy keys if called from old code
        item.get("Total Entries (Before)", item.get("Total Entries (Manual)", 0)),
        item.get("Contra Matches (Before)", item.get("Total Entries (Software)", 0)),
        item.get("Return (Before)", item.get("Manual Matched", 0)),
        item.get("Total S/W Categorized", item.get("Software Matched", 0)),
        item.get("Percentage", "0.00 %"),
    ]


# ── Public API ─────────────────────────────────────────────────────────────────

# ── Sheet Identifiers (Indices or Names) ──────────────────────────────────────
# The user can replace these with actual sheet names: e.g. "Live Report"
_SHEET_LIVE    = 4  
_SHEET_REGULAR = 5
_SHEET_MASTER  = 8  # 9th sheet

def update_google_sheets(summary_report: list, is_live: bool = False) -> bool:
    """
    Update multiple worksheets in the Google Spreadsheet:
    1. The target worksheet (LIVE or REGULAR based on is_live flag).
    2. The MASTER worksheet (9th sheet / index 8).
    """
    try:
        if not os.path.exists(_KEY_FILE):
            print("❌ Google Sheets key file not found")
            return False

        credentials = Credentials.from_service_account_file(_KEY_FILE, scopes=_SCOPE)
        gc          = gspread.authorize(credentials)
        spreadsheet = gc.open(_SPREADSHEET)

        # Update the master sheet (9th sheet)
        print(f"🔄 Updating master sheet (ID: {_SHEET_MASTER})...")
        success_master = _update_single_worksheet(spreadsheet, _SHEET_MASTER, summary_report, is_live=True, is_master=True)

        return success_master

    except Exception as e:
        print(f"❌ Error in update_google_sheets: {e}")
        traceback.print_exc()
        return False


def _update_single_worksheet(spreadsheet, sheet_id_or_name, summary_report: list, is_live: bool, is_master: bool = False) -> bool:
    """
    Internal helper to update the data in a single worksheet.
    Accepts index (int) or name (str).
    """
    try:
        if isinstance(sheet_id_or_name, int):
            sheet = spreadsheet.get_worksheet(sheet_id_or_name)
        else:
            sheet = spreadsheet.worksheet(sheet_id_or_name)

        # ── Existing-data analysis ──────────────────────────────────────────
        all_data = sheet.get_all_values()
        
        if len(all_data) <= 1:
            existing_entries = set()
            next_row         = 2
            should_have_bg   = False
        else:
            existing_entries = _build_existing_entries(all_data, is_master, is_live)
            next_row         = len(all_data) + 1
            last_row_has_bg  = check_last_row_background(sheet, len(all_data))
            should_have_bg   = not last_row_has_bg

        # ── Append new rows (BATCHED) ───────────────────────────────────────
        new_rows_data_to_append = []
        new_rows_meta = []

        for item in summary_report:
            fingerprint = _get_item_fingerprint(item, is_master, is_live)
            if fingerprint in existing_entries:
                print(f"   ⚠️ Skipping duplicate entry: {item.get('File Name')}")
                continue

            row_data = _build_row_data(item, is_live, serial=next_row - 1, is_master=is_master)
            new_rows_data_to_append.append(row_data)
            new_rows_meta.append({'row_number': next_row, 'file_name': item.get("File Name")})
            next_row += 1

        if new_rows_data_to_append:
            sheet.append_rows(new_rows_data_to_append, value_input_option='USER_ENTERED')
            apply_batch_color_simple(sheet, new_rows_meta, should_have_bg, is_live, is_master)
            print(f"   ✅ {sheet.title}: Added {len(new_rows_data_to_append)} rows.")
        
        return True

    except Exception as e:
        print(f"   ❌ Error updating worksheet {sheet_id_or_name}: {e}")
        return False


def update_google_sheets_final(consolidated_path: str) -> bool:
    """
    After consolidation, update the 'Final' columns (10-14) in the Master sheet.
    Finds rows by matching the sheet name (without XNS) in the 'File Name' column.
    """
    try:
        import pandas as pd
        from api.helpers import count_inb_matches, count_return_matches

        # 1. Extract 'Final' stats from consolidated file
        final_stats = {}
        xl = pd.ExcelFile(consolidated_path)
        for sn in xl.sheet_names:
            if "XNS" in sn.upper():
                df = pd.read_excel(xl, sheet_name=sn)
                name_no_xns = sn.upper().replace("XNS-", "").strip()
                final_stats[name_no_xns] = {
                    "total":  len(df),
                    "contra": count_inb_matches(df),
                    "return": count_return_matches(df)
                }

        if not final_stats:
            print("⚠️ No XNS sheets found in consolidated file for final update.")
            return False

        # 2. Update Master Google Sheet
        credentials = Credentials.from_service_account_file(_KEY_FILE, scopes=_SCOPE)
        gc          = gspread.authorize(credentials)
        sheet       = gc.open(_SPREADSHEET).get_worksheet(_SHEET_MASTER)
        rows        = sheet.get_all_values()
        
        for key, stats in final_stats.items():
            key_clean = re.sub(r'[^A-Z0-9]', '', str(key).upper())
            for i, row in enumerate(rows[1:], start=2): # skip header
                if len(row) < 5: continue
                file_name_gs = str(row[4]).upper() # Column E: File Name
                file_name_gs_clean = re.sub(r'[^A-Z0-9]', '', file_name_gs)
                
                if key_clean in file_name_gs_clean:
                    # Found a match! Calculate percentages
                    try:
                        c_before = int(row[6]) if row[6] else 0 # Col G
                        r_before = int(row[7]) if row[7] else 0 # Col H
                        total_f  = stats["total"]
                        contra_f = stats["contra"]
                        return_f = stats["return"]

                        # Calculate percentages: 0/0 = 100% per user request
                        if c_before == 0 and contra_f == 0:
                            c_pct = 100.0
                        else:
                            c_pct = (c_before / contra_f * 100) if contra_f > 0 else 0
                        
                        if r_before == 0 and return_f == 0:
                            r_pct = 100.0
                        else:
                            r_pct = (r_before / return_f * 100) if return_f > 0 else 0

                        # Columns J, K, L, M, N (10, 11, 12, 13, 14)
                        sheet.update(f"J{i}:N{i}", [[
                            total_f, 
                            contra_f, 
                            return_f, 
                            f"{c_pct:.2f}%", 
                            f"{r_pct:.2f}%"
                        ]])
                        print(f"   ✅ Updated 'Final' stats for: {file_name_gs}")
                        break # Move to next key once match found for this key
                    except Exception as e:
                        print(f"   ❌ Error updating row {i}: {e}")

        return True

    except Exception as e:
        print(f"❌ Error in update_google_sheets_final: {e}")
        traceback.print_exc()
        return False


def check_last_row_background(sheet, last_row_num: int) -> bool:
    """
    Return True if the last data row has a grey background; False otherwise.
    """
    if last_row_num < 2:
        return False

    try:
        service        = build('sheets', 'v4', credentials=sheet.spreadsheet.client.auth)
        spreadsheet_id = sheet.spreadsheet.id

        response = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[f"{sheet.title}!A{last_row_num}:I{last_row_num}"],
            includeGridData=True,
        ).execute()

        first_cell = response['sheets'][0]['data'][0]['rowData'][0]['values'][0]
        bg = first_cell.get('effectiveFormat', {}).get('backgroundColor', {})
        r, g, b = bg.get('red', 1.0), bg.get('green', 1.0), bg.get('blue', 1.0)
        return 0.85 <= r <= 0.95 and 0.85 <= g <= 0.95 and 0.85 <= b <= 0.95
    except:
        return _fallback_has_bg(last_row_num)


def apply_batch_color_simple(sheet, new_rows_data: list, should_have_bg: bool, is_live: bool = False, is_master: bool = False) -> None:
    """
    Apply background colour and solid borders to newly-appended rows using a single batch call.
    """
    try:
        if not new_rows_data:
            return

        if is_master:
            col_end = "N"
        elif is_live:
            col_end = "I"
        else:
            col_end = "L"

        bg_colour  = _GREY_BG if should_have_bg else _WHITE_BG
        fmt        = {"backgroundColor": bg_colour, "borders": _BORDERS}

        # Build list of format requests
        formats = []
        for row_info in new_rows_data:
            cell_range = f"A{row_info['row_number']}:{col_end}{row_info['row_number']}"
            formats.append({
                "range": cell_range,
                "format": fmt
            })
        
        # Execute in ONE batch call
        sheet.batch_format(formats)
        print(f"   ✨ Batch formatted {len(formats)} rows in {sheet.title}")

    except Exception as e:
        print(f"❌ Batch formatting error: {e}")
