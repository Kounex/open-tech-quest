import { useId } from "react";
import type { AttendanceState, QuestEvent } from "./types";

export function TeamNamingPolicy({
  state,
  event,
  busy,
  onChange,
}: {
  state: AttendanceState;
  event: QuestEvent;
  busy: boolean;
  onChange: (enabled: boolean) => Promise<void>;
}) {
  const helpId = useId();
  const editable =
    event.status === "draft" &&
    ["check_in", "closed", "naming"].includes(state.phase);
  return (
    <div className="team-naming-policy">
      <label className="checkbox-field">
        <input
          type="checkbox"
          checked={!!state.allow_team_naming}
          disabled={busy || !editable}
          aria-describedby={helpId}
          onChange={(event) => {
            const enabled = event.currentTarget.checked;
            void onChange(enabled).catch(() => {});
          }}
        />
        Let participants choose team names
      </label>
      <p id={helpId} className="meta">
        {state.allow_team_naming
          ? "Any checked-in current teammate can choose the team's unique name once before finalization. Enabling this opens only generated, unclaimed names; chosen or organizer-corrected names stay fixed."
          : "Teams receive fixed generated names such as Team 1 and Team 2 when the reviewed groups are applied. Participant name confirmation is not required."}
      </p>
      <p className="meta">
        {editable
          ? "Turning this off fixes current names without discarding a chosen name. Naming policy changes invalidate older formation previews."
          : "The naming policy is fixed after roster finalization or competition start."}
      </p>
    </div>
  );
}
