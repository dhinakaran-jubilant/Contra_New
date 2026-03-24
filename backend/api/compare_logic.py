from .spacy_normalize import is_same_name, description_contains_category
from datetime import timedelta
from . import config, helpers
import re

# ── Pre-compiled patterns ─────────────────────────────────────────────────────
_ETXN_RE = re.compile(r"(?i)^eTXN\/(?:By|To):(\d+)(?:\/Trf)?")
_WORD_RE  = re.compile(r'\b\w+\b')

_TRANSFER_CATS = frozenset({"TRANSFER IN", "TRANSFER OUT"})


# ── Private helpers ────────────────────────────────────────────────────────────

def _extract_acc_suffixes(numbers_col) -> list[str]:
    """Return the last-4-digit suffixes of numeric strings in *numbers_col*."""
    if not (isinstance(numbers_col, list) and numbers_col):
        return []
    return [
        num[-4:]
        for num in numbers_col
        if isinstance(num, str) and len(num) >= 4 and num[-4:].isdigit()
    ]


def _is_valid_imps(val) -> bool:
    """True if *val* is a non-empty string with at least 5 characters."""
    return bool(val) and isinstance(val, str) and len(val) >= 5


def _tail_matches_desc(tail: str, desc: str) -> bool:
    """True if any digit-containing word in *desc* ends with *tail*."""
    for word in _WORD_RE.findall(desc):
        if any(c.isdigit() for c in word) and word.endswith(tail):
            return True
    return False


# ── Public functions ───────────────────────────────────────────────────────────

def find_imps_match(row1, df2, lookup_df2, amount_col1, amount_col2, df2_key, file_used_indices):
    row1_imps = row1.get("IMPS")
    desc1     = str(row1.get("Description", ""))

    try:
        amt1 = float(row1[amount_col1])
    except (TypeError, ValueError):
        return None

    date_key = row1["norm_date"]

    # Build candidate set from ±1-day window
    candidate_idx2_list = list(dict.fromkeys(
        idx
        for offset in (-1, 0, 1)
        for idx in lookup_df2.get(date_key + timedelta(days=offset), [])
    ))
    if not candidate_idx2_list:
        return None

    matches = []
    for idx2 in candidate_idx2_list:
        if idx2 in file_used_indices[df2_key]:
            continue

        row2     = df2.loc[idx2]
        row2_imps = row2.get("IMPS")
        desc2    = str(row2.get("Description", ""))

        has_imps1 = _is_valid_imps(row1_imps)
        has_imps2 = _is_valid_imps(row2_imps)

        if not (has_imps1 or has_imps2):
            continue

        imps_ok = False

        # CHECK 1: Direct last-5 match
        if has_imps1 and has_imps2:
            imps_ok = (row1_imps[-5:] == row2_imps[-5:])

        # CHECK 2: row1 tail found in desc2 word
        if not imps_ok and has_imps1:
            imps_ok = _tail_matches_desc(row1_imps[-5:], desc2)

        # CHECK 3: row2 tail found in desc1 word
        if not imps_ok and has_imps2:
            imps_ok = _tail_matches_desc(row2_imps[-5:], desc1)

        if not imps_ok:
            continue

        try:
            amt2 = float(row2[amount_col2])
        except (TypeError, ValueError):
            continue

        if abs(amt1 - amt2) <= config.AMOUNT_TOLERANCE:
            matches.append(idx2)

    return matches[0] if len(matches) == 1 else None


