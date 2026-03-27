import os
import sys
import pandas as pd
from pathlib import Path

# ── 1. SETUP DJANGO ENVIRONMENT ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Ensure the backend directory is in sys.path BEFORE any Django imports
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

# Import core logic AFTER django.setup()
from live.views import _parse_software_xns, _categorize_df, _get_bank_name
from api.contra_match import compare_files
from api.helpers import (
    log_processing, format_category_counts, update_processing_log_final
)
from api.models import FileProcessingLog

# ── 2. CORE AUTOMATION LOGIC ──────────────────────────────────────────────────

def safe_print(msg):
    """Prints after sanitizing for console encoding limits."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(str(msg).encode('ascii', 'ignore').decode('ascii'))

def process_folder_in_memory(folder_path, report_date=None, user_name="Automated_System"):
    """Processes software files (matching) and final file (categorization) without saving files."""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        safe_print(f"[ERROR] Folder {folder_path} does not exist.")
        return

    safe_print(f"[INFO] Processing Folder: {folder.name}")
    
    # 1. Collect all Excel files RECURSIVELY (some software files are in subfolders)
    all_files = [f for f in folder.rglob("*.xlsx") if not f.name.startswith("~$")]
    if not all_files:
        safe_print("[WARN] No Excel files found.")
        return

    # 2. Identify XNS files (Software) and FINAL file
    software_file_paths = []
    final_file_path = None
    
    for f_path in all_files:
        if "final" in f_path.name.lower():
            final_file_path = f_path
            break # Found final file, we can proceed

    if not final_file_path:
        safe_print(f"[SKIP] No final file found in: {folder.name}")
        return

    # Now collect software files
    for f_path in all_files:
        try:
            if f_path == final_file_path: continue
            xl = pd.ExcelFile(f_path)
            if 'Xns' in xl.sheet_names:
                software_file_paths.append(f_path)
        except Exception: pass

    # 3. Process Software Files (Contra Match) - IN MEMORY ONLY
    if len(software_file_paths) >= 1:
        safe_print(f"[INFO] Analyzing {len(software_file_paths)} software files (In-Memory)...")
        
        bank_data_storage = {}
        acc_name_storage  = {}
        
        for f_path in software_file_paths:
            try:
                # Parse
                sheet_name, acc_name, acc_type, df, wb_src = _parse_software_xns(str(f_path))
                # Initial categorization
                df = _categorize_df(df, bank_code=sheet_name.split('-')[1].strip())
                
                if sheet_name in bank_data_storage:
                    existing_df = bank_data_storage[sheet_name]
                    if len(df) > len(existing_df):
                        safe_print(f"[INFO] Duplicate sheet '{sheet_name}' found with MORE entries ({len(df)} > {len(existing_df)}). Replacing existing.")
                        bank_data_storage[sheet_name] = df
                        acc_name_storage[sheet_name]  = acc_name
                    else:
                        safe_print(f"[INFO] Duplicate sheet '{sheet_name}' found but has FEWER/EQUAL entries ({len(df)} <= {len(existing_df)}). Ignoring.")
                else:
                    bank_data_storage[sheet_name] = df
                    acc_name_storage[sheet_name]  = acc_name
            except Exception as e:
                safe_print(f"[WARN] Error parsing {f_path.name}: {e}")

        # Run match logic to update TYPE columns in-memory
        if len(bank_data_storage) >= 2:
            safe_print("[INFO] Running Contra-Match engine across files...")
            total_cr_deposit = 0
            for _, dfs in bank_data_storage.items():
                mask = dfs['Category'].str.upper() == 'CASH DEPOSIT'
                if mask.any() and 'CR' in dfs.columns:
                    total_cr_deposit += pd.to_numeric(dfs['CR'][mask], errors='coerce').sum()
            
            bank_data_storage = compare_files(bank_data_storage, acc_name_storage, total_cr_deposit)
        elif len(bank_data_storage) == 1:
            safe_print("[INFO] Single file detected. Applying standalone type categorization...")
            total_cr_deposit = 0
            for sheet_name, df in bank_data_storage.items():
                mask = df['Category'].str.upper() == 'CASH DEPOSIT'
                if mask.any() and 'CR' in df.columns:
                    total_cr_deposit += pd.to_numeric(df['CR'][mask], errors='coerce').sum()
                
            from api.categorize_full import categorize_type
            type_value = 'SALES' if total_cr_deposit > 10_00_000 else 'CASH'
            for sheet_name, df in bank_data_storage.items():
                acc_type = sheet_name.split('-')[-1].strip()
                bank_data_storage[sheet_name] = categorize_type(df, type_value, acc_type)

        # Log Software results to Database
        for sheet_name, df in bank_data_storage.items():
            try:
                counts_str = format_category_counts(df)
                log_processing(
                    user_name=user_name,
                    bank_name=_get_bank_name(sheet_name),
                    file_name=f"{acc_name_storage[sheet_name]} ({sheet_name})",
                    total_entries=len(df),
                    software_count=counts_str,
                    processed_at=report_date
                )
                safe_print(f"[SUCCESS] Software stats saved for: {sheet_name}")
            except Exception as e:
                safe_print(f"[ERROR] Database error for {sheet_name}: {e}")
    
    # 4. Final Data Collection (Reading and Counting Only)
    if final_file_path:
        safe_print(f"[INFO] Reading counts from Final Report: {final_file_path.name}")
        try:
            xl_final = pd.ExcelFile(final_file_path)
            for sn in xl_final.sheet_names:
                if "XNS" in sn.upper():
                    # Read sheet
                    df_f = pd.read_excel(xl_final, sheet_name=sn)
                    # Get formatted counts
                    final_counts = format_category_counts(df_f)
                    
                    # Clean sheet name to ignore OD/CA suffix for matching
                    clean_sn = str(sn).upper().replace("XNS-", "").strip()
                    if len(clean_sn) > 3 and clean_sn[-3] == "-":
                        clean_sn = clean_sn[:-3]
                    
                    # Store results in database
                    update_processing_log_final(clean_sn, final_counts, report_date=report_date)
                    safe_print(f"[SUCCESS] Counts extracted and saved for final sheet: {sn} (Matched as {clean_sn})")
        except Exception as e:
            safe_print(f"[ERROR] Error reading final counts: {e}")

    safe_print(f"[INFO] Finished processing: {folder.name}")

def process_root_folder(root_path):
    root = Path(root_path)
    if not root.exists() or not root.is_dir():
        safe_print(f"[ERROR] Root folder {root_path} does not exist.")
        return

    # Attempt to extract date from folder name (D:\...\12-12-2025)
    report_date = None
    try:
        from datetime import datetime
        folder_name = root.name
        # Expecting DD-MM-YYYY format
        parsed_dt = datetime.strptime(folder_name, "%d-%m-%Y")
        from django.utils import timezone
        report_date = timezone.make_aware(parsed_dt)
        safe_print(f"[INFO] Using Report Date from path: {report_date}")
    except Exception:
        safe_print("[INFO] No valid date found in folder name. Using current time.")

    subfolders = [f for f in root.iterdir() if f.is_dir()]
    safe_print(f"[INFO] Processing {len(subfolders)} subfolders in: {root}")

    for folder in subfolders:
        try:
            process_folder_in_memory(str(folder), report_date=report_date)
        except Exception as e:
            safe_print(f"[ERROR] Fatal error in {folder.name}: {e}")

    safe_print("\n[COMPLETE] ALL COMPLETED. Database entries updated for all folders.")

# ── 3. EXECUTION ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    ROOT_TARGET = r"Y:\FILE WORKING\2026\FEB WORKING"

    for date_folder in os.listdir(ROOT_TARGET):
        process_root_folder(ROOT_TARGET + "\\" + date_folder)
