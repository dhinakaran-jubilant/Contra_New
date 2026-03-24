from pandas.tseries.offsets import MonthBegin
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from api import helpers
import pandas as pd
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

# Pre-compiled boundary pattern template
_BOUNDARY = r'(?:^|/|-|\s){kw}(?:$|/|-|\s)'
_BOUNDARY2 = r'(?:^|/|-|\s|_|:){kw}(?:$|/|-|\s|_|:)'


# ── Private helpers ────────────────────────────────────────────────────────────

def _bsearch(kw: str, text: str) -> bool:
    """True if *kw* appears at a word boundary in *text* (boundary pattern 1)."""
    return bool(re.search(_BOUNDARY.replace('{kw}', kw), text))


def _bsearch2(kw: str, text: str) -> bool:
    """True if *kw* appears at a word boundary in *text* (boundary pattern 2)."""
    return bool(re.search(_BOUNDARY2.replace('{kw}', kw), text))


def _any_bsearch(keywords, text: str, pattern_fn=None) -> bool:
    """True if any keyword in *keywords* matches with a boundary search."""
    fn = pattern_fn or _bsearch
    return any(fn(kw, text) for kw in keywords)


def _any_in(keywords, text: str) -> bool:
    """True if any keyword is a plain substring of *text*."""
    return any(kw in text for kw in keywords)


def _all_in(keywords, text: str) -> bool:
    """True if every keyword is a plain substring of *text*."""
    return all(kw in text for kw in keywords)


# ── Public helpers ─────────────────────────────────────────────────────────────

def word_in_description(word, description, threshold=0.85, min_len=3):
    word_clean = str(word).strip().lower()
    desc_clean = str(description).strip().lower()
    if not word_clean or not desc_clean:
        return False

    word_words = re.findall(r'\w+', word_clean)
    desc_words = re.findall(r'\w+', desc_clean)

    def single_word_match(w):
        if len(w) < min_len:
            return False
        if re.search(r'\b' + re.escape(w) + r'\b', desc_clean):
            return True
        return any(
            SequenceMatcher(None, w, d).ratio() >= threshold
            for d in desc_words if len(d) >= min_len
        )

    if len(word_words) > 1:
        return all(single_word_match(w) for w in word_words)
    return single_word_match(word_words[0])


def strings_similar(str1, str2, threshold=0.9):
    return SequenceMatcher(None, str1, str2).ratio() >= threshold


def is_fuzzy_match(a, b, threshold=75):
    if not a or not b:
        return False
    return fuzz.token_sort_ratio(a, b) >= threshold


def normalize_text(text):
    if pd.isna(text):
        return ''
    return str(text).upper().replace(',', '').replace('.', '').replace('TRANSFER TO', '').strip()


