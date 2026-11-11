"""Threshold-based fuzzy matching over the normalized catalog name index."""

from difflib import SequenceMatcher
import re

from .name_matching import normalize_name
from .variants import select_variant


def _compatible(left, right):
    # Do not trade channel numbers or plus variants for a high text score.
    return (re.findall(r"\d+", left) == re.findall(r"\d+", right)
            and ("plus" in left) == ("plus" in right))


def match_fuzzy(channel_name, index, threshold, prefix="", prefix_mode="literal", variant="strict", catalog_id=None):
    """Return the unique best path strictly above a similarity percentage.

    Scores are SequenceMatcher ratios on normalized names, multiplied by 100.
    Exact top-score ties across different paths are ambiguous. Similarity is
    not a probability, and a unique result is not proof of correct identity.
    """
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not 0 <= threshold <= 100):
        raise ValueError("Fuzzy threshold must be between 0 and 100")
    name = normalize_name(channel_name, prefix, prefix_mode)
    if not name:
        return {"path": None, "reason": "no_match", "score": None}
    best_score = None
    best_paths = set()
    for candidate, paths in index.items():
        if not candidate or not _compatible(name, candidate):
            continue
        score = SequenceMatcher(None, name, candidate, autojunk=False).ratio() * 100
        if best_score is None or score > best_score:
            best_score = score
            best_paths = set(paths)
        elif score == best_score:
            best_paths.update(paths)
    if best_score is None or not best_paths:
        return {"path": None, "reason": "no_match", "score": None}
    if best_score <= threshold:
        return {"path": None, "reason": "below_threshold", "score": best_score}
    selected = select_variant(best_paths, variant, catalog_id)
    if selected is None:
        return {"path": None, "reason": "ambiguous", "score": best_score}
    return {"path": selected, "reason": None, "score": best_score}
