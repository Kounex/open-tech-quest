import { useEffect, useState } from "react";
import { dateTime, request } from "./api";
import type {
  AdminState,
  Allocation,
  AttendancePlan,
  AttendanceState,
  Participant,
  Team,
} from "./types";
import { Confirm, Empty, Notice } from "./ui";

type Mutation = (
  path: string,
  method: string,
  body: unknown,
  success: string,
) => Promise<void>;
type Props = { data: AdminState; busy: boolean; mutate: Mutation };
const phaseNames = {
  check_in: "Check-in open",
  closed: "Attendance review",
  naming: "Team naming",
  finalized: "Rosters finalized",
};
function eligible(person: Participant) {
  return !person.banned;
}
function teamPeople(data: AdminState, team: Team) {
  return data.participants.filter((person) =>
    team.user_ids.includes(person.id),
  );
}

export function Attendance({ data, busy, mutate }: Props) {
  const [query, setQuery] = useState(""),
    [view, setView] = useState<"teams" | "people">("teams"),
    [filter, setFilter] = useState("all");
  const state = data.onboarding;
  if (!state)
    return (
      <Notice>
        Attendance controls are not available from the server yet. Refresh after
        the update completes.
      </Notice>
    );
  const minimum = Math.ceil(state.team_size * 0.8);
  const undersized = data.teams.filter(
    (team) => team.ready_count > 0 && team.ready_count < minimum,
  ).length;
  const matches = (value: string) =>
    value.toLocaleLowerCase().includes(query.toLocaleLowerCase());
  const teams = data.teams.filter((team) => {
    const people = teamPeople(data, team);
    return (
      (matches(team.name) ||
        people.some(
          (person) => matches(person.name) || matches(person.email),
        )) &&
      (filter === "all" ||
        (filter === "undersized" &&
          team.ready_count > 0 &&
          team.ready_count < minimum) ||
        (filter === "pending" &&
          people.some((person) => !person.ready_at && eligible(person))) ||
        (filter === "unnamed" &&
          team.user_ids.length > 0 &&
          !team.name_locked) ||
        (filter === "ready" &&
          team.ready_count > 0 &&
          team.ready_count === people.filter(eligible).length))
    );
  });
  const people = data.participants.filter(
    (person) =>
      (matches(person.name) ||
        matches(person.email) ||
        matches(
          data.teams.find((team) => team.id === person.team_id)?.name || "",
        )) &&
      (filter === "all" ||
        (filter === "ready" && !!person.ready_at) ||
        (filter === "pending" && !person.ready_at && eligible(person)) ||
        (filter === "unassigned" && !person.team_id && !!person.ready_at) ||
        (filter === "late" && person.late)),
  );
  return (
    <>
      <AttendanceLifecycle data={data} busy={busy} mutate={mutate} />
      <div
        className="attendance-counts"
        role="group"
        aria-label="Attendance totals"
      >
        <div>
          <strong>{state.ready_count}</strong>
          <span>Checked in</span>
        </div>
        <div>
          <strong>{state.pending_count}</strong>
          <span>Pending check-in</span>
        </div>
        <div>
          <strong>{state.unassigned_ready_count}</strong>
          <span>Ready, unassigned</span>
        </div>
        <div>
          <strong>{undersized}</strong>
          <span>Below 80% target</span>
        </div>
        <div>
          <strong>{state.unnamed_count}</strong>
          <span>Teams awaiting names</span>
        </div>
      </div>
      {data.event.status === "draft" && state.phase === "check_in" && (
        <InitialAllocation
          key={state.team_size}
          data={data}
          busy={busy}
          mutate={mutate}
        />
      )}
      {data.event.status === "draft" && state.phase === "closed" && (
        <OptimizeReview data={data} busy={busy} mutate={mutate} />
      )}
      {data.event.status === "draft" && state.phase === "naming" && (
        <LateQueue data={data} busy={busy} mutate={mutate} />
      )}
      <div className="section-heading">
        <div>
          <h2>Teams and attendance</h2>
          <p>
            {state.phase === "check_in"
              ? "Provisional groups show who is here. No check-in starts a competition clock."
              : state.phase === "closed"
                ? "Review attendance before applying the final grouping plan."
                : state.phase === "naming"
                  ? "Final groups can choose their name once. Place any ready late arrivals before finalizing."
                  : "The roster is fixed. A reasoned name correction remains possible before the competition starts."}
          </p>
        </div>
      </div>
      <div className="attendance-toolbar">
        <div className="attendance-views" role="group" aria-label="Roster view">
          <button
            className={view === "teams" ? "active" : ""}
            aria-pressed={view === "teams"}
            onClick={() => {
              setView("teams");
              setFilter("all");
            }}
          >
            Teams <span>{data.teams.length}</span>
          </button>
          <button
            className={view === "people" ? "active" : ""}
            aria-pressed={view === "people"}
            onClick={() => {
              setView("people");
              setFilter("all");
            }}
          >
            Participants <span>{data.participants.length}</span>
          </button>
        </div>
        <label className="attendance-search">
          <span className="sr-only">Search teams or participants</span>
          <input
            type="search"
            placeholder="Search teams, names or email"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          <span className="sr-only">Attendance filter</span>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">All {view}</option>
            <option value="ready">Checked in</option>
            <option value="pending">Pending check-in</option>
            {view === "teams" ? (
              <>
                <option value="undersized">Below 80% target</option>
                <option value="unnamed">Awaiting team name</option>
              </>
            ) : (
              <>
                <option value="unassigned">Ready, unassigned</option>
                <option value="late">Late arrivals</option>
              </>
            )}
          </select>
        </label>
      </div>
      {view === "teams" ? (
        teams.length ? (
          <div className="attendance-team-list">
            {teams.map((team) => (
              <RosterTeam
                key={team.id}
                team={team}
                data={data}
                busy={busy}
                mutate={mutate}
              />
            ))}
          </div>
        ) : (
          <Empty
            title={
              data.teams.length
                ? "No matching teams"
                : "No provisional teams yet"
            }
          >
            {data.teams.length
              ? "Try another search or attendance filter."
              : "Preview the initial allocation to group registered participants while check-in is open."}
          </Empty>
        )
      ) : (
        <ParticipantList people={people} data={data} />
      )}
    </>
  );
}