def categorize_desc_text(desc, category, cr=None, dr=None):
    if pd.isna(desc):
        return desc
    if pd.isna(category):
        return category

    desc_str     = str(desc).upper()
    cat_str      = str(category).upper()
    norm_desc_str = desc_str.replace(' ', '')

    has_cr = not pd.isna(cr)
    has_dr = not pd.isna(dr)

    has_neft = _any_in(NEFT_KEYWORDS, desc_str)
    has_rtgs = _any_in(RTGS_KEYWORDS, desc_str)
    has_upi  = bool(re.search(r'(?:^|/|-|\s)UPI(?:$|/|-|\s)', desc_str))

    if cat_str == 'REVERSAL' and not has_neft and not has_rtgs:
        return 'REVERSAL'

    elif (cat_str == 'CASH DEPOSIT' or 'CASH DEPOSIT' in desc_str) \
            and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi:
        if _any_bsearch(REVERSAL_KEYWORDS, desc_str) or cat_str == 'REVERSAL':
            return 'REVERSAL'
        elif _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str):
            if has_dr and cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'CASH WITHDRAWAL'):
                return 'CASH WITHDRAWAL'
            return 'REVERSAL' if has_cr else category
        elif has_cr and not has_neft:
            return 'CASH DEPOSIT'
        return category

    elif (re.search(r'(?:^|/|-|\s)(BNA|CAM|CDM)(?:$|/|-|\s)', desc_str) or 'BY CASH' in desc_str) \
            and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi:
        if _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str):
            if has_dr and cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'CASH WITHDRAWAL'):
                return 'CASH WITHDRAWAL'
            return 'REVERSAL' if has_cr else category
        elif _any_bsearch(REVERSAL_KEYWORDS, desc_str) or cat_str == 'REVERSAL':
            return 'REVERSAL'
        return 'CASH DEPOSIT' if has_cr else category

    elif re.search(r'(?:^|/|-|\s)ATM(?:$|/|-|\s)', desc_str) \
            and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi:
        if has_dr and cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'CASH WITHDRAWAL'):
            return 'CASH WITHDRAWAL'
        return category

    elif (cat_str == 'CASH WITHDRAWAL'
          or ((cat_str in ('LOAN', 'TRANSFER OUT', 'OTHERS', 'TRANSFER TO SELF')
               and ('ATM' in desc_str or _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str)))
              or _bsearch('ATW', desc_str)
              or 'ATM CSW' in desc_str
              or strings_similar('CASH WITHDRAWAL', cat_str.replace('TRANSFER TO', '').strip())
              or word_in_description('CASH WITHDRAWAL', desc_str)
              or (_any_in(CHEQUE_KEYWORDS, desc_str) and _any_bsearch(WITHDRAWAL_KEYWORDS, desc_str)))
          ) and cat_str != 'BANK CHARGES' \
          and 'TRANSFER' not in desc_str and 'TFR' not in desc_str \
          and 'TAX' not in desc_str and 'TAX' != cat_str \
          and not _any_in(CHARGE_KEYWORDS, desc_str) and not has_upi \
          and not has_neft and 'REMITTANCE' not in desc_str:
        if has_dr:
            return 'CASH WITHDRAWAL'
        return 'REVERSAL' if has_cr else category

    elif (re.search(r'(?:^|/|-|\s)CASH(?:$|/|-|\s)', cat_str)
          or (re.search(r'(?:^|/|-|\s)CASH(?:$|/|-|\s)', desc_str) and cat_str == 'TRANSFER TO SELF')
          or (('CHED' in desc_str or 'MDSE' in desc_str)
              and (re.search(r'(?:^|/|-|\s)CASH(?:$|/|-|\s)', desc_str) or 'CASH PAID' in desc_str)
              and 'SELF' in desc_str)) \
          and not has_upi and cat_str != 'BANK CHARGES':
        if has_cr:
            return 'CASH DEPOSIT'
        return 'CASH WITHDRAWAL' if has_dr else category

    elif cat_str == 'CASH WITHDRAWAL' and has_dr:
        return cat_str

    elif cat_str == 'CASH DEPOSIT' and has_cr:
        return cat_str

    elif cat_str == 'OTHERS' and _any_bsearch2(REVERSAL_KEYWORDS, desc_str) \
            and not _any_in(RETURN_KEYWORDS, desc_str):
        return 'REVERSAL' if has_cr else category

    elif cat_str == 'OTHERS' and has_dr:
        if (_any_in(CHARGE_KEYWORDS, desc_str)
                and not (_any_bsearch2(PENAL_KEYWORDS, desc_str)
                         or _any_in(RETURN_KEYWORDS, desc_str)
                         or _any_in(CHEQUE_KEYWORDS, desc_str)
                         or _any_bsearch2(ECS_KEYWORDS, desc_str)
                         or _any_in(('NACH', 'MAND', 'MANDATE'), desc_str)
                         or _any_in(('STOP', 'CHARGEBACK'), desc_str))) \
                or _any_in(('BOXRENT', 'SOUNDBOX', 'COMMISS', 'POS', 'REMIT'), norm_desc_str) \
                or (_any_in(('RECOVERY', 'RCVRY'), desc_str) and 'INTEREST' not in desc_str) \
                or any('SC' == w for w in desc_str.split(' ')):
            return 'BANK CHARGES'
        elif _any_in(('TAX', 'GST', 'TINCBDT', 'TDS', 'ITD'), desc_str) \
                and not (_any_in(CHEQUE_KEYWORDS, desc_str) or _any_in(RETURN_KEYWORDS, desc_str)):
            return 'BANK CHARGES' if 'NESL' in desc_str else 'TAX'
        elif _any_bsearch2(PENAL_KEYWORDS, desc_str):
            return 'PENAL CHARGES'
        elif _any_bsearch2(INTEREST_KEYWORDS, desc_str) and not _any_in(CHARGE_KEYWORDS, desc_str):
            return 'INTEREST'
        elif _any_in(EPFO_KEYWORDS, desc_str):
            return 'EPFO'
        elif 'TANGEDCO' in norm_desc_str or 'ELECTRICITY' in norm_desc_str:
            return 'EB BILL'
        return category

    elif cat_str == 'BANK CHARGES' and has_dr \
            and (not (_any_in(RETURN_KEYWORDS, desc_str)
                      or _any_in(CHEQUE_KEYWORDS, desc_str)
                      or _any_bsearch2(ECS_KEYWORDS, desc_str)
                      or _any_in(('NACH', 'MAND', 'MANDATE'), desc_str)
                      or _any_in(INWARD_KEYWORDS, desc_str)
                      or _any_in(OUTWARD_KEYWORDS, desc_str)
                      or _any_in(('STOP', 'MANDATE', 'DRAWDOWN', 'EMANCH', 'TAX', 'CSW'), desc_str)
                      or _all_in(FUNDS_INSUFFICIENT, desc_str)
                      or _all_in(EXCEEDS_ARRANGEMENT, desc_str))
                 or (_any_in(CHEQUE_KEYWORDS, desc_str)
                     and _any_in(('BOOK', 'COURIER'), desc_str)
                     and not _any_in(RETURN_KEYWORDS, desc_str))):
        return 'BANK CHARGES'

    elif cat_str == 'TRANSFER OUT' and has_dr:
        if 'ESIC' in desc_str:
            return 'ESIC'
        elif ('REMIT' in desc_str or 'RENT' in desc_str
              or _any_in(CHARGE_KEYWORDS, norm_desc_str)
              or any('SC' == w for w in desc_str.split(' '))) \
                and not (_any_in(RETURN_KEYWORDS, desc_str)
                         or _any_in(CHEQUE_KEYWORDS, desc_str)
                         or _any_bsearch2(ECS_KEYWORDS, desc_str)
                         or _any_in(('NACH', 'MAND', 'MANDATE'), desc_str)):
            return 'BANK CHARGES'
        elif _any_in(INTEREST_KEYWORDS, norm_desc_str):
            return 'INTEREST'
        elif _any_in(EPFO_KEYWORDS, desc_str):
            return 'EPFO'
        elif 'TANGEDCO' in norm_desc_str or 'ELECTRICITY' in norm_desc_str:
            return 'EB BILL'
        elif _any_in(SALARY_KEYWORDS, norm_desc_str):
            return 'SALARY'
        elif 'BONUS' in desc_str:
            return 'BONUS'
        return category

    elif cat_str == 'TRANSFER IN' and has_cr:
        if _any_in(SALARY_KEYWORDS, norm_desc_str):
            return 'SALARY'
        return 'BONUS' if 'BONUS' in desc_str else category

    elif cat_str == 'INTEREST CHARGES' and has_dr:
        return 'INTEREST CHARGES'

    elif _any_in(INTEREST_KEYWORDS, cat_str.replace('TRANSFER TO', '')) and has_dr:
        return 'INTEREST'

    elif cat_str == 'TAX' and not _any_in(RETURN_KEYWORDS, desc_str):
        if has_dr:
            return 'TAX'
        return 'REVERSAL' if has_cr else category

    elif ((_any_bsearch2(EPFO_KEYWORDS, desc_str) or 'EPFO' in desc_str)
          and cat_str != 'BANK CHARGES'
          or cat_str == 'PROVIDENT FUND CONTRIBUTION') and has_dr:
        return 'EPFO'

    elif cat_str == 'PROVIDENT FUND WITHDRAWAL' and has_cr:
        return 'PF WITHDRAWAL'

    elif cat_str == 'HOUSE RENT':
        return 'RENT'

    elif cat_str == 'INTEREST' and 'INT TRF' not in desc_str:
        return 'INTEREST'

    elif cat_str == 'CARD SETTLEMENT':
        return 'CARD SETTLEMENT'

    elif cat_str == 'CREDIT CARD PAYMENT':
        return 'CREDIT CARD PAYMENT'

    elif cat_str == 'BELOW MIN BALANCE':
        return 'BELOW MIN BALANCE'

    elif cat_str == 'PENAL CHARGES' and has_dr:
        if _any_in(('TAX', 'GST', 'TINCBDT', 'TDS', 'ITD'), desc_str) and not has_neft:
            return 'TAX'
        return 'PENAL CHARGES'

    elif 'TRANSFER FROM' in cat_str or 'TRANSFER TO' in cat_str:
        if 'UPI' in desc_str and 'SELF' not in cat_str:
            return 'UPI'
        elif 'TANGEDCO' in norm_desc_str or 'ELECTRICITY' in norm_desc_str:
            return 'EB BILL'
        elif _any_in(('TAX', 'GST', 'TINCBDT', 'TDS', 'ITD'), desc_str):
            if not has_neft and has_dr:
                return 'TAX'
            return category
        elif _bsearch2('ESIC', desc_str):
            return 'ESIC'
        elif _any_bsearch2(EPFO_KEYWORDS, desc_str):
            return 'EPFO'
        elif ('P CHARGE' in desc_str or 'PNLCHRG' in norm_desc_str
              or _any_bsearch2(PENAL_KEYWORDS, desc_str)) and has_dr:
            return 'PENAL CHARGES'
        elif _bsearch2('RENT', desc_str):
            return 'RENT'
        elif _bsearch2('ESI', desc_str):
            return 'ESI'
        return category

    return category


