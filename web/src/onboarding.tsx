import { useState } from "react";
import { dateTime, request } from "./api";
import { useResource } from "./hooks";
import type { Onboarding, Viewer } from "./types";
import { Check, Confirm, Notice } from "./ui";

export function ParticipantOnboarding({
  viewer,
  onChanged,
}: {
  viewer: Viewer;
  onChanged: () => Promise<void>;
}) {
  if (!viewer.authenticated || viewer.admin) return null;
  return (
    <PersonalOnboarding key={viewer.id} viewer={viewer} onChanged={onChanged} />
  );
}

function PersonalOnboarding({
  viewer,
  onChanged,
}: {
  viewer: Viewer;
  onChanged: () => Promise<void>;
}) {
  const resource = useResource<Onboarding>("/onboarding", 8000);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [name, setName] = useState("");
  const state = resource.data;
  async function update(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      const result = await request<Onboarding>(path, "POST", body);
      resource.setData(result);
      await onChanged();
      await resource.refresh();
    } catch (error) {
      setError((error as Error).message);
      await resource.refresh();
      await onChanged();
      throw error;
    } finally {
      setBusy(false);
    }
  }
  if (!state)
    return resource.error ? (
      <Notice tone="error" retry={() => void resource.refresh()}>
        {resource.error}
      </Notice>
    ) : (
      <div className="onboarding-loading" role="status">
        Checking your team and attendance…
      </div>
    );
  const team = state.roster_released ? state.team : null;
  return (
    <section
      className="onboarding-panel"
      id="your-team"
      aria-label="Your attendance and team"
    >
      <div className="personal-readiness">
        <div>
          <p className="eyebrow">Your place in the quest</p>
          <h2>
            {state.ready_at ? "You're checked in" : "Ready to join the quest?"}
          </h2>
          <p>
            {state.ready_at
              ? `${viewer.name || "Your attendance"} · Confirmed ${dateTime(state.ready_at)}`
              : "Confirm that you're here on your own device. Your organizers will bring the attending participants into teams."}
          </p>
          <p className="meta">
            Checking in and choosing a team name never start a competition clock
          </p>
        </div>
        {state.ready_at ? (
          <span className="readiness-confirmed">
            <Check /> {state.late ? "Late arrival recorded" : "Ready to quest"}
          </span>
        ) : state.can_ready ? (
          <button
            className="button"
            disabled={busy}
            onClick={() => void update("/onboarding/ready", {}).catch(() => {})}
          >
            {busy ? "Checking in…" : "I'm ready to quest"}
          </button>
        ) : (
          <span className="meta">
            Check-in is not available for this account
          </span>
        )}
      </div>
      {(error || resource.error) && (
        <Notice tone="error" retry={() => void resource.refresh()}>
          {error || resource.error}
        </Notice>
      )}
      {state.late && (
        <div className="onboarding-note">
          Your attendance was recorded after check-in closed.
          {!team && (
            <>
              {" "}
              Please see an organizer for placement
              {state.phase === "finalized"
                ? "; team rosters are already finalized"
                : " in a team"}
              .
            </>
          )}
        </div>
      )}
      {!state.roster_released ? (
        <div className="onboarding-note">
          <h3>Your team will appear at roster release</h3>
          <p>
            {state.ready_at
              ? "Your check-in is saved. "
              : "Confirm your attendance above when you're ready. "}
            Team names and teammates stay private until the organizers release
            the rosters.
          </p>
        </div>
      ) : !team ? (
        <div className="onboarding-note">
          <h3>
            {state.phase === "finalized"
              ? "See an organizer about your team"
              : "Your team is being arranged"}
          </h3>
          <p>
            {state.phase === "check_in"
              ? "Organizers are allocating provisional teams. You can confirm your attendance while they prepare the groups."
              : state.phase === "closed"
                ? "Check-in has closed. Organizers are reviewing attendance and the final group sizes."
                : state.phase === "naming"
                  ? state.ready_at
                    ? "Your readiness is saved. An organizer can place an attending late arrival before rosters are finalized."
                    : "Check in above, then see an organizer about placement before rosters are finalized."
                  : "The final rosters are fixed. An organizer can help you with the next step."}
          </p>
        </div>
      ) : (
        <div className="own-roster">
          <div className="own-team-heading">
            <div>
              <span className="meta">
                {state.phase === "check_in" || state.phase === "closed"
                  ? "Provisional team"
                  : state.phase === "finalized"
                    ? "Final team"
                    : team.name_locked
                      ? "Team name confirmed"
                      : "Your final group"}
              </span>
              <h3>{team.name}</h3>
            </div>
            <span className="meta">
              {team.members.filter((member) => member.ready_at).length} of{" "}
              {team.members.length} checked in
            </span>
          </div>
          <ul className="teammate-list">
            {team.members.map((member) => (
              <li key={member.id}>
                <span>
                  {member.name}
                  {member.id === viewer.id && <small> You</small>}
                </span>
                <span className={member.ready_at ? "member-ready" : "meta"}>
                  {member.ready_at ? (
                    <>
                      <Check /> Ready
                    </>
                  ) : (
                    "Not checked in"
                  )}
                </span>
              </li>
            ))}
          </ul>
          {(state.phase === "check_in" || state.phase === "closed") && (
            <p className="meta roster-explanation">
              These groups are provisional. Organizers will use attendance to
              balance the teams before naming opens.
            </p>
          )}
          {state.can_name && !team.name_locked ? (
            <div className="team-name-claim">
              <div>
                <h3>Give your team its final name</h3>
                <p>
                  Agree with your teammates first. Any checked-in member can
                  confirm the name once; the first confirmation fixes it for
                  your group.
                </p>
              </div>
              <label className="field">
                <span>Team name</span>
                <input
                  maxLength={128}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  disabled={busy}
                  autoComplete="off"
                  placeholder="The name your team agreed on"
                />
              </label>
              <Confirm
                label="Confirm team name"
                description={`Use “${name.trim()}” as your team's final name? This can be confirmed only once. An organizer correction requires a reason.`}
                disabled={busy || !name.trim()}
                onConfirm={() =>
                  update("/onboarding/name", {
                    name: name.trim(),
                    confirm: true,
                  })
                }
              />
            </div>
          ) : state.phase === "naming" && !team.name_locked ? (
            <p className="onboarding-note">
              {state.ready_at
                ? "A checked-in teammate can confirm your team's name once naming is available."
                : "Check in before confirming your team's name."}
            </p>
          ) : team.name_locked ? (
            <p className="meta roster-explanation">
              {state.phase === "finalized"
                ? "Your roster and team name are finalized. Your team shares progress across devices."
                : "Your team's name is fixed. Organizers will finalize the rosters before opening the rooms."}
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
