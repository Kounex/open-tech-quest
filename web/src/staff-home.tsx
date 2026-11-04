import type { Bootstrap } from "./types";
import { Arrow, Link, Notice } from "./ui";
export function StaffHome({ data }: { data: Bootstrap }) {
  const viewer = data.viewer;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {viewer.admin ? "Administrator" : "Challenge maintainer"}
          </p>
          <h1>Build the quest experience</h1>
          <p className="lede">
            {viewer.admin
              ? "Prepare rooms, manage accounts and organize the event from your staff workspace."
              : "Prepare room content, challenge paths and accepted answers in your room workspace."}
          </p>
        </div>
      </div>
      <section className="staff-role-card">
        <div>
          <h2>
            {viewer.admin
              ? "Your organizer workspace"
              : "Your room management access"}
          </h2>
          <p>
            You're signed in as {viewer.name}. Staff accounts prepare the quest
            and stay outside participant attendance, teams and awards.
          </p>
        </div>
        {viewer.can_manage_rooms ? (
          <Link className="button" href="/quest/admin">
            Open Organize <Arrow />
          </Link>
        ) : (
          <Notice>
            Room management is not available for this account. An administrator
            can check its access.
          </Notice>
        )}
      </section>
      {viewer.admin && viewer.can_manage_rooms && (
        <section className="staff-room-preview">
          <h2>Preview configured rooms</h2>
          <p className="meta">
            Organizer preview checks challenge content without recording team
            progress
          </p>
          <div>
            {data.rooms.map((room) => (
              <Link key={room.id} href={`/quest/rooms/${room.slug}`}>
                {room.name}
                <Arrow />
              </Link>
            ))}
          </div>
          {!data.rooms.length && (
            <p className="meta">
              No rooms yet. Add the first room in Organize.
            </p>
          )}
        </section>
      )}
    </>
  );
}
