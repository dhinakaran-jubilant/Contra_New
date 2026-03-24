from . import config, helpers
import re

# ── Pre-compiled patterns ─────────────────────────────────────────────────────

# Strip common company suffixes in one pass (ordered longest-first to avoid partial matches)
_SUFFIX_RE = re.compile(
    r'\s+(?:PVT\s+LTD|PRIVATE\s+LIMITED|PVT|PRIVATE|LIMITED|LLP|LTD|CO)\b',
    flags=re.IGNORECASE,
)

_AMP_RE = re.compile(r'\s*&\s*')

_FILLER_WORDS = frozenset({'THE', 'AND', 'OF', 'FOR', 'WITH'})


# ── Public functions ───────────────────────────────────────────────────────────

def get_party_type(raw_name: str) -> str:
    """Classify a name as COMPANY, PERSON, or OTHER."""
    norm = helpers.normalize_name(raw_name)
    if not norm:
        return 'OTHER'
    tokens = norm.split()
    if any(tok in config.FIRM_KEYWORDS for tok in tokens) or len(tokens) >= 4:
        return 'COMPANY'
    if all(t.isalpha() for t in tokens):
        return 'PERSON'
    return 'OTHER'


def extract_core_name(name: str) -> str:
    """Remove company suffixes and stray ampersands from a normalised name."""
    norm = helpers.normalize_name(name)
    if not norm:
        return ''
    core = _SUFFIX_RE.sub('', norm)
    return _AMP_RE.sub(' ', core).strip()


def same_entity(name1: str, name2: str) -> bool:
    """Return True if two names refer to the same legal entity."""
    if not name1 or not name2:
        return False

    n1 = helpers.normalize_name(name1)
    n2 = helpers.normalize_name(name2)
    if n1 == n2:
        return True

    core1 = extract_core_name(name1)
    core2 = extract_core_name(name2)
    if core1 and core2 and core1 == core2:
        return True

    t1 = set(core1.split())
    t2 = set(core2.split())
    if not t1 or not t2:
        return False

    if get_party_type(name1) == 'COMPANY' and get_party_type(name2) == 'COMPANY':
        # Filter out filler words for a cleaner comparison
        f1 = t1 - _FILLER_WORDS
        f2 = t2 - _FILLER_WORDS
        min_len = min(len(f1), len(f2))
        if min_len == 0:
            return False

        common_filtered = (f1 & f2) - _FILLER_WORDS
        if len(common_filtered) / min_len >= 0.7:
            return True

        # Acronym / no-space match (e.g. "GTIMES" vs "G TIMES")
        if core1.replace(' ', '') == core2.replace(' ', ''):
            return True

    return False


def infer_transfer_type(name_from: str, name_to: str) -> str:
    """
    Infer the transfer type between two account holders.
    Returns 'INB TRF' for intra-entity transfers, 'SIS CON' for sister concerns.
    """
    t1 = get_party_type(name_from)
    t2 = get_party_type(name_to)

    if t1 == t2 and t1 in {'COMPANY', 'PERSON'}:
        return 'INB TRF' if same_entity(name_from, name_to) else 'SIS CON'

    if {t1, t2} == {'COMPANY', 'PERSON'}:
        return 'SIS CON'

    return 'INB TRF'
