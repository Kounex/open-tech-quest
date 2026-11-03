"""Pure UTC time and competition-rank rules, shared by every presentation."""
def active_ms(origin, milestone, pauses):
    if origin is None or milestone is None:
        return None
    if milestone <= origin:
        return 0
    elapsed = (milestone - origin).total_seconds()
    for start, end in pauses:
        left, right = max(start, origin), min(end or milestone, milestone)
        if right > left:
            elapsed -= (right - left).total_seconds()
    return max(0, round(elapsed * 1000))


def prefix(ids, solves):
    result = []
    for challenge_id in ids:
        if challenge_id not in solves:
            break
        result.append(solves[challenge_id])
    return result


def assign_ranks(rows, count_key, time_key):
    """Competition ranks preserve genuine ties; zero solves is ineligible."""
    rows.sort(key=lambda row: (-row[count_key], row[time_key] if row[time_key] is not None else float("inf"), row.get("name", ""), row.get("id", 0)))
    last, rank = None, None
    for index, row in enumerate(rows, 1):
        key = (row[count_key], row[time_key])
        if key != last:
            rank = index
        row["rank"] = rank if row[count_key] else None
        last = key
    return rows
