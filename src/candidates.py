"""Bound candidate details included in an Auto Match report."""

MAX_CANDIDATES = 10


def candidate_details(paths, score=None):
    paths = sorted(set(paths))
    details = {"candidates": [{"path": path, **({"similarity": round(score, 2)} if score is not None else {})}
                              for path in paths[:MAX_CANDIDATES]]}
    if len(paths) > MAX_CANDIDATES:
        details["candidates_truncated"] = len(paths) - MAX_CANDIDATES
    return details
