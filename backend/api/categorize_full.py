from pandas.tseries.offsets import MonthBegin
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from api import helpers
import pandas as pd
import numpy as np
import re

# ── Keyword sets ──────────────────────────────────────────────────────────────
INWARD_KEYWORDS      = {'INW', 'INWARD', 'I/W', 'IW'}
OUTWARD_KEYWORDS     = {'OUTWARD', 'O/W', 'OWRTN', 'OW RET', 'OW REJ', 'OW CHQ', 'OW RTN'}
CHARGE_KEYWORDS      = {'CHARGE', 'CHRG', 'CHG', 'CHRGE', 'CHR', 'FEE', 'CRG'}
ECS_KEYWORDS         = {'ECS', 'ACH', 'EMI', 'AUTOPAY'}
NEFT_KEYWORDS        = {'NEFT', 'EFT', 'NFT', 'INFT', 'IFT'}
RTGS_KEYWORDS        = {'RTGS', 'RTG', 'TGS'}
RETURN_KEYWORDS      = {'RTN', 'RETURN', 'RET'}
CHEQUE_KEYWORDS      = {'CHQ', 'CHEQUE'}
FUNDS_INSUFFICIENT   = {'FUNDS', 'NSUFFICIENT'}
EXCEEDS_ARRANGEMENT  = {'EXCEEDS', 'RRANGEMENT'}
INSURANCE_KEYWORDS   = {'INSURANCE', 'INTEREST', 'INVESTMENT EXPENSE', 'LOAN REPAYMENT'}
WITHDRAWAL_KEYWORDS  = {'WITHDR', 'W/D', 'THDRAWAL', 'WDL', 'CSW', 'ATW', 'WITHDRAWL'}
PETTY_CASH_KEYWORDS  = {'PETTI', 'PETTY', 'PETT'}
CASH_KEYWORDS        = {'CASH', 'CAS', 'CSH'}
REVERSAL_KEYWORDS    = {'REV', 'REFUND', 'RVSL', 'REVRSD', 'REVERSED', 'REVERSAL', 'RETRACT'}
EPFO_KEYWORDS        = {'EPFO', 'PF', 'EPF', 'PROVIDENT', 'ESHP'}
PENAL_KEYWORDS       = {'PENAL', 'ENAL', 'PEN', 'OVERDUE', 'PNL'}
INTEREST_KEYWORDS    = {'INTEREST', 'INTERST', 'INTREST'}
EB_KEYWORDS          = {'ELECTRICITY', 'ELECTRIC', 'EB', 'EBBILL'}
SALARY_KEYWORDS      = {'SALARY', 'SALREY', 'SLARY', 'STAFF SALA', 'SALAY', 'SALAR'}

CHARGE_LIMIT    = 1000
OW_CHARGE_LIMIT = 300

# ── Pre-compiled patterns ──────────────────────────────────────────────────────
_BOUNDARY  = r'(?:^|/|-|\s){kw}(?:$|/|-|\s)'
_BOUNDARY2 = r'(?:^|/|-|\s|_|:){kw}(?:$|/|-|\s|_|:)'

RE_BNA_CAM_CDM     = re.compile(r'(?:^|/|-|\s)(BNA|CAM|CDM)(?:$|/|-|\s)', re.IGNORECASE)
RE_ATM             = re.compile(r'(?:^|/|-|\s)ATM(?:$|/|-|\s)', re.IGNORECASE)
RE_UPI             = re.compile(r'(?:^|/|-|\s)UPI(?:$|/|-|\s)', re.IGNORECASE)
RE_CASH            = re.compile(r'(?:^|/|-|\s)CASH(?:$|/|-|\s)', re.IGNORECASE)
RE_BOUNCE_CHQ      = re.compile(r"[()\\s]*(?:BOUNCE|REJECT|RETURNED|RET|ISSUED|RTN|RTRN)[()\\s:/\\-]*(\d+)", re.IGNORECASE)
RE_HDFC_EMI        = re.compile(r"\bEMI\s+(\d+)\b(?=.*\bCHQ\b)", re.IGNORECASE)
RE_HDFC_EMI_CHQ    = re.compile(r"(?i)^EMI\s+.*CHQ\s+([A-Z0-9]+)", re.IGNORECASE)
RE_RETURNS_SUMMARY = re.compile('O/W CHQ RTN|I/W CHQ RTN|I/W ECS RTN|I/W ECS MANDATE|I/W RTGS RTN|I/W NEFT RTN|I/W IMPS RTN')

