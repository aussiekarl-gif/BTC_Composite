"""Chart-only labelling for the lowest DCA risk band."""
from __future__ import annotations


def add_lowest_risk_multiplier_label(occurrence):
    """Merge exact-zero and (0, .01) into the 0.00–0.01 16x display bar.

    The source occurrence table is not mutated. All other buckets, counts and
    percentages remain unchanged. Invalid negative-risk observations stay
    separately visible and are not assigned a buy multiplier.
    """
    result = occurrence.copy().reset_index(drop=True)
    labels = result["Risk range"].astype(str).tolist()
    if len(result) >= 3 and labels[1] in {"0.000 (floor)", "0.00–0.00"} and labels[2] == "(0.00, 0.01)":
        result.loc[1, "Weeks"] = int(result.loc[1, "Weeks"]) + int(result.loc[2, "Weeks"])
        result.loc[1, "Percent"] = float(result.loc[1, "Percent"]) + float(result.loc[2, "Percent"])
        result.loc[1, "Risk range"] = "0.00–0.01 · 16×"
        result = result.drop(index=2).reset_index(drop=True)
    elif len(result) and labels[0] == "0.00–0.01":
        result.loc[0, "Risk range"] = "0.00–0.01 · 16×"
    elif len(result) and labels[0] == "0.00–0.01":
        result.loc[0, "Risk range"] = "0.00–0.01 · 16×"
    else:
        raise ValueError("Unexpected risk occurrence bucket layout; refusing to mislabel DCA multiplier")
    return result


def chart_highlight_index(source_index):
    """Translate original V5.9 13-bin highlight index to merged chart index."""
    if source_index < 0:
        return -1
    if source_index in (1, 2):
        return 1
    return source_index - 1 if source_index > 2 else source_index
