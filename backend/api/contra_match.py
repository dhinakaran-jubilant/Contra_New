from . import helpers
# from .unmatch import find_unmatch
from .regex_pattern import extract_imps
from .inb_sis import infer_transfer_type
from .categorize_full import categorize_type
from .compare_logic import find_imps_match, find_self_match, find_etxn_match, find_acc_num_match
import pandas as pd

# ── Constants ───────────────────────────────────────────────────────────────
_THRESHOLD    = 10_00_000
_TEMP_COLS    = ("norm_date", "CR_val", "DR_val", "IMPS", "NUMBERS")
_MATCH_TYPES  = {"INB TRF", "SIS CON", "PROP ACC", "PROP"}

# ── Module-level pure helpers ────────────────────────────────────────────────

def _matched_category(key: str) -> str:
    """Strip the leading 'XNS-' segment from a sheet key for display."""
    parts = key.split("-")
    if "XNS" in parts:
        parts.remove("XNS")
    return "-".join(parts)


def _preprocess_df(df: pd.DataFrame, bank_name: str) -> None:
    """Add derived lookup columns to *df* in-place (idempotent)."""
    if "norm_date" not in df.columns:
        df["norm_date"] = df["Date"].apply(helpers.normalize_date)

    if "CR_val" not in df.columns:
        df["CR_val"] = pd.to_numeric(df["CR"], errors="coerce").fillna(0.0).abs()

    if "DR_val" not in df.columns:
        df["DR_val"] = pd.to_numeric(df["DR"], errors="coerce").fillna(0.0).abs()

    if "IMPS" not in df.columns:
        df["IMPS"] = df["Description"].astype(str).apply(
            lambda d: extract_imps(d, bank_name)
        )

    if "NUMBERS" not in df.columns:
        df["NUMBERS"] = df["Description"].astype(str).apply(helpers.get_numbers)

    # Keep IMPS and NUMBERS adjacent
    if "IMPS" in df.columns and "NUMBERS" in df.columns:
        imps_pos     = df.columns.get_loc("IMPS")
        nums_series  = df.pop("NUMBERS")
        df.insert(imps_pos + 1, "NUMBERS", nums_series)


def _build_lookup_by_date(df: pd.DataFrame, value_col: str) -> dict:
    """Return {norm_date: [index, …]} for rows where value_col > 0."""
    sub    = df[df[value_col] > 0]
    lookup: dict = {}
    for idx, key in zip(sub.index, sub["norm_date"]):
        lookup.setdefault(key, []).append(idx)
    return lookup