# ── Private helpers ────────────────────────────────────────────────────────────

def _bsearch(kw: str, text: str) -> bool:
    return bool(re.search(_BOUNDARY.replace('{kw}', kw), text))

def _bsearch2(kw: str, text: str) -> bool:
    return bool(re.search(_BOUNDARY2.replace('{kw}', kw), text))

def _any_bsearch(keywords, text: str, pattern_fn=None) -> bool:
    fn = pattern_fn or _bsearch
    return any(fn(kw, text) for kw in keywords)

def _any_in(keywords, text: str) -> bool:
    if not isinstance(text, str): return False
    return any(kw in text for kw in keywords)

def _all_in(keywords, text: str) -> bool:
    if not isinstance(text, str): return False
    return all(kw in text for kw in keywords)

# ── Public helpers ─────────────────────────────────────────────────────────────

def word_in_description(word, description, threshold=0.75, min_len=3):
    word_clean = str(word).strip().lower()
    desc_clean = str(description).strip().lower()
    if not word_clean or not desc_clean: return False

    word_words = re.findall(r'\w+', word_clean)
    desc_words = re.findall(r'\w+', desc_clean)

    def single_word_match(w):
        if len(w) < min_len: return False
        if re.search(r'\b' + re.escape(w) + r'\b', desc_clean): return True
        return any(SequenceMatcher(None, w, d).ratio() >= threshold for d in desc_words if len(d) >= min_len)

    matches = [single_word_match(w) for w in word_words]
    return sum(matches) >= max(1, len(word_words) - 1)

def strings_similar(str1, str2, threshold=0.9):
    return SequenceMatcher(None, str1, str2).ratio() >= threshold

def is_fuzzy_match(a, b, threshold=75):
    if not a or not b: return False
    return fuzz.token_sort_ratio(a, b) >= threshold

def normalize_text(text):
    if pd.isna(text): return ''
    return str(text).upper().replace(',', '').replace('.', '').replace('TRANSFER TO', '').strip()

# ── Scalar function for fallback ──────────────────────────────────────────────

