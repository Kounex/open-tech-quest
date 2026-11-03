"""Transactional, explicitly invoked organizer demo loading and safe removal."""
from sqlalchemy import select
from CTFd.models import (Challenges, Flags, Hints, Submissions, Unlocks,
                         Solutions, SolutionFiles, db)
from .demo_content import ROOMS, challenge_content
from .models import QuestDemoBatch, QuestDemoChallenge, QuestRoom, QuestStart, QuestStep
from .service import now


class DemoConflict(Exception):
    pass


def active_batch():
    return QuestDemoBatch.query.filter_by(active=True).order_by(QuestDemoBatch.id.desc()).first()


def owned_ids(batch):
    return [row.challenge_id for row in QuestDemoChallenge.query.filter_by(batch_id=batch.id).all() if row.challenge_id is not None]


def load_reason(e):
    if e.status != "draft":
        return "Demo content can only be loaded or removed while the event is in draft."
    if active_batch():
        return "Demo content is already loaded. Remove the current demo before loading it again."
    if QuestStep.query.first():
        return "Rooms already contain mapped challenges. Remove those mappings before loading demo content; existing native challenges will be preserved."
    rooms = QuestRoom.query.filter(QuestRoom.slug.in_(list(ROOMS))).all()
    if len(rooms) != len(ROOMS):
        return "All five standard rooms must exist before demo content can be loaded."
    if QuestStart.query.filter(QuestStart.room_id.in_([room.id for room in rooms])).first():
        return "Room start history already exists. Demo content cannot replace a room with recorded activity."
    return None


def unload_reason(e, batch):
    if e.status != "draft":
        return "Demo content can only be loaded or removed while the event is in draft."
    if not batch:
        return "No demo content is loaded."
    ids = owned_ids(batch)
    room_ids = {int(room_id) for room_id in batch.rooms}
    room_ids.update(step.room_id for step in QuestStep.query.filter(QuestStep.challenge_id.in_(ids)).all())
    if QuestStart.query.filter(QuestStart.room_id.in_(list(room_ids))).first():
        return "Demo room starts exist. Removal is disabled to preserve activity history; no event reset is performed."
    if Submissions.query.filter(Submissions.challenge_id.in_(ids)).first():
        return "Demo submissions or solves exist. Removal is disabled to preserve activity history."
    hints = [hint.id for hint in Hints.query.filter(Hints.challenge_id.in_(ids)).all()]
    solutions = [solution.id for solution in Solutions.query.filter(Solutions.challenge_id.in_(ids)).all()]
    if (Unlocks.query.filter(Unlocks.type == "hints", Unlocks.target.in_(hints)).first()
            or Unlocks.query.filter(Unlocks.type == "solutions", Unlocks.target.in_(solutions)).first()):
        return "Demo hints or solutions have been unlocked. Removal is disabled to preserve activity history."
    affected = {step.room_id for step in QuestStep.query.filter(QuestStep.challenge_id.in_(ids)).all()}
    repairable = {step.challenge_id for step in QuestStep.query.filter(QuestStep.room_id.in_(list(affected))).all()} - set(ids)
    for challenge in Challenges.query.filter(~Challenges.id.in_(ids)).all():
        prerequisites = (challenge.requirements or {}).get("prerequisites", [])
        if (challenge.next_id in ids or set(prerequisites).intersection(ids)) and challenge.id not in repairable:
            return f"Native challenge '{challenge.name}' depends on demo content outside a repairable room chain. Remove those dependencies before removing the demo."
    return None


def status(e):
    batch = active_batch()
    reason = unload_reason(e, batch) if batch else load_reason(e)
    return {"active": batch is not None, "challenge_count": len(owned_ids(batch)) if batch else 0,
            "can_load": batch is None and reason is None,
            "can_unload": batch is not None and reason is None, "reason": reason}


