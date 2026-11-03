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
  return (
    <section className="admin-panel attendance-window-control">
      <div className="section-heading">
        <h2>Attendance check-in</h2>
        <span className="phase">{state.enabled ? "Open" : "Closed"}</span>
      </div>
      <p className="section-copy">
        {state.enabled
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
      {!state.enabled && state.reason && (
        <p className="attendance-blocker">{state.reason}</p>
      )}
      <Confirm
        key={`${state.generation}-${state.enabled}`}
        label={
          target ? "Open attendance check-in" : "Close attendance check-in"
        }
        description={
          target
            ? "Allow participants to confirm that they are at the event and participating. Unconfirmed participants will be prompted again for this opening. This does not start competition clocks, change registration or change the team preparation phase."
            : "Stop new attendance confirmations, including requests from already-open forms. Existing confirmations and their original timestamps stay saved. Team preparation and registration remain unchanged."
        }
        disabled={busy || (target && !state.can_open)}
        danger={!target}
        onConfirm={() => onChange(target)}
      />
    </section>
  );
}