def categorize_desc_text_row(desc, category, cr=None, dr=None):
    if pd.isna(desc) or pd.isna(category): return category
    
    desc_str = str(desc).upper()
    cat_str = str(category).upper().strip()
    norm_desc_str = desc_str.replace(' ', '')
    has_cr, has_dr = not pd.isna(cr), not pd.isna(dr)
    has_neft, has_rtgs = _any_in(NEFT_KEYWORDS, desc_str), _any_in(RTGS_KEYWORDS, desc_str)
    has_upi = bool(RE_UPI.search(desc_str))

    # --- Re-categorization rules ---
    if cat_str in ('ENTERTAINMENT', 'CLOTHING', 'PERSONAL CARE', 'FOOD', 'ALCOHOL', 'CASH BACK', 'LOGISTICS', 'MEDICAL', 'SUBSIDY', 'VEHICLE SERVICING'):
        return cat_str
    elif cat_str in ('FUEL', 'TRAVEL', 'UTILITIES'):
        return 'EXPENSE'
    
    if cat_str == 'REVERSAL' and not has_neft and not has_rtgs: return 'REVERSAL'

    elif (cat_str == 'CASH DEPOSIT' or 'CASH DEPOSIT' in desc_str) and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi:
        if _any_bsearch(REVERSAL_KEYWORDS, desc_str) or cat_str == 'REVERSAL': return 'REVERSAL'
        elif _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str):
            if has_dr and cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'CASH WITHDRAWAL'): return 'CASH WITHDRAWAL'
            return 'REVERSAL' if has_cr else category
        elif has_cr and not has_neft: return 'CASH DEPOSIT'
        return category

    elif (RE_BNA_CAM_CDM.search(desc_str) or 'BY CASH' in desc_str) and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi:
        if _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str):
            if has_dr and cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'CASH WITHDRAWAL'): return 'CASH WITHDRAWAL'
            return 'REVERSAL' if has_cr else category
        elif _any_bsearch(REVERSAL_KEYWORDS, desc_str) or cat_str == 'REVERSAL': return 'REVERSAL'
        return 'CASH DEPOSIT' if has_cr else category

    elif RE_ATM.search(desc_str) and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi:
        if has_dr and cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'CASH WITHDRAWAL'): return 'CASH WITHDRAWAL'
        return category

    elif (cat_str == 'CASH WITHDRAWAL' or ((cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'TRANSFER TO SELF') and ('ATM' in desc_str or _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str)))
              or _bsearch('ATW', desc_str) or 'ATM CSW' in desc_str or strings_similar('CASH WITHDRAWAL', cat_str.replace('TRANSFER TO', '').strip()) or word_in_description('CASH WITHDRAWAL', desc_str) or (_any_in(CHEQUE_KEYWORDS, desc_str) and _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str)))
          ) and cat_str != 'BANK CHARGES' and 'TRANSFER' not in desc_str and 'TFR' not in desc_str and 'TAX' not in desc_str and 'TAX' != cat_str \
          and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi and not has_neft and 'REMITTANCE' not in desc_str:
        if has_dr: return 'CASH WITHDRAWAL'
        return 'REVERSAL' if has_cr else category

    elif (RE_CASH.search(cat_str) or (RE_CASH.search(desc_str) and cat_str == 'TRANSFER TO SELF') or (('CHED' in desc_str or 'MDSE' in desc_str) and (RE_CASH.search(desc_str) or 'CASH PAID' in desc_str) and 'SELF' in desc_str)) \
          and not has_upi and cat_str != 'BANK CHARGES':
        if has_cr: return 'CASH DEPOSIT'
        return 'CASH WITHDRAWAL' if has_dr else category

    elif cat_str in ('CASH WITHDRAWAL', 'CASH DEPOSIT'): return cat_str
    elif cat_str == 'OTHERS' and _any_bsearch2(REVERSAL_KEYWORDS, desc_str) and not _any_in(RETURN_KEYWORDS, desc_str): return 'REVERSAL' if has_cr else category
    
    elif cat_str == 'OTHERS' and has_dr:
        if (_any_in(CHARGE_KEYWORDS, desc_str) and not (_any_bsearch2(PENAL_KEYWORDS, desc_str) or _any_in(RETURN_KEYWORDS, desc_str) or _any_in(CHEQUE_KEYWORDS, desc_str) or _any_bsearch2(ECS_KEYWORDS, desc_str) or _any_in(('NACH', 'MAND', 'MANDATE'), desc_str) or _any_in(('STOP', 'CHARGEBACK'), desc_str))) \
                or _any_in(('BOXRENT', 'SOUNDBOX', 'COMMISS', 'POS', 'REMIT'), norm_desc_str) or (_any_in(('RECOVERY', 'RCVRY'), desc_str) and 'INTEREST' not in desc_str) or any('SC' == w for w in desc_str.split(' ')):
            return 'BANK CHARGES'
        elif _any_in(('TAX', 'GST', 'TINCBDT', 'TDS', 'ITD'), desc_str) and not (_any_in(CHEQUE_KEYWORDS, desc_str) or _any_in(RETURN_KEYWORDS, desc_str)):
            return 'BANK CHARGES' if 'NESL' in desc_str else 'TAX'
        elif _any_bsearch2(PENAL_KEYWORDS, desc_str): return 'PENAL CHARGES'
        elif _any_bsearch2(INTEREST_KEYWORDS, desc_str) and not _any_in(CHARGE_KEYWORDS, desc_str): return 'INTEREST'
        elif _any_in(EPFO_KEYWORDS, desc_str): return 'EPFO'
        elif 'TANGEDCO' in norm_desc_str or 'ELECTRICITY' in norm_desc_str: return 'EB BILL'
        return category

    elif cat_str == 'BANK CHARGES' and has_dr and (not (_any_in(RETURN_KEYWORDS, desc_str) or _any_in(CHEQUE_KEYWORDS, desc_str) or _any_bsearch2(ECS_KEYWORDS, desc_str) or _any_in(('NACH', 'MAND', 'MANDATE'), desc_str) or _any_in(INWARD_KEYWORDS, desc_str) or _any_in(OUTWARD_KEYWORDS, desc_str) or _any_in(('STOP', 'MANDATE', 'DRAWDOWN', 'EMANCH', 'TAX', 'CSW'), desc_str) or _all_in(FUNDS_INSUFFICIENT, desc_str) or _all_in(EXCEEDS_ARRANGEMENT, desc_str)) or (_any_in(CHEQUE_KEYWORDS, desc_str) and _any_in(('BOOK', 'COURIER'), desc_str) and not _any_in(RETURN_KEYWORDS, desc_str))):
        return 'BANK CHARGES'

    elif cat_str == 'TRANSFER OUT' and has_dr:
        if 'ESIC' in desc_str: return 'ESIC'
        elif ('REMIT' in desc_str or 'RENT' in desc_str or _any_in(CHARGE_KEYWORDS, norm_desc_str) or any('SC' == w for w in desc_str.split(' '))) and not (_any_in(RETURN_KEYWORDS, desc_str) or _any_in(CHEQUE_KEYWORDS, desc_str) or _any_bsearch2(ECS_KEYWORDS, desc_str) or _any_in(('NACH', 'MAND', 'MANDATE'), desc_str)):
            return 'BANK CHARGES'
        elif _any_in(INTEREST_KEYWORDS, norm_desc_str): return 'INTEREST'
        elif _any_in(EPFO_KEYWORDS, desc_str): return 'EPFO'
        elif 'TANGEDCO' in norm_desc_str or 'ELECTRICITY' in norm_desc_str: return 'EB BILL'
        elif _any_in(SALARY_KEYWORDS, norm_desc_str): return 'SALARY'
        elif 'BONUS' in desc_str: return 'BONUS'
        return category

    elif cat_str == 'TRANSFER IN' and has_cr:
        if _any_in(SALARY_KEYWORDS, norm_desc_str): return 'SALARY'
        return 'BONUS' if 'BONUS' in desc_str else category

    elif cat_str == 'INTEREST CHARGES' and has_dr: return 'INTEREST CHARGES'
    elif _any_in(INTEREST_KEYWORDS, cat_str.replace('TRANSFER TO', '')) and has_dr: return 'INTEREST'
    elif cat_str == 'TAX' and not _any_in(RETURN_KEYWORDS, desc_str):
        if has_dr: return 'TAX'
        return 'REVERSAL' if has_cr else category
    elif ((_any_bsearch2(EPFO_KEYWORDS, desc_str) or 'EPFO' in desc_str) and cat_str != 'BANK CHARGES' or cat_str == 'PROVIDENT FUND CONTRIBUTION') and has_dr: return 'EPFO'
    elif cat_str == 'PROVIDENT FUND WITHDRAWAL' and has_cr: return 'PF WITHDRAWAL'
    elif cat_str == 'HOUSE RENT': return 'RENT'
    elif cat_str == 'INTEREST' and 'INT TRF' not in desc_str: return 'INTEREST'
    elif cat_str in ('CARD SETTLEMENT', 'CREDIT CARD PAYMENT', 'BELOW MIN BALANCE', 'ADVANCE SALARY PAID', 'SALARY PAID', 'UPI SETTLEMENT', 'ONLINE SHOPPING', 'INSURANCE'): return 'UPI' if cat_str == 'UPI SETTLEMENT' else cat_str
    
    elif cat_str == 'PENAL CHARGES' and has_dr:
        if _any_in(('TAX', 'GST', 'TINCBDT', 'TDS', 'ITD'), desc_str) and not has_neft: return 'TAX'
        return 'PENAL CHARGES'

    elif 'TRANSFER FROM' in cat_str or 'TRANSFER TO' in cat_str:
        if 'UPI' in desc_str and 'SELF' not in cat_str: return 'UPI'
        elif 'TANGEDCO' in norm_desc_str or 'ELECTRICITY' in norm_desc_str: return 'EB BILL'
        elif _any_in(('TAX', 'GST', 'TINCBDT', 'TDS', 'ITD'), desc_str): return 'TAX' if not has_neft and has_dr else category
        elif _bsearch2('ESIC', desc_str): return 'ESIC'
        elif _any_bsearch2(EPFO_KEYWORDS, desc_str): return 'EPFO'
        elif ('P CHARGE' in desc_str or 'PNLCHRG' in norm_desc_str or _any_bsearch2(PENAL_KEYWORDS, desc_str)) and has_dr: return 'PENAL CHARGES'
        elif _bsearch2('RENT', desc_str): return 'RENT'
        elif _bsearch2('ESI', desc_str): return 'ESI'
    
    return category