def find_self_match(row1, df2, lookup_df2, amount_col1, amount_col2,
                    this_acc_name, other_acc_name, df1_key, df2_key,
                    file_used_indices, is_working=False):
    try:
        amt1 = float(row1[amount_col1])
    except (TypeError, ValueError):
        return None

    date_key       = row1["norm_date"]
    acc_candidates = lookup_df2.get(date_key, [])
    if not acc_candidates:
        return None

    cat1_raw  = str(row1.get("Category", "")).lower().replace('transfer to', '').replace('transfer from', '').strip()
    desc1_raw = str(row1.get("Description", "")).strip()

    df1_acc_suffix = helpers.extract_acc_suffix_from_key(df1_key)
    df2_acc_suffix = helpers.extract_acc_suffix_from_key(df2_key)

    # Veto row1 if it references an account that isn't df2
    row1_suffixes = _extract_acc_suffixes(row1.get("NUMBERS", []))
    if row1_suffixes and not any(s == df2_acc_suffix for s in row1_suffixes):
        return None

    matches = []
    for idx2 in acc_candidates:
        row2 = df2.loc[idx2]
        try:
            amt2 = float(row2[amount_col2])
        except (TypeError, ValueError):
            continue
        if amt2 != amt1 or idx2 in file_used_indices[df2_key]:
            continue

        cat2_raw  = str(row2.get("Category", "")).lower().replace('transfer to', '').replace('transfer from', '').strip()
        desc2_raw = str(row2.get("Description", "")).strip()

        # Veto row2 if it references an account that isn't df1
        row2_suffixes = _extract_acc_suffixes(row2.get("NUMBERS", []))
        if row2_suffixes and not any(s == df1_acc_suffix for s in row2_suffixes):
            continue

        is_match = False

        if cat1_raw.upper() == 'SELF':
            is_match = (
                is_same_name(this_acc_name, cat2_raw)['same']
                or description_contains_category(this_acc_name, desc2_raw)['contains']
            )

        elif cat2_raw.upper() == 'SELF':
            is_match = (
                is_same_name(other_acc_name, cat1_raw)['same']
                or description_contains_category(other_acc_name, desc1_raw)['contains']
            )

        elif is_same_name(other_acc_name, cat1_raw)['same']:
            is_match = (
                is_same_name(this_acc_name, cat2_raw)['same']
                or description_contains_category(this_acc_name, desc2_raw)['contains']
            )

        if is_match:
            matches.append(idx2)

    if is_working:
        return matches[0] if len(matches) == 1 else None
    return matches


def find_etxn_match(row1, df2, lookup_df2, amount_col1, amount_col2, df2_key, file_used_indices):
    """Find eTXN matches based on description pattern, amount, and date."""
    try:
        amt1 = float(row1[amount_col1])
    except (TypeError, ValueError):
        return None

    date_key   = row1["norm_date"]
    candidates = lookup_df2.get(date_key, [])
    if not candidates:
        return None

    desc1 = str(row1.get("Description", "")).strip()
    cat1  = str(row1.get("Category",    "")).strip().upper()

    match1 = _ETXN_RE.search(desc1)
    if not (match1 and cat1 in _TRANSFER_CATS):
        return None

    for idx2 in candidates:
        if idx2 in file_used_indices[df2_key]:
            continue

        row2 = df2.loc[idx2]
        try:
            amt2 = float(row2[amount_col2])
        except (TypeError, ValueError):
            continue

        if amt2 != amt1:
            continue

        desc2 = str(row2.get("Description", "")).strip()
        cat2  = str(row2.get("Category",    "")).strip().upper()

        if cat2 not in _TRANSFER_CATS:
            continue

        match2 = _ETXN_RE.search(desc2)
        if not match2:
            continue

        # Opposite transfer direction is always sufficient; same ID is ideal
        if (cat1 == "TRANSFER IN") != (cat2 == "TRANSFER IN"):  # opposite directions
            if match1.group(1) == match2.group(1) or True:
                return idx2

    return None


def find_acc_num_match(row1, df2, lookup_df2, amount_col1, amount_col2,
                       df1_key, df2_key, file_used_indices):
    date_key       = row1["norm_date"]
    acc_candidates = lookup_df2.get(date_key, [])
    if not acc_candidates:
        return None

    try:
        amt1 = float(row1[amount_col1])
    except (TypeError, ValueError):
        return None

    # Require exactly one amount match to avoid ambiguity
    amount_matches = []
    for idx2 in acc_candidates:
        row2 = df2.loc[idx2]
        try:
            amt2 = float(row2[amount_col2])
        except (TypeError, ValueError):
            continue
        if amt2 == amt1 and idx2 not in file_used_indices[df2_key]:
            amount_matches.append((idx2, row2))

    if len(amount_matches) != 1:
        return None

    idx2, row2 = amount_matches[0]

    df1_acc_suffix = helpers.extract_acc_suffix_from_key(df1_key)
    df2_acc_suffix = helpers.extract_acc_suffix_from_key(df2_key)

    row1_suffixes = _extract_acc_suffixes(row1.get("NUMBERS", []))
    row2_suffixes = _extract_acc_suffixes(row2.get("NUMBERS", []))

    if row1_suffixes and df2_acc_suffix and any(s == df2_acc_suffix for s in row1_suffixes):
        return idx2

    if row2_suffixes and df1_acc_suffix and any(s == df1_acc_suffix for s in row2_suffixes):
        return idx2

    return None