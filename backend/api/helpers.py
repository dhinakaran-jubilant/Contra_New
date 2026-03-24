from . import config
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import re

# ============================================================
# Internal helpers (not exported)
# ============================================================

def _bank_code_from_name(bank_name: str) -> str:
    """
    Return the short bank code for a bank name.
    Falls back to initials if the name is not in SHORT_BANK_NAMES.
    Used in get_sheet_name, create_account_map_from_details, etc.
    """
    try:
        return config.SHORT_BANK_NAMES[bank_name]
    except (KeyError, TypeError):
        cleaned = str(bank_name).replace('India', '').replace(',', '').strip()
        return ''.join(word[0].upper() for word in cleaned.split() if word)


def _add_x_prefix_if_3digit(acc_num: str) -> str:
    """Prepend 'X' to a 3-digit account number; leave 4-digit numbers unchanged."""
    return f"X{acc_num}" if len(acc_num) == 3 else acc_num


def _extract_sheet_details_from_rows(df: pd.DataFrame) -> list:
    """
    Shared logic used by both get_multiple_sheet_name and
    extract_account_details_from_analysis. Iterates the dataframe
    (column B = index 1, column C = index 2) and collects account
    detail blocks delimited by 'Name of the Account Holder' …
    'Account Type'.
    """
    account_details = []
    details = {}
    flag = False
    ignore_keys = {"Address", "Email", "PAN", "Mobile Number"}

    for _, row in df.iterrows():
        key   = row.iloc[1]
        value = row.iloc[2]

        if key == "Name of the Account Holder" or flag:
            if key not in ignore_keys:
                details[key] = value
            flag = True
            if key == "Account Type":
                account_details.append(details)
                details = {}
                flag = False

    return account_details


def _apply_pattern_list(name: str, patterns: list[tuple]) -> str | None:
    """
    Try a list of (regex, formatter) tuples against `name`.
    Returns the formatted string from the first match, or None.
    `formatter` is a callable that receives the match groups and
    returns the canonical string.
    """
    for pattern, formatter in patterns:
        m = re.search(pattern, name)
        if m:
            return formatter(m.groups())
    return None


# ============================================================
# Public functions
# ============================================================

def find_limit(value):
    value = abs(value)
    if value >= 10_000_000:
        crore = round(value / 10_000_000, 1)
        return f"{crore:g}Cr"
    lakh = value / 100_000
    lakh = round(lakh) if lakh >= 10 else round(lakh, 1)
    return f"{lakh:g}L"


def get_downloads() -> Path:
    return Path.home() / "Downloads"


def get_sheet_name(df):
    """Return (sheet_name, account_holder_name) from an Analysis sheet DataFrame."""
    global account_type
    wanted = ["Name of the Account Holder", "Name of the Bank", "Account Number", "Account Type"]
    sub  = df[df[1].isin(wanted)]
    info = dict(zip(sub[1], sub[2]))

    account_number = str(info['Account Number']).strip()
    last_4_digits  = account_number[-4:] if len(account_number) >= 4 else account_number
    account_type   = info['Account Type']
    bank_code      = _bank_code_from_name(info['Name of the Bank'])
    sheet_name     = f"XNS-{bank_code}-{last_4_digits}"
    return sheet_name, info["Name of the Account Holder"]


def get_multiple_sheet_name(df):
    """Return a list of account-detail dicts from an Analysis sheet DataFrame."""
    return _extract_sheet_details_from_rows(df)


def get_month_values(df, date_col):
    temp = pd.DataFrame()
    temp['DATE']       = pd.to_datetime(df[date_col], errors='coerce')
    temp['M_NAME']     = temp['DATE'].dt.strftime("%b").str.upper()
    temp['YEAR']       = temp['DATE'].dt.year
    temp['Y_SHORT']    = temp['DATE'].dt.strftime("%y")
    temp['MAX_YEAR']   = temp.groupby('M_NAME')['YEAR'].transform('max')
    temp['YEAR_COUNT'] = temp.groupby('M_NAME')['YEAR'].transform('nunique')
    mask = (temp['YEAR_COUNT'] > 1) & (temp['YEAR'] == temp['MAX_YEAR'])
    return np.where(mask, temp['M_NAME'] + " (" + temp['Y_SHORT'] + ")", temp['M_NAME'])