def categorize_desc_text(desc, category, cr=None, dr=None):
    # This remains as a entry point, but we could vectorize the calling side significantly
    return categorize_desc_text_row(desc, category, cr, dr)

def _any_bsearch2(keywords, text: str) -> bool:
    return any(_bsearch2(kw, text) for kw in keywords)

# ── Matching logic for categorize_return_type ───────────────────────────────────

def get_base_mask(df, idx, nearest_idx, current_date, day, amount):
    after_idx = df.index > idx
    not_nearest = df.index != nearest_idx
    if day >= 25:
        window_end = (current_date + MonthBegin(1)).replace(day=10)
        return after_idx & not_nearest & (df['_date_only'] >= current_date) & (df['_date_only'] <= window_end) & (df['DR'].abs().round(2) == amount)
    return after_idx & not_nearest & (df['_date_only'].dt.month == current_date.month) & (df['_date_only'].dt.year == current_date.year) & (df['DR'].abs().round(2) == amount)

def handle_exact_match(df, exact_mask, base_mask, rep_chq_no):
    exact_rows = df[exact_mask]
    if not exact_rows.empty and rep_chq_no:
        chq_mask = base_mask & (df['Cheque_No'].astype(str).str.strip() == rep_chq_no)
        return chq_mask if chq_mask.any() else None
    return exact_mask