# ── Helper aliases used above that reference functions defined later ───────────

def _any_bsearch2(keywords, text: str) -> bool:
    return any(_bsearch2(kw, text) for kw in keywords)


def _bsearch2(kw: str, text: str) -> bool:  # noqa: F811
    return bool(re.search(_BOUNDARY2.replace('{kw}', kw), text))


# ── Other public functions ─────────────────────────────────────────────────────

def get_base_mask(df, idx, nearest_idx, current_date, day, amount):
    if day >= 25:
        window_end = (current_date + MonthBegin(1)).replace(day=10)
        return (
            (df.index > idx) & (df.index != nearest_idx)
            & (df['_date_only'] >= current_date) & (df['_date_only'] <= window_end)
            & (df['DR'].abs().round(2) == amount)
        )
    return (
        (df.index > idx) & (df.index != nearest_idx)
        & (df['_date_only'].dt.month == current_date.month)
        & (df['_date_only'].dt.year == current_date.year)
        & (df['DR'].abs().round(2) == amount)
    )


def handle_exact_match(df, exact_mask, base_mask, rep_chq_no):
    exact_rows   = df[exact_mask]
    rows_with_chq = exact_rows[exact_rows['Cheque_No'].notna()]
    if not rows_with_chq.empty and rep_chq_no:
        chq_mask = base_mask & (df['Cheque_No'].astype(str).str.strip() == rep_chq_no)
        return chq_mask if chq_mask.any() else None
    return exact_mask


