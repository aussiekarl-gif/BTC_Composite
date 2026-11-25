"""Shared display labels for the historical risk histogram and DCA ladder."""


def risk_ladder_chart_labels(risk_ranges, lower_bounds, ladder):
    """Append the applicable DCA multiplier to each valid risk histogram bucket.

    lower_bounds must align one-for-one with risk_ranges. Use None for invalid
    buckets. The lower bound determines the multiplier because the ladder is a
    step function and each threshold starts a new band.
    """
    if len(risk_ranges) != len(lower_bounds):
        raise ValueError("risk_ranges and lower_bounds must have equal lengths")
    points = sorted((float(x), float(y)) for x, y in ladder)
    labels = []
    multipliers = []
    for label, lower in zip(risk_ranges, lower_bounds):
        if lower is None:
            labels.append(str(label))
            multipliers.append(None)
            continue
        risk = float(lower)
        selected = points[0][1]
        for threshold, multiplier in points:
            if risk >= threshold:
                selected = multiplier
            else:
                break
        labels.append(f"{label}<br>{selected:g}×")
        multipliers.append(selected)
    return labels, multipliers


def risk_history_hover_customdata(risk_line, price_line=None):
    """Return hover customdata aligned to risk dates, with price or a clear n/a."""
    if price_line is None:
        return [["n/a"] for _ in risk_line.index]
    aligned = price_line.reindex(risk_line.index)
    return [[f"${value:,.2f}" if value == value else "n/a"] for value in aligned.to_numpy()]