def get_mask(df, idx, nearest_idx, current_date, amount, base_mask,
             rep_cat, rep_chq_no, rep_cat_clean, rep_desc, bank_code):
    _false = pd.Series(False, index=df.index)
    if str(rep_cat).strip().upper().startswith("TRANSFER TO"):
        exact_mask = base_mask & (df['Category'] == rep_cat)
        if exact_mask.any():
            res = handle_exact_match(df, exact_mask, base_mask, rep_chq_no)
            if res is not None: return res, False
        fuzzy_mask = base_mask & df['Category_clean'].apply(lambda x: fuzz.token_sort_ratio(x, rep_cat_clean) >= 75)
        if fuzzy_mask.any(): return fuzzy_mask, False
        non_amt_mask = (df.index > idx) & (df.index != nearest_idx) & (df['_date_only'].dt.month == current_date.month) & (df['_date_only'].dt.year == current_date.year) & (df['DR'].abs() > 0)
        desc_word_mask = non_amt_mask & df['Description'].apply(lambda d: word_in_description(rep_cat_clean, d))
        if not df[desc_word_mask].empty and round(df[desc_word_mask]['DR'].abs().round(2).sum(), 2) == amount: return desc_word_mask, True
        fuzzy_na = non_amt_mask & df['Category_clean'].apply(lambda x: fuzz.token_sort_ratio(x, rep_cat_clean) >= 70)
        if not df[fuzzy_na].empty and round(df[fuzzy_na]['DR'].abs().round(2).sum(), 2) == amount: return fuzzy_na, True
    else:
        desc_cat_mask = base_mask & df['Category_clean'].apply(lambda x: x in rep_desc)
        if desc_cat_mask.any(): return desc_cat_mask, False
        exact_mask = base_mask & (df['Category'] == rep_cat)
        if exact_mask.any():
            res = handle_exact_match(df, exact_mask, base_mask, rep_chq_no)
            if res is not None: return res, False
        if bank_code == 'HDFC':
            match = RE_HDFC_EMI.search(rep_desc)
            if match:
                emi_no = match.group(1)
                desc_emi_mask = base_mask & df['Description'].str.contains(rf"\b{emi_no}\b", case=False, na=False)
                if not df[desc_emi_mask].empty: return desc_emi_mask, False
                match2 = RE_HDFC_EMI_CHQ.search(rep_desc)
                if match2:
                    chq_no = match2.group(1)
                    chq_mask = (df.index > idx) & (df['_date_only'].dt.month == current_date.month) & (df['_date_only'].dt.year == current_date.year) & (df['Description'].str.contains(chq_no, case=False, na=False)) & (df['DR'].abs() > 0)
                    if not df[chq_mask].empty and round(df[chq_mask]['DR'].abs().round(2).sum(), 2) == amount: return chq_mask, True
    return _false, False