function AttendanceLifecycle({ data, busy, mutate }: Props) {
  const state = data.onboarding;
  const [size, setSize] = useState(state.team_size);
  useEffect(() => {
    setSize(state.team_size);
  }, [state.team_size]);
  const draft = data.event.status === "draft";
  const settingsEditable =
    draft && ["check_in", "closed"].includes(state.phase);
  return (
    <section className="admin-panel attendance-lifecycle">
      <div className="section-heading">
        <h2>Prepare the attending teams</h2>
        <span className="phase">{phaseNames[state.phase]}</span>
      </div>
      <ol className="phase-path">
        {Object.entries(phaseNames).map(([phase, name]) => (
          <li key={phase} className={phase === state.phase ? "current" : ""}>
            {name}
          </li>
        ))}
      </ol>
      <div className="attendance-settings">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void mutate(
              "/admin/onboarding",
              "PATCH",
              { team_size: size },
              "Team capacity saved",
            ).catch(() => {});
          }}
        >
          <label className="field">
            <span>Maximum people per team</span>
            <input
              type="number"
              min={1}
              max={50}
              value={size}
              disabled={!settingsEditable || busy}
              onChange={(event) => setSize(Number(event.target.value))}
            />
          </label>
          {settingsEditable && (
            <button
              className="button secondary"
              disabled={
                busy ||
                size === state.team_size ||
                !Number.isInteger(size) ||
                size < 1 ||
                size > 50
              }
            >
              Save capacity
            </button>
          )}
        </form>
        <p>
          Maximum size is a hard limit. The 80% target is a guideline; the
          attendance preview explains any smaller groups. Readiness belongs to
          the person and survives a team move.
        </p>
      </div>
      <div className="actions">
        {draft && state.phase === "check_in" && (
          <Confirm
            label="Close check-in"
            description="Close the attendance window and move to review. Participants can still record a late arrival; new readiness invalidates an older optimization preview. No clocks are started."
            disabled={busy}
            onConfirm={() =>
              mutate(
                "/admin/onboarding/action",
                "POST",
                { action: "close_checkin" },
                "Check-in closed; review the attending groups",
              )
            }
          />
        )}
        {draft && state.phase === "closed" && (
          <Confirm
            label="Reopen check-in"
            description="Return to open check-in before final grouping has been applied. Participants keep their recorded readiness."
            disabled={busy}
            onConfirm={() =>
              mutate(
                "/admin/onboarding/action",
                "POST",
                { action: "reopen_checkin" },
                "Check-in reopened",
              )
            }
          />
        )}
        {draft && state.phase === "naming" && (
          <Confirm
            label="Finalize rosters"
            description="Freeze team membership after confirming every competing team has a final name, all assigned members are ready and no ready participant is waiting for placement. This does not start the event."
            disabled={
              busy ||
              state.unassigned_ready_count > 0 ||
              state.unnamed_count > 0 ||
              state.ready_count === 0
            }
            onConfirm={() =>
              mutate(
                "/admin/onboarding/action",
                "POST",
                { action: "finalize" },
                "Team rosters finalized",
              )
            }
          />
        )}
      </div>
      {state.phase === "naming" &&
        (state.unassigned_ready_count > 0 || state.unnamed_count > 0) && (
          <p className="attendance-blocker">
            Before finalizing:{" "}
            {state.unassigned_ready_count > 0
              ? `${state.unassigned_ready_count} ready participant${state.unassigned_ready_count === 1 ? " needs" : "s need"} placement`
              : ""}
            {state.unassigned_ready_count > 0 && state.unnamed_count > 0
              ? " · "
              : ""}
            {state.unnamed_count > 0
              ? `${state.unnamed_count} team${state.unnamed_count === 1 ? " needs" : "s need"} a final name`
              : ""}
          </p>
        )}
      {state.phase === "finalized" && (
        <p className="meta">
          Rosters are finalized. Start the competition separately from the Event
          tab when every other requirement is satisfied.
        </p>
      )}
    </section>
  );
}