def preprocess_category(category):
    return str(category).replace("Transfer from", "").replace("Transfer to", "").strip()


def norm_desc(val):
    return str(val).upper() if val else ""


def get_acc_type(bal):
    non_zero  = bal[bal != 0]
    neg_count = (non_zero < 0).sum()
    pos_count = (non_zero > 0).sum()
    return "OD" if (len(non_zero) > 0 and neg_count > pos_count) else "CA"


def has_date(text):
    return bool(re.search(r'\d{2}[-\/](?:\d{2}|[a-zA-Z]{3})[-\/]\d{2,4}', str(text)))


def update_account_types(df, acc_type=None):
    def determine_type(row):
        if row['Category'] in ['INTEREST', 'INTEREST CHARGES']:
            if acc_type != 'OD':
                return 'EXPENSE'
            desc = str(row.get('Description', '')).upper()
            if has_date(desc) or 'DEBIT' in desc:
                return 'BANK FIN'
            return 'EXPENSE'
        return row.get('TYPE')
    df['TYPE'] = df.apply(determine_type, axis=1)
    return df


def extract_account_details_from_analysis(analysis_df):
    """Extract account detail blocks from a working-file ANALYSIS sheet."""
    return _extract_sheet_details_from_rows(analysis_df)


def create_account_map_from_details(account_details_list: list) -> dict:
    """
    Convert a list of account-detail dicts (from extract_account_details_from_analysis)
    into a dict keyed by the last-4-digit account suffix.
    """
    account_map = {}
    for details in account_details_list:
        if not details:
            continue
        account_number = str(details.get('Account Number', '')).strip()
        if not account_number:
            continue
        last_4   = account_number[-4:] if len(account_number) >= 4 else account_number
        raw_bank = details.get('Name of the Bank', '')
        bank_code = _bank_code_from_name(raw_bank)
        account_map[last_4] = {
            'bank_code':       bank_code,
            'bank_name':       raw_bank,
            'account_suffix':  last_4,
            'account_holder':  details.get('Name of the Account Holder', ''),
            'sheet_name':      f"XNS-{bank_code}-{last_4}",
        }
    return account_map


def extract_account_suffix_from_sheet_name(sheet_name):
    """
    Extract the 3 or 4-digit account suffix from a sheet name.
    Priority: 4-digit > 3-digit.
    """
    if not sheet_name:
        return None

    s = str(sheet_name)

    for pattern in [r'[_-](\d{4})(?:[_-]|$)', r'^(\d{4})[_-]', r'\b(\d{4})\b']:
        m = re.findall(pattern, s, re.IGNORECASE)
        if m:
            return m[0]

    for pattern in [r'[_-](\d{3})(?:[_-]|$)', r'^(\d{3})[_-]', r'\b(\d{3})\b', r'[_-]?X(\d{3})(?:[_-]|$)']:
        m = re.findall(pattern, s, re.IGNORECASE)
        if m:
            return m[0]

    for digits in re.findall(r'\d+', s):
        n = len(digits)
        if n == 4:
            return digits
        if n == 3:
            return digits
        if n > 4:
            last_4 = digits[-4:]
            last_3 = digits[-3:]
            if not (n > 4 and last_4.startswith('0')):
                return last_4
            if not (n > 3 and last_3.startswith('0')):
                return last_3

    return None


def get_numbers(desc):
    text         = re.sub(r"\s+", "", str(desc))
    masked       = re.findall(r"(?:X|x){2,}(\d{3,})", text)
    if masked:
        return masked
    mobk = re.search(r"(?i)^(?:MOBK|INET)\/(\d+)To(\d+)(?:\/[A-Z0-9]*)?\/?" , text)
    if mobk:
        return list(mobk.groups())
    mob = re.search(r"(?i)^MOB/(?:SELFFT|TPFT)/[A-Z0-9 ]*/(\d{10,})$", text)
    if mob:
        return [mob.group(1)]
    od = re.search(r"(?i)(?:OD|CA)(\d+):", text)
    if od:
        return [od.group(1)]
    return []


def extract_acc_suffix_from_key(key):
    """Extract last 4 digits of account number from a key like XNS-BANKCODE-ACCNUM-PRODUCT."""
    for part in key.split("-"):
        clean = part.replace('X', '')
        if len(clean) in (3, 4) and clean.isdigit():
            return clean[-4:]
    return None


