import { dateTime } from "./api";
import type { AttendanceWindow } from "./types";
import { Confirm } from "./ui";

export function AttendanceWindowControls({
  state,
  busy,
  onChange,
}: {
  state?: AttendanceWindow;
  busy: boolean;
  onChange: (enabled: boolean) => Promise<void>;
}) {
  if (!state)
    return (
      <section className="admin-panel">
        <h2>Attendance check-in</h2>
        <p className="section-copy">
          Attendance window status is not available. Refresh organizer controls
          before changing it.
        </p>
      </section>
    );
  const target = !state.enabled;
  const late = state.late_only;
  return (
    <section className="admin-panel attendance-window-control">
      <div className="section-heading">
        <h2>{late ? "Late attendance check-in" : "Attendance check-in"}</h2>
        <span className="phase">
          {state.enabled ? (state.can_open ? "Open" : "Unavailable") : "Closed"}
        </span>
      </div>
      <p className="section-copy">
        {state.enabled && !state.can_open
          ? "This attendance window cannot accept new confirmations in the current event state. Existing confirmations and recorded history stay saved."
          : late
            ? state.enabled
              ? "Eligible unassigned newcomers can confirm that they are here. An organizer admits them separately into a team; existing players and clocks stay unchanged. This window may remain open during live or paused play, but must close before starting an event still in draft."
              : "Late attendance confirmation is off. When allowed, reopen this window for unassigned newcomers, then admit checked-in arrivals through Teams. Registration, existing confirmations, rosters and clocks stay unchanged."
            : state.enabled
              ? "Participants can explicitly confirm that they are here and taking part. Signed-in participants receive a prompt across the quest. Close this window before reviewing the final groups or finalizing rosters."
              : "New attendance confirmations are off. Registration and sign-in remain independent; existing confirmations, rosters and progress are preserved."}
      </p>
      {state.enabled ? (
        <p className="meta">Opened {dateTime(state.opened_at)}</p>
      ) : state.closed_at ? (
        <p className="meta">Closed {dateTime(state.closed_at)}</p>
      ) : (
        <p className="meta">The attendance window has not been opened</p>
      )}
      {state.reason && <p className="attendance-blocker">{state.reason}</p>}
      <Confirm
        key={`${state.generation}-${state.enabled}-${late}-${state.can_open}`}
        label={
          target
            ? late
              ? "Open late attendance check-in"
              : "Open attendance check-in"
            : late
              ? "Close late attendance check-in"
              : "Close attendance check-in"
        }
        description={
          target
            ? late
              ? "Open late-only attendance for eligible unassigned newcomers? They confirm personally, then an administrator reviews their final placement. This never moves existing players, changes registration or resets a competition clock."
              : "Allow participants to confirm that they are at the event and participating. Unconfirmed participants will be prompted again for this opening. This does not start competition clocks, change registration or change the team preparation phase."
            : "Stop new attendance confirmations, including requests from already-open forms. Existing confirmations and their original timestamps stay saved. Team preparation and registration remain unchanged."
        }
        disabled={busy || (target && !state.can_open)}
        danger={!target}
        onConfirm={() => onChange(target)}
      />
    </section>
  );
}