function InitialAllocation({ data, busy, mutate }: Props) {
  const [preview, setPreview] = useState<Allocation | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  return (
    <section className="admin-panel">
      <h2>Initial random allocation</h2>
      <p>
        Place eligible registered participants into provisional teams, up to the
        saved maximum of {data.onboarding.team_size}. Existing populated teams
        are preserved. Attendance optimization comes after check-in closes.
      </p>
      <button
        className="button secondary"
        disabled={busy || loading}
        onClick={async () => {
          setLoading(true);
          setPreview(null);
          setError("");
          try {
            setPreview(
              await request<Allocation>("/admin/teams/allocate", "POST", {
                preview: true,
                team_size: data.onboarding.team_size,
              }),
            );
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setLoading(false);
          }
        }}
      >
        {loading ? "Preparing allocation…" : "Preview initial allocation"}
      </button>
      {error && <Notice tone="error">{error}</Notice>}
      {preview && (
        <div className="initial-allocation-preview">
          <h3>
            {preview.groups.length
              ? `${preview.groups.length} provisional teams`
              : "No eligible unassigned participants"}
          </h3>
          <div className="allocation-preview">
            {preview.groups.map((group, index) => (
              <div key={index}>
                <label className="field">
                  <span>Provisional team name</span>
                  <input
                    value={group.name}
                    maxLength={128}
                    onChange={(event) =>
                      setPreview({
                        ...preview,
                        groups: preview.groups.map((entry, i) =>
                          i === index
                            ? { ...entry, name: event.target.value }
                            : entry,
                        ),
                      })
                    }
                  />
                </label>
                <p>
                  {group.user_ids
                    .map(
                      (id) =>
                        data.participants.find((person) => person.id === id)
                          ?.name || `Participant ${id}`,
                    )
                    .join(", ")}
                </p>
              </div>
            ))}
          </div>
          {preview.groups.length > 0 && (
            <Confirm
              label="Apply initial allocation"
              description={`Create the ${preview.groups.length} provisional teams shown above. Participants may still be moved when attendance is reviewed; this is not the final grouping or team naming step.`}
              disabled={
                busy ||
                loading ||
                preview.groups.some((group) => !group.name.trim())
              }
              onConfirm={async () => {
                await mutate(
                  "/admin/teams/allocate",
                  "POST",
                  { preview: false, groups: preview.groups },
                  "Initial provisional teams allocated",
                );
                setPreview(null);
              }}
            />
          )}
        </div>
      )}
    </section>
  );
}

