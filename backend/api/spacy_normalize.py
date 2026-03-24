from difflib import SequenceMatcher
import spacy
import re

nlp = spacy.load("en_core_web_sm")

# ── Constants ──────────────────────────────────────────────────────────────────

# Pre-compiled: strip M/S prefixes and non-alphanumeric characters in one pass
_PREFIX_RE  = re.compile(r"\bm[/ ]?s\b", re.IGNORECASE)
_CLEAN_RE   = re.compile(r"[^a-z0-9\s]")
_SPACE_RE   = re.compile(r"\s+")

STOP_WORDS = frozenset({
    "imps", "neft", "upi", "rtgs", "payment",
    "bank", "ltd", "limited", "pvt", "private",
    "services", "service", "fin", "finance",
})


# ── Private helpers ────────────────────────────────────────────────────────────

def _concat_match(token: str, token_list: list[str], max_concat: int = 4) -> bool:
    """Return True if *token* equals any run of up to *max_concat* consecutive items."""
    n = len(token_list)
    for i in range(n):
        concat = token_list[i]
        if concat == token:
            return True
        for j in range(i + 1, min(i + max_concat, n)):
            concat += token_list[j]
            if concat == token:
                return True
    return False


# ── Public helpers ─────────────────────────────────────────────────────────────

def normalize_name(name: str) -> list[str]:
    """Normalize and tokenize a name / category string."""
    if not name:
        return []
    s = name.lower().replace("&", " and ")
    s = _PREFIX_RE.sub(" ", s)
    s = _CLEAN_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s).strip()
    doc = nlp(s)
    return [tok.text for tok in doc if tok.text and tok.text not in STOP_WORDS]


def is_same_name(
    account_name: str,
    category_text: str,
    containment_threshold: float = 0.80,
    min_shared_tokens: int = 2,
    seq_fallback_threshold: float = 0.88,
) -> dict:
    acc_tokens = normalize_name(account_name)
    cat_tokens = normalize_name(category_text)

    acc_set = set(acc_tokens)
    cat_set = set(cat_tokens)

    # Hard rejection: category too small
    if len(cat_set) < min_shared_tokens:
        return {
            "same": False,
            "reason": "category_too_short",
            "account_tokens": acc_tokens,
            "category_tokens": cat_tokens,
        }

    shared      = acc_set & cat_set
    containment = len(shared) / len(cat_set)

    if containment >= containment_threshold and len(shared) >= min_shared_tokens:
        return {
            "same": True,
            "reason": "category_tokens_contained_in_account",
            "scores": {"containment": round(containment, 3), "shared_tokens": list(shared)},
        }

    # Fallback: character-level similarity
    seq_sim = SequenceMatcher(None, " ".join(acc_tokens), " ".join(cat_tokens)).ratio()
    if seq_sim >= seq_fallback_threshold:
        return {
            "same": True,
            "reason": "high_sequence_similarity_fallback",
            "scores": {"sequence": round(seq_sim, 3)},
        }

    return {
        "same": False,
        "reason": "below_thresholds",
        "scores": {
            "containment":   round(containment, 3),
            "sequence":      round(seq_sim, 3),
            "shared_tokens": list(shared),
        },
    }


def description_contains_category(
    category: str,
    description: str,
    max_concat: int = 4,
    containment_threshold: float = 0.75,
    min_shared_tokens: int = 2,
    seq_fallback_threshold: float = 0.88,
    min_token_length: int = 3,
) -> dict:
    """
    Directional containment test:
    category (short, noisy) must be largely explained by description (longer).
    """
    cat_tokens  = normalize_name(category)
    desc_tokens = normalize_name(description)

    if not cat_tokens:
        return {
            "contains": False,
            "reason": "empty_category_after_normalization",
            "category": category,
            "description": description,
        }

    # Filter short tokens
    cat_tokens_f  = [t for t in cat_tokens  if len(t) >= min_token_length]
    desc_tokens_f = [t for t in desc_tokens if len(t) >= min_token_length]

    if len(cat_tokens_f) < min_shared_tokens:
        return {
            "contains": False,
            "reason": "category_too_short_after_filtering",
            "cat_tokens":  cat_tokens,
            "desc_tokens": desc_tokens,
        }

    cat_set  = set(cat_tokens_f)
    desc_set = set(desc_tokens_f)
    shared   = cat_set & desc_set

    # ── PRIMARY: token containment ────────────────────────────────────────
    containment = len(shared) / len(cat_set)
    if containment >= containment_threshold and len(shared) >= min_shared_tokens:
        return {
            "contains": True,
            "reason": "category_tokens_contained_in_description",
            "scores": {"containment": round(containment, 3), "shared_tokens": list(shared)},
        }

    # ── CONCAT MATCH (e.g. TATACAP ← TATA + CAP) ─────────────────────────
    # Tokens already in desc_set count as hits; only run concat on the rest.
    concat_hits = len(shared) + sum(
        1 for ct in cat_set - shared
        if _concat_match(ct, desc_tokens_f, max_concat)
    )
    concat_containment = concat_hits / len(cat_set)

    if concat_containment >= containment_threshold and concat_hits >= min_shared_tokens:
        return {
            "contains": True,
            "reason": "concat_based_containment",
            "scores": {"containment": round(concat_containment, 3), "matched_tokens": concat_hits},
        }

    # ── SEQUENCE SIMILARITY FALLBACK ──────────────────────────────────────
    norm_cat  = " ".join(cat_tokens_f)
    norm_desc = " ".join(desc_tokens_f)
    if norm_cat and norm_desc:
        seq_sim = SequenceMatcher(None, norm_cat, norm_desc).ratio()
        if seq_sim >= seq_fallback_threshold:
            return {
                "contains": True,
                "reason": "high_sequence_similarity_fallback",
                "scores": {"sequence_similarity": round(seq_sim, 3)},
            }

    return {
        "contains": False,
        "reason": "below_thresholds",
        "scores": {
            "containment":        round(containment, 3),
            "concat_containment": round(concat_containment, 3),
            "shared_tokens":      list(shared),
        },
    }