def extract_bank_name_from_sheet(sheet_name):
    parts = str(sheet_name).split("-")
    filtered = [p for p in parts if not p.isdigit() and p not in ("XNS", "CA", "OD")]
    return filtered[0] if filtered else None


def normalize_date(date_val):
    if pd.isna(date_val):
        return None
    try:
        if isinstance(date_val, str):
            date_part = date_val.split()[0] if " " in date_val else date_val
            return pd.to_datetime(date_part).normalize()
        if isinstance(date_val, datetime):
            return date_val.normalize()
        return pd.to_datetime(date_val).normalize()
    except Exception:
        return None


def normalize_name(name: str) -> str:
    """Normalize company names by removing common variations."""
    if not name or not isinstance(name, str):
        return ""
    s = str(name).upper().strip()
    s = re.sub(r"^M/S[.\s]*", "", s)
    s = re.sub(r"^THE\s+", "", s)
    s = re.sub(r"^Messrs\s+", "", s)
    s = re.sub(r"\b(PVT|PRIVATE)\s+(LTD|LIMITED)\b", "PVT LTD", s)
    s = re.sub(r"\bPVT\.?\s*LTD\.?\b", "PVT LTD", s)
    s = re.sub(r"\bPRIVATE\s+LIMITED\b", "PVT LTD", s)
    s = re.sub(r"\bLTD\.?\b", "LTD", s)
    s = re.sub(r"\bCO\.?\b", "CO", s)
    s = re.sub(r"\bAND\b", "&", s)
    s = re.sub(r"[^\w\s&]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    parts = [p for p in s.split() if p not in config.TITLE_WORDS]
    return " ".join(parts)


def is_valid_xns_sheet_name(sheet_name):
    name = str(sheet_name).upper().replace(' ', '')
    if name == "XNS":
        return False
    patterns = [
        r'^XNS[-_][A-Z]{3,5}[-_]\d{3,4}[-_][A-Z]{2}$',
        r'^XNS[-_]\d{3,4}[-_][A-Z]{3,5}[-_][A-Z]{2}$',
        r'^[A-Z]{3,5}[-_]\d{3,4}[-_][A-Z]{2}[-_]XNS$',
        r'^[A-Z]{3,5}[-_]\d{3,4}[-_][A-Z]{2}$',
        r'^\d{3,4}[-_][A-Z]{3,5}[-_][A-Z]{2}$',
    ]
    return any(re.match(p, name) for p in patterns)


def canonical_sheet_id(name: str) -> str:
    """
    Convert any recognised sheet-name variant to a canonical
    BANKCODE-ACCNUM-PRODUCT string (e.g. 'SBI-X987-CA').
    Returns '' for invalid / unrecognised names.
    """
    name = str(name).strip().upper().replace(' ', '')

    if name == "XNS" or re.search(r'^XNS[-_]\d+$', name):
        print(f"❌ Invalid sheet name in canonical_sheet_id: '{name}'")
        return ""

    print(f"🔍 canonical_sheet_id processing: '{name}'")

    def _fmt_bap(groups):
        bank, acc, prod = groups
        acc = _add_x_prefix_if_3digit(acc)
        return f"{bank}-{acc}-{prod}"

    def _fmt_abp(groups):
        acc, bank, prod = groups
        acc = _add_x_prefix_if_3digit(acc)
        return f"{bank}-{acc}-{prod}"

    patterns = [
        (r'^XNS[-_]?([A-Z]{3,5})[-_]?(\d{3,4})[-_]?([A-Z]{2})$', _fmt_bap),  # P1
        (r'^XNS[-_]?(\d{3,4})[-_]?([A-Z]{3,5})[-_]?([A-Z]{2})$', _fmt_abp),  # P2
        (r'^([A-Z]{3,5})[-_]?(\d{3,4})[-_]?([A-Z]{2})[-_]?XNS$', _fmt_bap),  # P3
        (r'^([A-Z]{3,5})[-_]?(\d{3,4})[-_]?([A-Z]{2})$',          _fmt_bap),  # P4
        (r'^(\d{3,4})[-_]?([A-Z]{3,5})[-_]?([A-Z]{2})$',          _fmt_abp),  # P5
    ]

    for i, (pattern, formatter) in enumerate(patterns, 1):
        m = re.search(pattern, name)
        if m:
            result = formatter(m.groups())
            print(f"   Pattern {i} matched: {result}")
            return result

    print(f"   No pattern matched, returning empty string for: '{name}'")
    return ""


def generate_summary_report(matched_df, df_storage, separate_canon_map, final_canon_map, final_file_label, acc_name_storage):
    summary_data = []
    print("🔍 Generating summary report...")
    print(f"Files in matched_df: {list(matched_df.keys())}")
    print(f"Files in separate_canon_map: {list(separate_canon_map.keys())}")

    for canon, sep_sheet in separate_canon_map.items():
        final_sheet = final_canon_map.get(canon)
        if final_sheet is None:
            print(f"⚠️ Skipping {sep_sheet} - no matching final sheet")
            continue
        if sep_sheet not in matched_df:
            print(f"⚠️ {sep_sheet} not in matched_df, skipping")
            continue

        auto_df_full   = matched_df.get(sep_sheet)
        manual_df_full = df_storage.get(final_sheet)
        if auto_df_full is None or manual_df_full is None:
            print(f"⚠️ Skipping {sep_sheet} - missing data")
            continue

        manual_matched   = len(manual_df_full[manual_df_full["TYPE"].astype(str).str.contains("UNMAT", case=False, na=False)])
        software_matched = len(auto_df_full[auto_df_full["TYPE"].astype(str).str.contains("UNMAT", case=False, na=False)])
        percentage       = (software_matched / manual_matched * 100) if manual_matched > 0 else 0

        acc_name     = acc_name_storage.get(sep_sheet, "")
        safe_acc_name = acc_name.replace("/", "_")
        parts = sep_sheet.split("-")
        if "XNS" in parts:
            parts.remove("XNS")
        file_name = f"{safe_acc_name}-{'-'.join(parts)}"

        bank_value = extract_bank_name_from_sheet(sep_sheet)
        bank_name  = next((k for k, v in config.SHORT_BANK_NAMES.items() if v == bank_value), "Unknown Bank")

        summary_data.append({
            "File Name":               file_name,
            "Bank Name":               bank_name,
            "Total Entries (Manual)":  len(manual_df_full),
            "Total Entries (Software)": len(auto_df_full),
            "Manual Matched":          manual_matched,
            "Software Matched":        software_matched,
            "Percentage":              f"{percentage:.2f}%",
        })
        print(f"✅ Added to summary: {file_name}")

    print(f"📊 Summary report generated for {len(summary_data)} files")
    return summary_data


def reformat_final_sheet_name(sheet_name: str) -> str:
    """
    Normalise any recognised sheet-name variant to a canonical form.
    3-digit account numbers get an 'X' prefix.
    """
    name = str(sheet_name).replace(" ", "").strip().upper()
    print(f"🔍 Processing sheet name: '{name}'")

    def _fmt_bap_xns(groups):
        bank, acc, prod = groups
        acc = _add_x_prefix_if_3digit(acc)
        return f"XNS-{bank}-{acc}-{prod}"

    def _fmt_bap_plain(groups):
        bank, acc, prod = groups
        acc = _add_x_prefix_if_3digit(acc)
        return f"{bank}-{acc}-{prod}"

    def _fmt_abp_xns(groups):
        acc, bank, prod = groups
        acc = _add_x_prefix_if_3digit(acc)
        return f"XNS-{bank}-{acc}-{prod}"

    patterns = [
        # P1 — BANKCODE-3digit-PRODUCT  → needs X prefix, plain output
        (r'^([A-Z]{3,5})[-_]?(\d{3})[-_]?([A-Z]{2})$',           _fmt_bap_plain),
        # P2 — BANKCODE-4digit-PRODUCT  → plain output
        (r'^([A-Z]{3,5})[-_]?(\d{4})[-_]?([A-Z]{2})$',           _fmt_bap_plain),
        # P3 — XNS-ACCNUM-BANKCODE-PRODUCT → XNS-prefixed output
        (r'^XNS[-_]?(\d{3,4})[-_]?([A-Z]{3,5})[-_]?([A-Z]{2})$', _fmt_abp_xns),
        # P4 — BANKCODE-ACCNUM-PRODUCT-XNS → XNS-prefixed output
        (r'^([A-Z]{3,5})[-_]?(\d{3,4})[-_]?([A-Z]{2})[-_]?XNS$', _fmt_bap_xns),
        # P5 — XNS-BANKCODE-ACCNUM-PRODUCT → XNS-prefixed output (already canonical)
        (r'^XNS[-_]?([A-Z]{3,5})[-_]?(\d{3,4})[-_]?([A-Z]{2})$', _fmt_bap_xns),
    ]

    for i, (pattern, formatter) in enumerate(patterns, 1):
        m = re.search(pattern, name)
        if m:
            result = formatter(m.groups())
            print(f"🔁 Reformatted (pattern {i}): '{name}' -> '{result}'")
            return result

    print(f"ℹ️  No reformatting needed for: '{name}'")
    return sheet_name
def count_inb_matches(df: pd.DataFrame) -> int:
    """Count rows whose TYPE is one of the match types (INB TRF / SIS CON)."""
    MATCH_TYPES = ["INB TRF", "SIS CON"]
    if 'TYPE' not in df.columns:
        return 0
    return len(df[df["TYPE"].astype(str).str.upper().isin(MATCH_TYPES)])


def count_return_matches(df: pd.DataFrame) -> int:
    """Count rows whose TYPE is 'RETURN'."""
    if 'TYPE' not in df.columns:
        return 0
    return len(df[df["TYPE"].astype(str).str.upper() == "RETURN"])


def log_processing(user_name, file_name, bank_name, total_entries, software_count=None, final_count=None, processed_at=None):
    """Save a processing log entry to the database, skipping duplicates within 10s."""
    from api.models import FileProcessingLog
    from django.utils import timezone
    from datetime import timedelta

    try:
        # 1. Proactively ensure the logging table exists
        from django.db import connection, transaction
        table_name = FileProcessingLog._meta.db_table
        
        # Check presence in the list of existing tables
        if table_name not in connection.introspection.table_names():
            from django.core.management import call_command
            print(f"🔄 Table '{table_name}' missing from DB. Attempting recovery...")
            
            # ATTEMPT A: Standard Migration
            try:
                call_command('migrate', 'api', interactive=False)
            except Exception as migrate_err:
                print(f"⚠️ Standard migration attempt failed: {migrate_err}")

            # Refresh connection and check again
            connection.close()
            if table_name not in connection.introspection.table_names():
                # ATTEMPT B: Raw SQL Fallback (Cross-DB)
                print(f"⚠️ Table still missing. Falling back to raw SQL for '{table_name}'...")
                engine = connection.settings_dict.get('ENGINE', '')
                id_sql   = "SERIAL PRIMARY KEY" if "postgres" in engine else "INTEGER PRIMARY KEY AUTOINCREMENT"
                
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            id {id_sql},
                            user_name VARCHAR(150),
                            file_name VARCHAR(255),
                            bank_name VARCHAR(100),
                            processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            total_entries INTEGER DEFAULT 0,
                            software_count TEXT,
                            final_count TEXT
                        )
                    """)
                print(f"[SUCCESS] Table '{table_name}' forced creation via raw SQL.")

        # 2. Check for duplicate within the last 10 seconds
        if not processed_at:
            ten_seconds_ago = timezone.now() - timedelta(seconds=10)
            exists = FileProcessingLog.objects.filter(
                user_name=str(user_name).upper(),
                file_name=file_name,
                bank_name=bank_name,
                total_entries=total_entries,
                processed_at__gte=ten_seconds_ago
            ).exists()

            if exists:
                print(f"⏩ Duplicate log ignored for {file_name}")
                return None

        # 3. Create entry
        params = {
            "user_name": str(user_name).upper(),
            "file_name": file_name,
            "bank_name": bank_name,
            "total_entries": total_entries,
            "software_count": software_count,
            "final_count": final_count,
        }
        if processed_at:
            params["processed_at"] = processed_at

        return FileProcessingLog.objects.create(**params)
        print(f"📊 Process log saved for {file_name}")
    except Exception as e:
        print(f"⚠️ Failed to log processing for {file_name}: {e}")


def get_category_counts(df: pd.DataFrame) -> dict:
    """Return a dictionary of counts for each 'TYPE' category, including sub-categories for specific types."""
    if 'TYPE' not in df.columns:
        return {}
    
    # 1. Get top-level TYPE counts
    type_counts_raw = df['TYPE'].astype(str).str.strip().str.upper().value_counts().to_dict()
    cleaned_counts = {}
    
    # Define which types should have their sub-categories expanded
    # User-defined exclusion: EXCEPT inb trf, sis con, and unmatch*
    EXCLUDE_EXPANSION = ["INB TRF", "SIS CON", "SIS-CON", "INB-TRF"]

    for type_key, v in type_counts_raw.items():
        if not type_key or type_key == "NAN":
            type_key = "UNCATEGORIZED"
            
        cleaned_counts[type_key] = int(v)
        
        # 2. Get sub-category breakdown if:
        # - Category column exists
        # - type_key is NOT in exclusion list
        # - type_key does NOT start with UNMATCH
        should_expand = (
            type_key not in EXCLUDE_EXPANSION and 
            not type_key.startswith("UNMATCH") and
            "Category" in df.columns
        )

        if should_expand:
            sub_df = df[df['TYPE'].astype(str).str.strip().str.upper() == type_key]
            if not sub_df.empty:
                sub_counts_raw = sub_df["Category"].value_counts().to_dict()
                for sub_k, sub_v in sub_counts_raw.items():
                    sub_key = str(sub_k).strip().upper() if pd.notna(sub_k) and str(sub_k).strip() else "UNKNOWN"
                    # Add as secondary entry with specific prefix for display
                    cleaned_counts[f"{type_key} > {sub_key}"] = int(sub_v)
            
    return cleaned_counts


def format_category_counts(df: pd.DataFrame) -> str:
    """Return a formatted string like [inb_trf: 10, sis_con: 15, ...] from dataframe categories."""
    if df is None or df.empty or 'TYPE' not in df.columns:
        return ""
    
    counts = get_category_counts(df)
    if not counts:
        return ""
        
    # Format as: [KEY: VAL, KEY: VAL, ...]
    items = [f"{str(k).lower().replace(' ', '_')}: {v}" for k, v in counts.items()]
    return f"[{', '.join(items)}]"


def update_processing_log_final(sheet_id: str, final_count_str: str, report_date=None):
    """
    Finds existing log entries where the file_name contains the sheet_id 
    and updates their final_count. Uses report_date window if provided.
    """
    try:
        from .models import FileProcessingLog
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Q
        
        # Calculate search window (24h around report date)
        base_date = report_date if report_date else timezone.now()
        start_window = base_date - timedelta(hours=24)
        end_window   = base_date + timedelta(hours=24)
        
        # Clean the sheet_id
        clean_id = str(sheet_id).upper().replace("-XNS", "").replace("-PIVOT", "").replace("_", "-").strip()
        
        # Target logs with empty final_count within the time window
        logs = FileProcessingLog.objects.filter(
            Q(final_count="") | Q(final_count__isnull=True),
            file_name__icontains=clean_id,
            processed_at__range=(start_window, end_window)
        ).order_by('-processed_at')
        
        if logs.exists():
            log = logs.first()
            log.final_count = final_count_str
            log.save()
            print(f"[SUCCESS] Updated final_count for log: {log.file_name} with ID: {clean_id}")
            return True
        else:
            print(f"[INFO] No matching log found for ID: {clean_id} near {base_date.strftime('%Y-%m-%d')}")
            return False
    except Exception as e:
        print(f"⚠️ Failed to update processing log for {sheet_id}: {e}")
        return False


def parse_metric(metric_str: str, keys: list = None) -> int:
    """
    Parse a metric string like '[key1: 10, key2: 5]' and return the sum of values.
    If 'keys' is provided (e.g. ['inb_trf', 'sis_con']), only sum values for those specific keys.
    """
    if not metric_str or not isinstance(metric_str, str):
        return 0
    
    # Remove brackets
    s = metric_str.strip().strip('[]')
    if not s:
        return 0
        
    total = 0
    # Split by comma
    parts = s.split(',')
    for part in parts:
        if ':' not in part:
            continue
        try:
            k, v = part.split(':', 1)
            k = k.strip().lower()
            val_str = v.strip()
            # If keys is None, sum numerical values EXCLUDING 'uncategorized' and sub-categories (containing '>')
            if keys is None:
                if k != 'uncategorized' and '>' not in k and '_>_' not in k:
                    total += int(val_str)
            else:
                # If keys list provided, match against keys (lowercase)
                if k in [str(kn).lower() for kn in keys]:
                    total += int(val_str)
        except (ValueError, IndexError):
            continue
            
    return total