def get_mask(df, idx, nearest_idx, current_date, amount, base_mask,
             rep_cat, rep_chq_no, rep_cat_clean, rep_desc, bank_code):
    _false = pd.Series(False, index=df.index)

    if str(rep_cat).strip().upper().startswith("TRANSFER TO"):
        exact_mask = base_mask & (df['Category'] == rep_cat)
        if exact_mask.any():
            result = handle_exact_match(df, exact_mask, base_mask, rep_chq_no)
            if result is not None:
                return result, False

        fuzzy_mask = base_mask & df['Category_clean'].apply(
            lambda x: fuzz.token_sort_ratio(x, rep_cat_clean) >= 75
        )
        if fuzzy_mask.any():
            return fuzzy_mask, False

        non_amount_mask = (
            (df.index > idx) & (df.index != nearest_idx)
            & (df['_date_only'].dt.month == current_date.month)
            & (df['_date_only'].dt.year == current_date.year)
            & (df['DR'].abs() > 0)
        )
        fuzzy_na = non_amount_mask & df['Category_clean'].apply(
            lambda x: fuzz.token_sort_ratio(x, rep_cat_clean) >= 70
        )
        if not df[fuzzy_na].empty:
            if round(df[fuzzy_na]['DR'].abs().round(2).sum(), 2) == amount:
                return non_amount_mask, True

    else:
        desc_cat_mask = base_mask & df['Category_clean'].apply(lambda x: x in rep_desc)
        if desc_cat_mask.any():
            return desc_cat_mask, False

        exact_mask = base_mask & (df['Category'] == rep_cat)
        if exact_mask.any():
            result = handle_exact_match(df, exact_mask, base_mask, rep_chq_no)
            if result is not None:
                return result, False

        if bank_code == 'HDFC':
            pattern = r"\bEMI\s+(\d+)\b(?=.*\bCHQ\b)"
            match   = re.search(pattern, rep_desc, re.IGNORECASE)
            if match:
                emi_no       = match.group(1)
                desc_emi_mask = base_mask & df['Description'].str.contains(rf"\b{emi_no}\b", case=False, na=False)
                if not df[desc_emi_mask].empty:
                    return desc_emi_mask, False

                pattern2 = r"(?i)^EMI\s+.*CHQ\s+([A-Z0-9]+)"
                match2   = re.search(pattern2, rep_desc, re.IGNORECASE)
                if match2:
                    chq_no   = match2.group(1)
                    chq_mask = (
                        (df.index > idx)
                        & (df['_date_only'].dt.month == current_date.month)
                        & (df['_date_only'].dt.year == current_date.year)
                        & (df['Description'].str.contains(chq_no, case=False, na=False))
                        & (df['DR'].abs() > 0)
                    )
                    chq_rows = df[chq_mask]
                    if not chq_rows.empty and round(chq_rows['DR'].abs().round(2).sum(), 2) == amount:
                        return chq_mask, True

    return _false, False