def categorize_return_type(df, bank_code=None):
    # Prepare standard columns
    df['CR'] = pd.to_numeric(df['CR'], errors='coerce')
    df['DR'] = pd.to_numeric(df['DR'], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Category_clean'] = df['Category'].apply(normalize_text)
    df['_date_only'] = df['Date'].dt.normalize()
    df['_used_rep'] = False

    # The O(N^2) complexity is in the loop below. 
    # For now, we keep the loop to preserve exact behavior but optimize the lookups.
    for idx, row in df.iterrows():
        row_no = int(row['Sl. No.']) if 'Sl. No.' in df.columns else idx
        has_cr, has_dr = not pd.isna(row['CR']), not pd.isna(row['DR'])
        desc_str = str(row['Description']).upper() if pd.notna(row['Description']) else ''
        cat_str = str(row['Category']).upper() if pd.notna(row['Category']) else ''
        has_inward, has_outward, has_charge, has_chq, has_rtn, has_ecs = _any_in(INWARD_KEYWORDS, desc_str), _any_in(OUTWARD_KEYWORDS, desc_str), _any_in(CHARGE_KEYWORDS, desc_str), _any_in(CHEQUE_KEYWORDS, desc_str), _any_in(RETURN_KEYWORDS, desc_str), _any_in(ECS_KEYWORDS, desc_str)

        if cat_str == 'BOUNCED O/W CHEQUE' and has_dr and not has_inward:
            m = RE_BOUNCE_CHQ.search(desc_str)
            if m:
                chq_no, date, amount = m.group(1).strip(), row['_date_only'], abs(round(row['DR'], 2))
                trans = df[(df['CR'].round(2) == amount) & (df['_date_only'] == date) & df['Description'].str.contains(chq_no, case=False, na=False) & (df.index != idx)]
                if len(trans) == 1:
                    t_idx = trans.index[0]
                    t_row_no = int(df.at[t_idx, 'Sl. No.']) if 'Sl. No.' in df.columns else t_idx
                    if max(row_no, t_row_no) - min(row_no, t_row_no) == 1 or row_no < t_row_no:
                        df.at[t_idx, 'Category'], df.at[idx, 'Category'] = 'O/W CHQ RTN', 'O/W CHQ RTN'
                    else: df.at[idx, 'Category'] = 'O/W CHQ RTN'
                else: df.at[idx, 'Category'] = 'O/W CHQ RTN'
            else: df.at[idx, 'Category'] = 'O/W CHQ RTN'

        elif cat_str in ('BOUNCED I/W CHEQUE', 'BOUNCED I/W ECS', 'BOUNCED I/W PAYMENT') and has_cr:
            curr_date, day, amount = row['_date_only'], row['_date_only'].day, round(row['CR'], 2)
            mask, is_multiple, nearest_row, nearest_idx = pd.Series(False, index=df.index), False, None, None
            final_text = 'CHQ' if cat_str == 'BOUNCED I/W CHEQUE' else 'ECS' if cat_str == 'BOUNCED I/W ECS' else next((k for k in ('RTGS', 'NEFT', 'IMPS') if k in desc_str), None)
            if final_text is None and cat_str == 'BOUNCED I/W PAYMENT':
                if _any_in(NEFT_KEYWORDS, desc_str): final_text = 'NEFT'
                elif _any_in(RTGS_KEYWORDS, desc_str): final_text = 'RTGS'

            trans = df[(abs(df['DR'].round(2)) == amount) & (df['_date_only'] == curr_date) & (~df.index.isin([idx])) & (~df['_used_rep']) & (df['Category_clean'] != cat_str)]
            if not trans.empty:
                trans_above = trans.loc[trans.index < idx]
                if not trans_above.empty:
                    trans_sorted = trans_above.sort_index(ascending=False)
                    cat_m = trans_sorted['Category_clean'].apply(lambda x: str(x).strip() in desc_str)
                    nearest_idx = trans_sorted[cat_m].index[0] if cat_m.any() else trans_sorted.index[0]
                    nearest_row = df.loc[nearest_idx]
                elif cat_str == 'BOUNCED I/W PAYMENT':
                    fwd = df[(df['_date_only'] == curr_date) & (df['DR'].abs().round(2) == amount) & (df.index > idx) & (~df['_used_rep']) & (df['Category_clean'] != cat_str)]
                    if not fwd.empty: nearest_row, nearest_idx = fwd.iloc[0], fwd.index[0]
                elif idx + 1 < len(df):
                    nxt = df.iloc[idx + 1]
                    if abs(round(nxt['DR'], 2)) == amount and nxt['_date_only'] == curr_date: nearest_row, nearest_idx = nxt, df.index[idx + 1]

                if nearest_row is not None:
                    b_mask = get_base_mask(df, idx, nearest_idx, curr_date, day, amount)
                    rep_cat, rep_cat_cl, rep_desc, rep_chq = nearest_row['Category'], normalize_text(nearest_row['Category']), str(nearest_row['Description']).upper(), str(nearest_row['Cheque_No']).strip() if pd.notna(nearest_row['Cheque_No']) and nearest_row['Cheque_No'] != '' else None
                    if rep_chq:
                        m_chq = b_mask & df['Cheque_No'].notna() & (df['Cheque_No'].astype(str).str.strip() == rep_chq)
                        if m_chq.any(): mask = m_chq
                        else: mask, is_multiple = get_mask(df, idx, nearest_idx, curr_date, amount, b_mask, rep_cat, rep_chq, rep_cat_cl, rep_desc, bank_code)
                    else: mask, is_multiple = get_mask(df, idx, nearest_idx, curr_date, amount, b_mask, rep_cat, rep_chq, rep_cat_cl, rep_desc, bank_code)

            is_rep = df[mask]
            if not is_rep.empty:
                rep_idxs = []
                if not is_multiple:
                    rep_idx, rep_date = is_rep.index[0], is_rep.iloc[0]['Date']
                    rep_idxs.append(rep_idx)
                    bounced = ((df['_date_only'] == rep_date) & (df['CR'].abs().round(2) == amount) & (df.index != rep_idx) & (df.index > idx) & (~df['_used_rep']) & (df['Category'].str.upper() == cat_str)).any()
                    rep_dates = [rep_date] if not bounced else []
                else:
                    bounced, rep_dates = False, []
                    for r_idx, r_row in is_rep.iterrows():
                        r_date, r_amt = r_row['Date'], abs(round(r_row['DR'], 2))
                        if ((df['_date_only'] == r_date) & (df['CR'].abs().round(2) == r_amt) & (df.index != r_idx) & (df.index > idx) & (~df['_used_rep']) & (df['Category'].str.upper() == cat_str)).any():
                            bounced = True; break
                        rep_dates.append(r_date); rep_idxs.append(r_idx); df.at[r_idx, '_used_rep'] = True
                
                if final_text == 'NEFT': df.at[idx, 'Category'] = 'I/W NEFT RTN'
                elif bounced and final_text:
                    if rep_chq: df.at[idx, 'Cheque_No'] = int(float(rep_chq))
                    df.at[idx, 'Category'] = f'I/W {final_text} RTN (NOT REP)'
                else:
                    is_l, rp_dts = str(rep_cat).strip().upper() == 'LOAN', sorted(set(rep_dates))
                    dt_txt = ", ".join(d.strftime("%d-%m-%Y") for d in rp_dts)
                    txt = 'I/W NEFT RTN' if final_text == 'NEFT' else f'I/W {final_text} RTN ON DATE' if len(rp_dts) == 1 and rp_dts[0] == row['Date'] else f'I/W {final_text} RTN ON {dt_txt}' if final_text else cat_str
                    if is_l and bank_code == 'HDFC':
                        m = RE_HDFC_EMI.search(rep_desc)
                        if m:
                            emi = str(m.group(1)); txt += f' (LOAN-{emi[-4:]})'
                            for i_ in rep_idxs: df.at[i_, 'Category'] = f'LOAN-{emi[-4:]}'
                    elif is_l: txt += ' (LOAN)'
                    if rep_chq: df.at[idx, 'Cheque_No'] = int(float(rep_chq))
                    df.at[idx, 'Category'] = txt
            else:
                if final_text == 'NEFT': df.at[idx, 'Category'] = 'I/W NEFT RTN'
                elif final_text: df.at[idx, 'Category'] = f'I/W {final_text} RTN (NOT REP)'

        elif cat_str == 'BOUNCED O/W CHEQUE CHARGES' and has_dr and not has_inward: df.at[idx, 'Category'] = 'O/W CHQ RTN CHGS'
        elif cat_str == 'BOUNCED I/W CHEQUE CHARGES' and has_dr and not has_outward: df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS'
        elif cat_str == 'BOUNCED I/W ECS CHARGES' and has_dr and not has_outward: df.at[idx, 'Category'] = 'I/W ECS RTN CHGS'
        elif cat_str == 'TRANSFER OUT' and has_dr:
            if has_outward and has_rtn and 'IMPS' not in desc_str: df.at[idx, 'Category'] = 'O/W CHQ RTN CHGS' if has_charge else 'O/W CHQ RTN'
        elif cat_str == 'TRANSFER IN' and has_cr:
            if has_inward and has_rtn and 'IMPS' not in desc_str:
                f_txt = next((k for k in ('RTGS', 'NEFT') if k in desc_str), None)
                if f_txt: df.at[idx, 'Category'] = f'I/W {f_txt} RTN' if not has_charge else f'I/W {f_txt} RTN CHGS'
                else: df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS' if has_charge else 'I/W CHQ RTN'
        elif cat_str == 'BANK CHARGES' and has_dr:
            if has_outward and has_rtn and 'IMPS' not in desc_str: df.at[idx, 'Category'] = f'O/W CHQ RTN CHGS' + ('-GST' if 'GST' in desc_str and '18%' in desc_str else '')
            elif has_inward and has_rtn and 'IMPS' not in desc_str: df.at[idx, 'Category'] = f'I/W CHQ RTN CHGS' + ('-GST' if 'GST' in desc_str and '18%' in desc_str else '')
            elif has_chq and has_rtn and float(abs(pd.to_numeric(row['DR'], errors='coerce'))) == 590.00: df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS'
            elif has_ecs: df.at[idx, 'Category'] = 'I/W ECS RTN CHGS' if has_rtn else 'I/W ECS MANDATE CHGS' if 'MANDATE' in desc_str else df.at[idx, 'Category']
        elif cat_str == 'OTHERS' and has_dr:
            if has_outward: df.at[idx, 'Category'] = 'O/W CHQ RTN CHGS' if has_charge else 'O/W CHQ RTN' if 'CLG' not in desc_str else df.at[idx, 'Category']
            elif has_inward: df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS' if has_charge else 'I/W CHQ RTN' if 'CLG' not in desc_str else df.at[idx, 'Category']

    df.drop(columns=['_date_only', 'Category_clean', '_used_rep'], inplace=True)
    return df

def categorize_type(df, type_value, acc_type):
    # --- Group-sum logic for specific categories ---
    target_cats = {'ENTERTAINMENT', 'CLOTHING', 'PERSONAL CARE', 'FOOD', 'ALCOHOL', 
                   'CASH BACK', 'LOGISTICS', 'MEDICAL', 'SUBSIDY', 'VEHICLE SERVICING'}
    
    # Ensure DR is numeric for calculation
    dr_vals = pd.to_numeric(df['DR'], errors='coerce').fillna(0).abs()
    
    # Check if we have any target categories before grouping to save time
    if df['Category'].str.upper().isin(target_cats).any():
        # Group by Category and sum DR values
        cat_sum_series = df.groupby('Category')[dr_vals.name].transform('sum')
        
        # Apply threshold: if sum < 50,000, change to COMPANY NAME
        mask = df['Category'].str.upper().isin(target_cats) & (cat_sum_series < 50000)
        df.loc[mask, 'Category'] = 'COMPANY NAME'

    cat_upper = df['Category'].str.upper()
    df['TYPE'] = df.get('TYPE', '')
    df.loc[cat_upper == 'CASH DEPOSIT', 'TYPE'] = type_value
    df.loc[cat_upper == 'CASH WITHDRAWAL', 'TYPE'] = 'CASH'
    df.loc[cat_upper == 'REVERSAL', 'TYPE'] = 'REVERSAL'
    df.loc[cat_upper == 'INSURANCE', 'TYPE'] = 'INSURANCE'
    expense_cats = {'BANK CHARGES', 'TAX', 'PENAL CHARGES', 'EPFO', 'ADVANCE SALARY PAID', 'EB BILL', 'RENT', 
                    'PF WITHDRAWAL', 'BELOW MIN BALANCE', 'SALARY PAID', 'UTILITIES', 'FUEL', 'TRAVEL', 'EXPENSE'}
    df.loc[cat_upper.isin(expense_cats), 'TYPE'] = 'EXPENSE'
    df.loc[df['Category'].isin(['ESIC', 'ESI']), 'TYPE'] = 'INSURANCE'
    df.loc[df['Category'].isin(['CREDIT CARD PAYMENT', 'ONLINE SHOPPING']), 'TYPE'] = 'PURCHASE'
    df.loc[df['Category'].isin(['CARD SETTLEMENT']), 'TYPE'] = 'SALES'
    df.loc[df['Category'].str.contains(RE_RETURNS_SUMMARY, na=False), 'TYPE'] = 'RETURN'
    df.loc[df['Category'].str.startswith('LOAN-', na=False), 'TYPE'] = 'BANK FIN'
    upi_mask = (df['Category'] == 'UPI')
    df.loc[upi_mask & df['CR'].notna() & (df['CR'] > 0), 'TYPE'] = 'SALES'
    df.loc[upi_mask & (df['CR'].isna() | (df['CR'] < 0)), 'TYPE'] = 'PURCHASE'
    co_mask = (df['Category'] == 'COMPANY NAME')
    df.loc[co_mask & df['CR'].notna() & (df['CR'] > 0), 'TYPE'] = 'SALES'
    df.loc[co_mask & (df['CR'].isna() | (df['CR'] < 0)), 'TYPE'] = 'PURCHASE'
    return helpers.update_account_types(df, acc_type)
