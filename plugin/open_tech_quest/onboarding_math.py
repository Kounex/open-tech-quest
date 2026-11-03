"""Deterministic attendance grouping with bounded capacity and minimum moves."""
import math


def optimize(ready_ids, memberships, teams, capacity, protected_ids=(), reserved_names=()):
    """Return selected bins and assignment; user IDs belong to exactly one bin.

    Candidate teams are ranked by retained attendance. Selecting the largest
    disjoint cohorts maximizes retained members. Lower-bound deficits consume
    unassigned attendees first, then the fewest donor members. Full cohorts are
    broken only when needed, using the smallest surplus donors last.
    """
    ready = set(ready_ids)
    if not ready:
        raise ValueError("No ready eligible participants are available")
    members = {team["id"]: sorted(u for u in ready if memberships.get(u) == team["id"]) for team in teams}
    protected = set(protected_ids)
    if any(len(members.get(tid, [])) > capacity for tid in protected):
        raise ValueError("A team with activity exceeds capacity; resolve its roster before optimizing")
    protected = {tid for tid in protected if members.get(tid)}
    count = max(math.ceil(len(ready) / capacity), len(protected))
    lower = math.ceil(capacity * .8)
    balanced = len(ready) < count * lower
    minimum = len(ready) // count if balanced else lower
    maximum = math.ceil(len(ready) / count) if balanced else capacity
    # Fixed activity cohorts cannot be split to force a prettier distribution.
    if any(len(members[tid]) > maximum for tid in protected):
        maximum = capacity
    candidates = sorted(teams, key=lambda t: (
        t["id"] not in protected, -min(len(members[t["id"]]), maximum),
        len(members[t["id"]]) != capacity, t["id"]))
    selected = candidates[:count]
    groups = [{"team_id": t["id"], "name": t["name"], "user_ids": members[t["id"]][:maximum]} for t in selected]
    existing_names = {name.casefold() for name in reserved_names}
    existing_names.update(t["name"].casefold() for t in teams)
    number = 1
    while len(groups) < count:
        while f"Team {number:02}".casefold() in existing_names:
            number += 1
        name = f"Team {number:02}"
        existing_names.add(name.casefold())
        groups.append({"team_id": None, "name": name, "user_ids": []})
    retained = {u for group in groups for u in group["user_ids"]}
    pool = sorted(ready - retained)
    # Fill deficits using unattached/moved participants before disturbing a
    # retained member. If necessary, drain non-full donors before full cohorts.
    for group in groups:
        while len(group["user_ids"]) < minimum:
            if pool:
                group["user_ids"].append(pool.pop(0))
                continue
            donors = [g for g in groups if len(g["user_ids"]) > minimum and g["team_id"] not in protected]
            if not donors:
                break  # Attendance target is soft; activity cohorts stay intact.
            donor = min(donors, key=lambda g: (len(g["user_ids"]) == capacity, -len(g["user_ids"]), -(g["team_id"] or 0)))
            group["user_ids"].append(donor["user_ids"].pop())
    # A surplus pool can fill the least-populated bins without moving anyone
    # retained. Ties use stable group order, so repeat previews never reshuffle.
    for uid in pool:
        destination = min((i for i, g in enumerate(groups) if len(g["user_ids"]) < maximum), key=lambda i: (len(groups[i]["user_ids"]), i))
        groups[destination]["user_ids"].append(uid)
    for group in groups:
        group["user_ids"].sort()
    warnings = []
    if any(len(g["user_ids"]) < lower for g in groups):
        warnings.append(f"The {lower}-person attendance target (80% of {capacity}) cannot be met by every group; capacity remains enforced.")
    return groups, warnings