def categorize_return_type(df, bank_code=None):
    df['CR']            = pd.to_numeric(df['CR'], errors='coerce')
    df['DR']            = pd.to_numeric(df['DR'], errors='coerce')
    df['Date']          = pd.to_datetime(df['Date'], errors='coerce')
    df['Category_clean'] = df['Category'].apply(normalize_text)
    df['_date_only']    = df['Date'].dt.normalize()
    df['_used_rep']     = False

    for idx, row in df.iterrows():
        row_no  = int(row['Sl. No.']) if 'Sl. No.' in df.columns else idx
        has_cr  = not pd.isna(row['CR'])
        has_dr  = not pd.isna(row['DR'])

        desc_str = str(row['Description']).upper() if pd.notna(row['Description']) else ''
        cat_str  = str(row['Category']).upper()    if pd.notna(row['Category'])    else ''

        has_inward  = _any_in(INWARD_KEYWORDS,  desc_str)
        has_outward = _any_in(OUTWARD_KEYWORDS, desc_str)
        has_charge  = _any_in(CHARGE_KEYWORDS,  desc_str)
        has_chq     = _any_in(CHEQUE_KEYWORDS,  desc_str)
        has_rtn     = _any_in(RETURN_KEYWORDS,  desc_str)
        has_ecs     = _any_in(ECS_KEYWORDS,     desc_str)

        # ── BOUNCED O/W CHEQUE ────────────────────────────────────────────
        if cat_str == 'BOUNCED O/W CHEQUE' and has_dr and not has_inward:
            match = re.search(
                r"[()\\s]*(?:BOUNCE|REJECT|RETURNED|RET|ISSUED|RTN|RTRN)[()\\s:/\\-]*(\d+)",
                desc_str, re.IGNORECASE
            )
            if match:
                chq_no = match.group(1).strip()
                date   = row['_date_only']
                amount = abs(round(row['DR'], 2))
                trans  = df[
                    (df['CR'].round(2) == amount) & (df['_date_only'] == date)
                    & df['Description'].str.contains(chq_no, case=False, na=False)
                    & (df.index != idx)
                ]
                if len(trans) == 1:
                    trans_idx    = trans.index[0]
                    trans_row_no = int(trans.iloc[0]['Sl. No.'])
                    row_diff     = max(row_no, trans_row_no) - min(row_no, trans_row_no)
                    if row_diff == 1 or row_no < trans_row_no:
                        df.at[trans_idx, 'Category'] = 'I/W CHQ RTN'
                    else:
                        df.at[idx, 'Category'] = 'O/W CHQ RTN'
                else:
                    df.at[idx, 'Category'] = 'O/W CHQ RTN'
            else:
                df.at[idx, 'Category'] = 'O/W CHQ RTN'

        # ── BOUNCED I/W CHEQUE / ECS / PAYMENT ───────────────────────────
        elif cat_str in ('BOUNCED I/W CHEQUE', 'BOUNCED I/W ECS', 'BOUNCED I/W PAYMENT') and has_cr:
            current_date = row['_date_only']
            day          = current_date.day
            amount       = round(row['CR'], 2)
            is_rep       = pd.DataFrame()
            mask         = pd.Series(False, index=df.index)
            is_multiple  = False
            nearest_row  = None
            nearest_idx  = None

            # Determine final_text label
            if cat_str == 'BOUNCED I/W CHEQUE':
                final_text = 'CHQ'
            elif cat_str == 'BOUNCED I/W ECS':
                final_text = 'ECS'
            else:  # BOUNCED I/W PAYMENT
                final_text = next((k for k in ('RTGS', 'NEFT', 'IMPS') if k in desc_str), None)
                if final_text is None:
                    if _any_in(NEFT_KEYWORDS, desc_str):
                        final_text = 'NEFT'
                    elif _any_in(RTGS_KEYWORDS, desc_str):
                        final_text = 'RTGS'

            trans = df[
                (abs(df['DR'].round(2)) == amount) & (df['_date_only'] == current_date)
                & (~df.index.isin([idx])) & (~df['_used_rep'])
                & (df['Category_clean'] != cat_str)
            ]

            if len(trans) > 0:
                trans_above = trans.loc[trans.index < idx]
                if not trans_above.empty:
                    trans_sorted = trans_above.sort_index(ascending=False)
                    cat_match    = trans_sorted['Category_clean'].apply(lambda x: str(x).strip() in desc_str)
                    if cat_match.any():
                        nearest_row = trans_sorted[cat_match].iloc[0]
                        nearest_idx = trans_sorted[cat_match].index[0]
                    else:
                        nearest_row = trans_sorted.iloc[0]
                        nearest_idx = trans_sorted.index[0]
                else:
                    if cat_str == 'BOUNCED I/W PAYMENT':
                        fwd_mask = (
                            (df['_date_only'] == current_date) & (df['DR'].abs().round(2) == amount)
                            & (df.index > idx) & (~df['_used_rep']) & (df['Category_clean'] != cat_str)
                        )
                        fwd_matches = df.loc[fwd_mask]
                        if not fwd_matches.empty:
                            nearest_row = fwd_matches.iloc[0]
                            nearest_idx = fwd_matches.index[0]
                    else:
                        if idx + 1 < len(df):
                            next_row_data = df.iloc[idx + 1]
                            if abs(round(next_row_data['DR'], 2)) == amount and next_row_data['_date_only'] == current_date:
                                nearest_row = next_row_data
                                nearest_idx = df.index[idx + 1]

                if nearest_row is not None:
                    base_mask    = get_base_mask(df, idx, nearest_idx, current_date, day, amount)
                    rep_cat      = nearest_row['Category']
                    rep_cat_clean = normalize_text(rep_cat)
                    rep_desc     = str(nearest_row['Description']).upper()
                    rep_chq_no   = (
                        str(nearest_row['Cheque_No']).strip()
                        if pd.notna(nearest_row['Cheque_No']) and nearest_row['Cheque_No'] != ''
                        else None
                    )

                    if rep_chq_no:
                        mask_with_chq = base_mask & df['Cheque_No'].notna() & (
                            df['Cheque_No'].astype(str).str.strip() == rep_chq_no
                        )
                        if mask_with_chq.any():
                            mask = mask_with_chq
                        else:
                            mask, is_multiple = get_mask(df, idx, nearest_idx, current_date, amount,
                                                         base_mask, rep_cat, rep_chq_no, rep_cat_clean,
                                                         rep_desc, bank_code)
                    else:
                        mask, is_multiple = get_mask(df, idx, nearest_idx, current_date, amount,
                                                     base_mask, rep_cat, rep_chq_no, rep_cat_clean,
                                                     rep_desc, bank_code)

                    if mask is None:
                        mask = pd.Series(False, index=df.index)

            is_rep = df[mask]

            if not is_rep.empty:
                rep_idxs = []

                if not is_multiple:
                    rep_row  = is_rep.iloc[0]
                    rep_idx  = rep_row.name
                    rep_date = rep_row['Date']
                    rep_idxs.append(rep_idx)

                    # Build same-day-bounce mask then apply category filter once
                    same_day_bounce_mask = (
                        (df['_date_only'] == rep_date)
                        & (df['CR'].abs().round(2) == amount)
                        & (df.index != rep_idx) & (df.index > idx)
                        & (~df['_used_rep'])
                        & (df['Category'].str.upper() == cat_str)
                    )
                    bounced = same_day_bounce_mask.any()
                    if not bounced:
                        rep_dates = [rep_date]
                else:
                    bounced   = False
                    rep_dates = []
                    for rep_idx, rep_row in is_rep.iterrows():
                        rep_date   = rep_row['Date']
                        rep_amount = abs(round(rep_row['DR'], 2))
                        same_day_bounce_mask = (
                            (df['_date_only'] == rep_date)
                            & (df['CR'].abs().round(2) == rep_amount)
                            & (df.index != rep_idx) & (df.index > idx)
                            & (~df['_used_rep'])
                            & (df['Category'].str.upper() == cat_str)
                        )
                        if same_day_bounce_mask.any():
                            bounced = True
                            break
                        rep_dates.append(rep_date)
                        rep_idxs.append(rep_idx)
                        df.at[rep_idx, '_used_rep'] = True

                if bounced and final_text is not None:
                    if rep_chq_no:
                        df.at[idx, 'Cheque_No'] = int(float(rep_chq_no))
                    df.at[idx, 'Category'] = f'I/W {final_text} RTN (NOT REP)'
                else:
                    is_loan    = str(rep_cat).strip().upper() == 'LOAN'
                    rep_dates  = sorted(set(rep_dates))
                    date_text  = ", ".join(d.strftime("%d-%m-%Y") for d in rep_dates)
                    if final_text is not None:
                        text = (f'I/W {final_text} RTN ON DATE'
                                if len(rep_dates) == 1 and rep_dates[0] == row['Date']
                                else f'I/W {final_text} RTN ON {date_text}')

                    if is_loan:
                        if bank_code == 'HDFC':
                            pattern = r"\bEMI\s+(\d+)\b(?=.*\bCHQ\b)"
                            m = re.search(pattern, rep_desc, re.IGNORECASE)
                            if m:
                                emi_no = str(m.group(1))
                                text  += f' (LOAN-{emi_no[-4:]})'
                                for id_ in rep_idxs:
                                    df.at[id_, 'Category'] = f'LOAN-{emi_no[-4:]}'
                        else:
                            text += ' (LOAN)'

                    if rep_chq_no:
                        df.at[idx, 'Cheque_No'] = int(float(rep_chq_no))
                    df.at[idx, 'Category'] = text
            else:
                if final_text is not None:
                    df.at[idx, 'Category'] = f'I/W {final_text} RTN (NOT REP)'

        # ── Charge/simple bounce categories ──────────────────────────────
        elif cat_str == 'BOUNCED O/W CHEQUE CHARGES' and has_dr and not has_inward:
            df.at[idx, 'Category'] = 'O/W CHQ RTN CHGS'
        elif cat_str == 'BOUNCED I/W CHEQUE CHARGES' and has_dr and not has_outward:
            df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS'
        elif cat_str == 'BOUNCED I/W ECS CHARGES' and has_dr and not has_outward:
            df.at[idx, 'Category'] = 'I/W ECS RTN CHGS'

        elif cat_str == 'TRANSFER OUT' and has_dr:
            if has_outward and 'IMPS' not in desc_str:
                df.at[idx, 'Category'] = 'O/W CHQ RTN CHGS' if has_charge else 'O/W CHQ RTN'

        elif cat_str == 'TRANSFER IN' and has_cr:
            if has_inward and 'IMPS' not in desc_str:
                df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS' if has_charge else 'I/W CHQ RTN'

        elif cat_str == 'BANK CHARGES' and has_dr:
            if has_outward and has_rtn and 'IMPS' not in desc_str:
                suffix = '-GST' if ('GST' in desc_str and '18%' in desc_str) else ''
                df.at[idx, 'Category'] = f'O/W CHQ RTN CHGS{suffix}'
            elif has_inward and has_rtn and 'IMPS' not in desc_str:
                suffix = '-GST' if ('GST' in desc_str and '18%' in desc_str) else ''
                df.at[idx, 'Category'] = f'I/W CHQ RTN CHGS{suffix}'
            elif has_chq and has_rtn:
                if float(abs(pd.to_numeric(row['DR'], errors='coerce'))) == 590.00:
                    df.at[idx, 'Category'] = 'I/W CHQ RTN CHGS'
            elif has_ecs:
                df.at[idx, 'Category'] = ('I/W ECS RTN CHGS' if has_rtn else
                                           'I/W ECS MANDATE CHGS' if 'MANDATE' in desc_str else
                                           df.at[idx, 'Category'])

        elif cat_str == 'OTHERS' and has_dr:
            if has_outward:
                df.at[idx, 'Category'] = ('O/W CHQ RTN CHGS' if has_charge else
                                           'O/W CHQ RTN' if 'CLG' not in desc_str else
                                           df.at[idx, 'Category'])
            elif has_inward:
                df.at[idx, 'Category'] = ('I/W CHQ RTN CHGS' if has_charge else
                                           'I/W CHQ RTN' if 'CLG' not in desc_str else
                                           df.at[idx, 'Category'])

    df.drop(columns=['_date_only', 'Category_clean', '_used_rep'], inplace=True)
    return df