def load(e):
    reason = load_reason(e)
    if reason:
        raise DemoConflict(reason)
    batch = QuestDemoBatch(active=True, challenge_ids=[], rooms={})
    db.session.add(batch)
    db.session.flush()
    ids, copies = [], {}
    for room in QuestRoom.query.filter(QuestRoom.slug.in_(list(ROOMS))).order_by(QuestRoom.position).all():
        content = ROOMS[room.slug]
        seeded = {"subtitle": content["subtitle"].strip(), "description": content["description"].strip()}
        copies[str(room.id)] = {"original": {"subtitle": room.subtitle, "description": room.description}, "seeded": seeded}
        room.subtitle, room.description = seeded["subtitle"], seeded["description"]
        chain = []
        for position, item in enumerate(content["challenges"]):
            material = challenge_content(room.slug, item)
            challenge = Challenges(name=material["title"], description=material["description"],
                                   attribution="Public Open Tech Quest organizer demo; not competition content.",
                                   category=room.name, value=100, type="standard", state="visible",
                                   position=position, requirements={"prerequisites": list(chain), "anonymize": False})
            db.session.add(challenge)
            db.session.flush()
            if chain:
                Challenges.query.get(chain[-1]).next_id = challenge.id
            chain.append(challenge.id)
            ids.append(challenge.id)
            db.session.add(QuestStep(room_id=room.id, challenge_id=challenge.id, position=position))
            db.session.add(QuestDemoChallenge(batch_id=batch.id, challenge_id=challenge.id))
            db.session.add(Flags(challenge_id=challenge.id, type="static", content=material["flag"], data=""))
            db.session.add(Hints(challenge_id=challenge.id, title="Public demo answer", content=material["hint"], cost=0))
    batch.challenge_ids, batch.rooms = ids, copies
    db.session.flush()
    return batch


def unload(e):
    batch = active_batch()
    reason = unload_reason(e, batch)
    if reason:
        raise DemoConflict(reason)
    ids = owned_ids(batch)
    affected = {step.room_id for step in QuestStep.query.filter(QuestStep.challenge_id.in_(ids)).all()}
    for room_id in affected:
        remaining = [step.challenge_id for step in QuestStep.query.filter_by(room_id=room_id).order_by(QuestStep.position).all() if step.challenge_id not in ids]
        # Removing/recreating mapping rows avoids transient unique-position
        # collisions. Native real challenge IDs, content and order survive.
        QuestStep.query.filter_by(room_id=room_id).delete(synchronize_session=False)
        db.session.flush()
        for position, challenge_id in enumerate(remaining):
            challenge = Challenges.query.get(challenge_id)
            challenge.requirements = {"prerequisites": remaining[:position], "anonymize": False}
            challenge.next_id = remaining[position + 1] if position + 1 < len(remaining) else None
            challenge.position = position
            db.session.add(QuestStep(room_id=room_id, challenge_id=challenge_id, position=position))
    db.session.flush()
    # Native solution files lack ON DELETE CASCADE, unlike challenge files,
    # flags and hints. Delete only their owned database rows before the parent.
    solutions = [row.id for row in Solutions.query.filter(Solutions.challenge_id.in_(ids)).all()]
    SolutionFiles.query.filter(SolutionFiles.solution_id.in_(solutions)).delete(synchronize_session=False)
    # Recheck ownership atomically with deletion: native removal can null an
    # ownership FK, and a later challenge must never inherit that ownership.
    live_owned = select(QuestDemoChallenge.challenge_id).where(QuestDemoChallenge.batch_id == batch.id, QuestDemoChallenge.challenge_id.isnot(None))
    Challenges.query.filter(Challenges.id.in_(live_owned)).delete(synchronize_session=False)
    for room_id, copies in batch.rooms.items():
        room = QuestRoom.query.get(int(room_id))
        if room:
            for field in ("description", "subtitle"):
                if getattr(room, field) == copies["seeded"][field]:
                    setattr(room, field, copies["original"][field])
    batch.active, batch.active_slot, batch.removed_at = False, None, now()
    db.session.flush()
    return batch