def _drop_temp_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Remove all temporary lookup columns from df."""
    return df.drop(columns=[c for c in _TEMP_COLS if c in df.columns])


# ────────────────────────────────────────────────────────────────────────────

def compare_files(bank_data_storage: dict, acc_name_storage: dict, cash_deposit_sum: float = 0):
    """
    Compare all pairs of files in *bank_data_storage* and annotate
    matching rows with their transfer TYPE and counterpart Category.
    Returns the mutated bank_data_storage.
    """
    all_files = list(bank_data_storage.keys())
    if len(all_files) < 2:
        print(f"Need at least 2 files, got: {all_files}")
        return bank_data_storage

    print(f"Files to process: {all_files}")

    total_matches  = 0
    inb_trf_count  = 0
    file_used_indices = {k: set() for k in all_files}

    # ── Inner helpers that need closure access ───────────────────────────────

    def _choose_candidate(row1, df2, lookup_df2, amount_col1, amount_col2,
                          name1, name2, df1_key, df2_key, logic):
        """
        Dispatch to the correct match function for *logic* and return
        a matching df2 index (or None).  For 'self' mode the raw result
        (possibly a list) is returned unchanged.
        """
        finder_map = {
            'imps':    lambda: find_imps_match(row1, df2, lookup_df2, amount_col1, amount_col2, df2_key, file_used_indices),
            'etxn':    lambda: find_etxn_match(row1, df2, lookup_df2, amount_col1, amount_col2, df2_key, file_used_indices),
            'acc_num': lambda: find_acc_num_match(row1, df2, lookup_df2, amount_col1, amount_col2,
                                                  df1_key=df1_key, df2_key=df2_key,
                                                  file_used_indices=file_used_indices),
            'self':    lambda: find_self_match(row1=row1, df2=df2, lookup_df2=lookup_df2,
                                               amount_col1=amount_col1, amount_col2=amount_col2,
                                               this_acc_name=name1, other_acc_name=name2,
                                               df1_key=df1_key, df2_key=df2_key,
                                               file_used_indices=file_used_indices),
        }
        idx2 = finder_map[logic]()
        # 'self' returns a list; all others need the "not already used" guard
        if logic == 'self':
            return idx2
        if idx2 is not None and idx2 not in file_used_indices[df2_key]:
            return idx2
        return None

    def _resolve_self_matched(self_match_map):
        """
        Deduplicate self-match candidates: if a df2 row is claimed by
        exactly one df1 row → confirm it; otherwise defer.
        Returns the contested {(df2_key, idx2): owners} dict.
        """
        reverse_index: dict  = {}
        for df1_key, idx_map in self_match_map.items():
            for idx1, pairs in idx_map.items():
                for df2_key, idx2 in pairs:
                    reverse_index.setdefault((df2_key, idx2), []).append((df1_key, idx1))

        contested = {}
        for (df2_key, idx2), owners in reverse_index.items():
            if len(owners) == 1:
                df1_key, idx1 = owners[0]
                if idx1 not in file_used_indices[df1_key] and idx2 not in file_used_indices[df2_key]:
                    _apply_match(idx1=idx1, idx2=idx2,
                                 df1=bank_data_storage[df1_key],
                                 df2=bank_data_storage[df2_key],
                                 df1_key=df1_key, df2_key=df2_key)
            else:
                contested[(df2_key, idx2)] = owners
        return contested

    def _apply_match(idx1=None, idx2=None, df1=None, df2=None,
                     df1_key=None, df2_key=None,
                     repeat=False, repeated_self_matches=None):
        nonlocal matches_in_pair, total_matches, inb_trf_count

        if repeat:
            # ── "Many df1 → one df2" resolution ─────────────────────────
            for (df2_key_r, idx2_r), owners in repeated_self_matches.items():
                df2_local   = bank_data_storage[df2_key_r]
                owner_names = [
                    f"{acc_name_storage[k]}-{_matched_category(k)}"
                    for k, _ in owners
                ]
                # Use first owner's key to determine transfer type
                first_df1_key = list({k for k, _ in owners})[0]
                type_for_pair = infer_transfer_type(
                    acc_name_storage[first_df1_key],
                    acc_name_storage[df2_key_r],
                )
                df2_local.at[idx2_r, "TYPE"]     = f"MULTIPLE {type_for_pair}"
                df2_local.at[idx2_r, "Category"] = ", ".join(set(owner_names))
                file_used_indices[df2_key_r].add(idx2_r)

                for k, i1 in owners:
                    df1_local = bank_data_storage[k]
                    df1_local.at[i1, "TYPE"]     = f"{type_for_pair} - Need to verify"
                    df1_local.at[i1, "Category"] = f"{acc_name_storage[df2_key_r]}-{_matched_category(df2_key_r)}"
                    file_used_indices[k].add(i1)
            return

        used1 = file_used_indices[df1_key]
        used2 = file_used_indices[df2_key]
        if idx1 in used1 or idx2 in used2:
            return

        # Determine TYPE
        orig_cat1 = str(df1.at[idx1, "Category"]).upper() if "Category" in df1.columns else ""
        orig_cat2 = str(df2.at[idx2, "Category"]).upper() if "Category" in df2.columns else ""

        type_for_pair = (
            (df1.at[idx1, "TYPE"] if df1.at[idx1, "TYPE"] else None)
            or (df2.at[idx2, "TYPE"] if df2.at[idx2, "TYPE"] else None)
            or infer_transfer_type(acc_name_storage[df1_key], acc_name_storage[df2_key])
        )
        if not type_for_pair:
            if "SIS CON" in orig_cat1 or "SIS CON" in orig_cat2:
                type_for_pair = "SIS CON"
            elif "INB TRF" in orig_cat1 or "INB TRF" in orig_cat2:
                type_for_pair = "INB TRF"

        final_type = type_for_pair or "TRANSFER"
        df1.at[idx1, "TYPE"]     = final_type
        df2.at[idx2, "TYPE"]     = final_type
        df1.at[idx1, "Category"] = f"{acc_name_storage[df2_key]}-{_matched_category(df2_key)}"
        df2.at[idx2, "Category"] = f"{acc_name_storage[df1_key]}-{_matched_category(df1_key)}"

        if str(final_type).upper() in _MATCH_TYPES:
            inb_trf_count += 1

        used1.add(idx1)
        used2.add(idx2)
        matches_in_pair += 1
        total_matches   += 1

    # ── Main comparison loop ─────────────────────────────────────────────────
    for logic in ('imps', 'self', 'etxn', 'acc_num'):
        self_match_map: dict = {}

        for i in range(len(all_files)):
            for j in range(i + 1, len(all_files)):
                df1_key = all_files[i]
                df2_key = all_files[j]

                df1_bank = helpers.extract_bank_name_from_sheet(df1_key)
                df2_bank = helpers.extract_bank_name_from_sheet(df2_key)
                print(f"\n=== {logic.upper()}: {df1_key} ({df1_bank}) vs {df2_key} ({df2_bank}) ===")

                df1 = bank_data_storage[df1_key].copy()
                df2 = bank_data_storage[df2_key].copy()
                _preprocess_df(df1, df1_bank)
                _preprocess_df(df2, df2_bank)

                matches_in_pair = 0
                used_idx1 = file_used_indices[df1_key]
                used_idx2 = file_used_indices[df2_key]
                name1     = acc_name_storage[df1_key]
                name2     = acc_name_storage[df2_key]

                def _process_case(df1_side, lookup_df2, amount_col1, amount_col2):
                    for idx1, row1 in df1_side.iterrows():
                        if idx1 in used_idx1:
                            continue
                        result = _choose_candidate(
                            row1, df2, lookup_df2, amount_col1, amount_col2,
                            name1, name2, df1_key, df2_key, logic,
                        )
                        if logic == "self" and result is not None:
                            for idx2 in result:
                                if idx2 in file_used_indices[df2_key]:
                                    continue
                                bucket = self_match_map.setdefault(df1_key, {}).setdefault(idx1, [])
                                pair   = (df2_key, idx2)
                                if pair not in bucket:
                                    bucket.append(pair)
                        elif logic != "self" and result is not None:
                            _apply_match(idx1=idx1, idx2=result,
                                         df1=df1, df2=df2,
                                         df1_key=df1_key, df2_key=df2_key)

                # Case 1: df1 CR > 0  ↔  df2 DR > 0
                _process_case(df1[df1["CR_val"] > 0], _build_lookup_by_date(df2, "DR_val"), "CR_val", "DR_val")
                # Case 2: df1 DR > 0  ↔  df2 CR > 0
                _process_case(df1[df1["DR_val"] > 0], _build_lookup_by_date(df2, "CR_val"), "DR_val", "CR_val")

                print(f"📊 Matches in this pair: {matches_in_pair}")

                bank_data_storage[df1_key] = _drop_temp_cols(df1)
                bank_data_storage[df2_key] = _drop_temp_cols(df2)

        if logic == "self":
            repeated = _resolve_self_matched(self_match_map)
            if repeated:
                _apply_match(repeat=True, repeated_self_matches=repeated)

    print("\n=== FINAL SUMMARY ===")
    print(f"TOTAL MATCHES FOUND: {total_matches}")
    print(f"INB TRF COUNT: {inb_trf_count}")

    # ── Post-process: assign CASH / SALES type ───────────────────────────────
    print(f"Process Cash type: {cash_deposit_sum}")
    type_value = 'SALES' if cash_deposit_sum > _THRESHOLD else 'CASH'
    for key in all_files:
        df = bank_data_storage[key]
        acc_type = key.split('-')[-1]
        bank_data_storage[key] = categorize_type(df, type_value, acc_type)

    return bank_data_storage