def categorize_type(df, type_value, acc_type):
    df.loc[df['Category'].str.upper() == 'CASH DEPOSIT',    'TYPE'] = type_value
    df.loc[df['Category'].str.upper() == 'CASH WITHDRAWAL', 'TYPE'] = 'CASH'
    df.loc[df['Category'].str.upper() == 'REVERSAL',        'TYPE'] = 'REVERSAL'
    df.loc[df['Category'].isin([
        'BANK CHARGES', 'TAX', 'PENAL CHARGES', 'EPFO',
        'EB BILL', 'RENT', 'PF WITHDRAWAL', 'BELOW MIN BALANCE',
    ]), 'TYPE'] = 'EXPENSE'
    df.loc[df['Category'].isin(['ESIC', 'ESI']),             'TYPE'] = 'INSURANCE'
    df.loc[df['Category'].isin(['CREDIT CARD PAYMENT']),     'TYPE'] = 'PURCHASE'
    df.loc[df['Category'].isin(['CARD SETTLEMENT']),         'TYPE'] = 'SALES'
    df.loc[df['Category'].str.contains(
        'O/W CHQ RTN|I/W CHQ RTN|I/W ECS RTN|I/W ECS MANDATE|'
        'I/W RTGS RTN|I/W NEFT RTN|I/W IMPS RTN', na=False
    ), 'TYPE'] = 'RETURN'
    df.loc[df['Category'].str.startswith('LOAN-', na=False), 'TYPE'] = 'BANK FIN'

    upi_mask = df['Category'] == 'UPI'
    df.loc[upi_mask & df['CR'].notna() & (df['CR'] > 0),           'TYPE'] = 'SALES'
    df.loc[upi_mask & (df['CR'].isna() | (df['CR'] < 0)),          'TYPE'] = 'PURCHASE'

    return helpers.update_account_types(df, acc_type)