function OptimizeReview({ data, busy, mutate }: Props) {
  const [plan, setPlan] = useState<AttendancePlan | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const name = (id: number) =>
    data.participants.find((person) => person.id === id)?.name ||
    `Participant ${id}`;
  return (
    <section className="admin-panel optimize-panel">
      <h2>Review the attending groups</h2>
      <p>
        Preview includes checked-in eligible participants only. It preserves
        full groups where possible, minimizes moves and spreads a small tail
        across the final groups. No-show accounts are kept; their provisional
        assignments can be cleared.
      </p>
      <button
        className="button secondary"
        disabled={busy || loading}
        onClick={async () => {
          setLoading(true);
          setPlan(null);
          setError("");
          try {
            setPlan(
              await request<AttendancePlan>(
                "/admin/onboarding/optimize",
                "POST",
                { preview: true },
              ),
            );
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setLoading(false);
          }
        }}
      >
        {loading
          ? "Reviewing attendance…"
          : plan
            ? "Refresh optimization preview"
            : "Preview attendance optimization"}
      </button>
      {error && <Notice tone="error">{error}</Notice>}
      {plan && (
        <div className="optimization-review">
          <div className="optimization-totals">
            <span>
              <strong>{plan.groups.length}</strong> final groups
            </span>
            <span>
              <strong>{plan.moves.length}</strong> proposed moves
            </span>
            <span>
              <strong>{plan.unassigned_user_ids.length}</strong> outside final
              groups
            </span>
          </div>
          {plan.warnings.length > 0 && (
            <div className="optimization-warnings" role="status">
              <h3>Review these warnings</h3>
              <ul>
                {plan.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="optimized-groups">
            {plan.groups.map((group, index) => (
              <section key={`${group.team_id}-${index}`}>
                <div>
                  <h3>{group.name}</h3>
                  <span>
                    {group.user_ids.length} / {data.onboarding.team_size} people
                  </span>
                </div>
                <p>{group.user_ids.map(name).join(", ")}</p>
              </section>
            ))}
          </div>
          <details className="optimization-details">
            <summary>Review participant moves ({plan.moves.length})</summary>
            {plan.moves.length ? (
              <ul>
                {plan.moves.map((move) => (
                  <li key={move.user_id}>
                    <strong>{name(move.user_id)}</strong>
                    <span>
                      {data.teams.find((team) => team.id === move.from_team_id)
                        ?.name || "Unassigned"}{" "}
                      → {plan.groups[move.to_group]?.name || "Final group"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No attending participant needs to move</p>
            )}
          </details>
          {plan.unassigned_user_ids.length > 0 && (
            <details className="optimization-details">
              <summary>
                Accounts outside final groups ({plan.unassigned_user_ids.length}
                )
              </summary>
              <p>{plan.unassigned_user_ids.map(name).join(", ")}</p>
              <p className="meta">
                These accounts remain registered. A later check-in appears in
                the organizer placement queue.
              </p>
            </details>
          )}
          <p className="meta">
            This plan is tied to the current attendance, capacity and
            memberships. If anything changes, the server rejects it and you must
            preview again.
          </p>
          <Confirm
            key={plan.fingerprint}
            label="Apply reviewed groups"
            description="Apply exactly the reviewed attendance plan and open team naming. No-show assignments may be cleared without deleting accounts. After this, automatic rebalancing is unavailable because final names belong to these groups."
            disabled={busy || loading || !plan.groups.length}
            onConfirm={async () => {
              await mutate(
                "/admin/onboarding/optimize",
                "POST",
                { preview: false, fingerprint: plan.fingerprint },
                "Attending groups applied; team naming is open",
              );
              setPlan(null);
            }}
          />
        </div>
      )}
    </section>
  );
}

function LateQueue({ data, busy, mutate }: Props) {
  const [selected, setSelected] = useState<number[]>([]),
    [reason, setReason] = useState("");
  const queue = data.participants.filter(
    (person) => eligible(person) && person.ready_at && !person.team_id,
  );
  const queueKey = queue.map((person) => person.id).join(",");
  useEffect(
    () =>
      setSelected((current) =>
        current.filter((id) => queue.some((person) => person.id === id)),
      ),
    [queueKey],
  );
  if (!queue.length) return null;
  return (
    <section className="admin-panel late-arrival-queue">
      <h2>Ready participants awaiting placement</h2>
      <p>
        Place late arrivals in an existing final group with space. Every
        placement needs a reason. Finalize only when this queue is resolved.
      </p>
      {queue.map((person) => (
        <LatePlacement
          key={person.id}
          person={person}
          data={data}
          busy={busy}
          mutate={mutate}
        />
      ))}
      <details className="additional-team">
        <summary>Create an additional team for late arrivals</summary>
        <p>
          When the existing groups are full, create another group without moving
          their members or changing their names. The new members will choose
          their final team name.
        </p>
        <fieldset disabled={busy}>
          <legend>
            Select up to {data.onboarding.team_size} ready participants
          </legend>
          <div className="late-team-choices">
            {queue.map((person) => (
              <label key={person.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(person.id)}
                  disabled={
                    !selected.includes(person.id) &&
                    selected.length >= data.onboarding.team_size
                  }
                  onChange={(event) =>
                    setSelected(
                      event.target.checked
                        ? [...selected, person.id]
                        : selected.filter((id) => id !== person.id),
                    )
                  }
                />
                <span>
                  {person.name}
                  <small>{person.email}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <label className="field">
          <span>Reason for creating an additional team</span>
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            disabled={busy}
            required
          />
        </label>
        <Confirm
          label="Create additional team"
          description={`Create a new final group for ${selected.length} selected ready participant${selected.length === 1 ? "" : "s"}? Existing groups stay intact. The new group must confirm its team name before rosters can be finalized.`}
          disabled={
            busy ||
            !selected.length ||
            selected.length > data.onboarding.team_size ||
            !reason.trim()
          }
          onConfirm={async () => {
            await mutate(
              "/admin/onboarding/action",
              "POST",
              { action: "create_late_team", user_ids: selected, reason },
              "Additional late-arrival team created",
            );
            setSelected([]);
            setReason("");
          }}
        />
      </details>
    </section>
  );
}
function LatePlacement({
  person,
  data,
  busy,
  mutate,
}: Props & { person: Participant }) {
  const [teamId, setTeamId] = useState(""),
    [reason, setReason] = useState("");
  const available = data.teams.filter(
    (team) => team.user_ids.length < data.onboarding.team_size,
  );
  return (
    <form
      className="late-placement"
      onSubmit={(event) => {
        event.preventDefault();
        const team = available.find((team) => team.id === Number(teamId));
        if (!team) return;
        void mutate(
          `/admin/teams/${team.id}`,
          "PATCH",
          { user_ids: [...team.user_ids, person.id], reason },
          `${person.name} placed in ${team.name}`,
        ).catch(() => {});
      }}
    >
      <div>
        <strong>{person.name}</strong>
        <span>
          {person.email} · {person.late ? "Late arrival" : "Checked in"}
        </span>
      </div>
      <label>
        <span className="sr-only">Team for {person.name}</span>
        <select
          value={teamId}
          onChange={(event) => setTeamId(event.target.value)}
          required
          disabled={busy}
        >
          <option value="">
            {available.length
              ? "Choose a team with space"
              : "All teams are at capacity"}
          </option>
          {available.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name} · {team.user_ids.length}/{data.onboarding.team_size}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="sr-only">Placement reason for {person.name}</span>
        <input
          placeholder="Organizer reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          disabled={busy}
        />
      </label>
      <button
        className="button secondary"
        disabled={busy || !teamId || !reason.trim()}
      >
        Place participant
      </button>
    </form>
  );
}

function RosterTeam({ team, data, busy, mutate }: Props & { team: Team }) {
  const [name, setName] = useState(team.name),
    [members, setMembers] = useState(team.user_ids.map(String)),
    [excluded, setExcluded] = useState(team.excluded),
    [reason, setReason] = useState("");
  const membershipKey = team.user_ids.join(",");
  useEffect(() => setName(team.name), [team.name]);
  useEffect(() => setMembers(team.user_ids.map(String)), [membershipKey]);
  useEffect(() => setExcluded(team.excluded), [team.excluded]);
  const phase = data.onboarding.phase;
  const draft = data.event.status === "draft";
  const provisional = draft && (phase === "check_in" || phase === "closed");
  const identityEditable = draft;
  const published = data.event.status === "published";
  const people = teamPeople(data, team);
  const membersChanged =
    members.length !== team.user_ids.length ||
    members.some((id) => !team.user_ids.includes(Number(id)));
  const changed =
    (identityEditable && name !== team.name) ||
    (provisional && membersChanged) ||
    excluded !== team.excluded;
  const reasonRequired =
    (name !== team.name && (team.name_locked || !provisional)) ||
    excluded !== team.excluded;
  return (
    <details className="attendance-team">
      <summary>
        <span className="attendance-team-name">
          {team.name}
          <small>
            {team.excluded
              ? "Excluded from awards"
              : phase === "check_in" || phase === "closed"
                ? "Provisional"
                : team.name_locked
                  ? "Name confirmed"
                  : "Awaiting name"}
          </small>
        </span>
        <span className="attendance-team-size">
          {team.user_ids.length}
          <small>/{data.onboarding.team_size} people</small>
        </span>
        <span
          className={
            team.ready_count === team.user_ids.length && team.ready_count > 0
              ? "member-ready"
              : "meta"
          }
        >
          {team.ready_count} ready
          {team.user_ids.length > team.ready_count
            ? ` · ${team.user_ids.length - team.ready_count} pending`
            : ""}
        </span>
        <span className="meta">View team</span>
      </summary>
      <div className="attendance-team-body">
        <ul className="organizer-member-list">
          {people.map((person) => (
            <li key={person.id}>
              <div>
                <strong>{person.name}</strong>
                <span>{person.email}</span>
              </div>
              <span>
                {person.banned
                  ? "Ineligible"
                  : person.ready_at
                    ? person.late
                      ? "Ready · Late arrival"
                      : "Ready"
                    : "Pending check-in"}
              </span>
            </li>
          ))}
        </ul>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void mutate(
              `/admin/teams/${team.id}`,
              "PATCH",
              {
                ...(identityEditable && name !== team.name ? { name } : {}),
                ...(provisional && membersChanged
                  ? { user_ids: members.map(Number) }
                  : {}),
                ...(excluded !== team.excluded ? { excluded } : {}),
                ...(reason.trim() ? { reason } : {}),
              },
              "Team updated",
            ).catch(() => {});
          }}
        >
          <div className="form-grid">
            <label className="field">
              <span>
                {provisional
                  ? "Provisional team name"
                  : "Organizer name correction"}
              </span>
              <input
                value={name}
                maxLength={128}
                required
                disabled={!identityEditable || busy}
                onChange={(event) => setName(event.target.value)}
              />
              <small>
                {!draft
                  ? "Team identity is fixed after competition start"
                  : provisional
                    ? "Members choose their final name after attendance optimization"
                    : "Correcting a final group name requires an organizer reason"}
              </small>
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={excluded}
                disabled={published || busy}
                onChange={(event) => setExcluded(event.target.checked)}
              />
              Exclude from awards and public standings
            </label>
          </div>
          {provisional && (
            <label className="field">
              <span>Provisional members</span>
              <select
                multiple
                value={members}
                size={Math.min(8, Math.max(3, data.participants.length))}
                disabled={busy}
                onChange={(event) =>
                  setMembers(
                    Array.from(
                      event.target.selectedOptions,
                      (option) => option.value,
                    ),
                  )
                }
              >
                {data.participants
                  .filter(
                    (person) =>
                      eligible(person) &&
                      (!person.team_id || person.team_id === team.id),
                  )
                  .map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name} · {person.ready_at ? "Ready" : "Pending"}
                    </option>
                  ))}
              </select>
              <small>
                Maximum {data.onboarding.team_size} members. Use Command or
                Control to select several people.
              </small>
            </label>
          )}
          <label className="field">
            <span>Organizer reason{reasonRequired ? " (required)" : ""}</span>
            <input
              value={reason}
              required={reasonRequired}
              disabled={published || busy}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Explain a final name or prize eligibility correction"
            />
          </label>
          <button
            className="button secondary"
            disabled={
              busy ||
              published ||
              !changed ||
              (provisional &&
                membersChanged &&
                members.length > data.onboarding.team_size) ||
              (reasonRequired && !reason.trim())
            }
          >
            Save team changes
          </button>
        </form>
      </div>
    </details>
  );
}

function ParticipantList({
  people,
  data,
}: {
  people: Participant[];
  data: AdminState;
}) {
  if (!people.length)
    return (
      <Empty title="No matching participants">
        Try another search or attendance filter.
      </Empty>
    );
  return (
    <div className="attendance-people">
      <table>
        <thead>
          <tr>
            <th scope="col">Participant</th>
            <th scope="col">Team</th>
            <th scope="col">Attendance</th>
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={person.id}>
              <th scope="row">
                {person.name}
                <small>{person.email}</small>
              </th>
              <td>
                {data.teams.find((team) => team.id === person.team_id)?.name ||
                  "Unassigned"}
              </td>
              <td>
                {person.banned ? (
                  "Ineligible"
                ) : person.ready_at ? (
                  <>
                    <span className="member-ready">
                      Ready{person.late ? " · Late" : ""}
                    </span>
                    <small>{dateTime(person.ready_at)}</small>
                  </>
                ) : (
                  "Pending check-in"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
