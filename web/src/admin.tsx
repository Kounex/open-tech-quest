import { useState, type FormEvent } from "react";
import { dateTime, request } from "./api";
import { useResource } from "./hooks";
import { DemoControls } from "./demo";
import { Attendance } from "./attendance";
import { RegistrationControls } from "./registration";
import type {
  AdminState,
  AttendanceState,
  DemoContentState,
  Projector,
  QuestEvent,
  RegistrationState,
  Room,
} from "./types";
import { Arrow, Confirm, Empty, Markdown, Notice } from "./ui";
const tabs = [
  "Event",
  "Rooms",
  "Teams",
  "Awards",
  "Projector",
  "Audit",
] as const;
function text(form: FormData, name: string) {
  return String(form.get(name) || "");
}
function localDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function utcDate(value: string) {
  return value ? new Date(value).toISOString() : null;
}
export function Admin() {
  const resource = useResource<AdminState>("/admin/state", 20000),
    [tab, setTab] = useState<(typeof tabs)[number]>("Event"),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const data = resource.data;
  async function mutate(
    path: string,
    method: string,
    body: unknown,
    success: string,
  ) {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await request(path, method, body);
      setMessage(success);
      await resource.refresh();
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return resource.error ? (
      <Notice tone="error" retry={() => void resource.refresh()}>
        {resource.error}
      </Notice>
    ) : (
      <p role="status">Loading organizer controls…</p>
    );
  const execute = (
    path: string,
    method: string,
    body: unknown,
    success: string,
  ) => void mutate(path, method, body, success).catch(() => {});
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Organizer workspace</p>
          <h1>Run the quest</h1>
          <p className="lede">
            Prepare the rooms, bring teams together and publish fair results.
          </p>
        </div>
        <a href="/admin" className="button secondary">
          Native CTFd admin <Arrow />
        </a>
      </div>
      <nav className="room-tabs" aria-label="Organizer sections">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setMessage("");
              setError("");
            }}
            className={tab === t ? "active" : ""}
          >
            {t}
          </button>
        ))}
      </nav>
      {resource.error && (
        <Notice tone="error" retry={() => void resource.refresh()}>
          Showing saved configuration. {resource.error}
        </Notice>
      )}
      {message && <Notice tone="success">{message}</Notice>}
      {error && <Notice tone="error">{error}</Notice>}
      <div className="admin-content" aria-busy={busy}>
        {tab === "Event" ? (
          <EventControls
            event={data.event}
            demo={data.demo}
            onboarding={data.onboarding}
            registration={data.registration}
            busy={busy}
            mutate={mutate}
            execute={execute}
          />
        ) : tab === "Rooms" ? (
          <RoomsControls data={data} busy={busy} execute={execute} />
        ) : tab === "Teams" ? (
          <Attendance data={data} busy={busy} mutate={mutate} />
        ) : tab === "Awards" ? (
          <AwardControls data={data} busy={busy} execute={execute} />
        ) : tab === "Projector" ? (
          <ProjectorControls data={data} busy={busy} execute={execute} />
        ) : (
          <AuditControls data={data} />
        )}
      </div>
    </>
  );
}
type Mutation = (
  path: string,
  method: string,
  body: unknown,
  success: string,
) => Promise<void>;
type Execute = (
  path: string,
  method: string,
  body: unknown,
  success: string,
) => void;
function EventControls({
  event,
  demo,
  onboarding,
  registration,
  busy,
  mutate,
  execute,
}: {
  event: QuestEvent;
  demo: DemoContentState;
  onboarding: AttendanceState;
  registration: RegistrationState;
  busy: boolean;
  mutate: Mutation;
  execute: Execute;
}) {
  const [reason, setReason] = useState("");
  const draft = event.status === "draft";
  const transitions: Record<
    string,
    { action: string; label: string; description: string }[]
  > = {
    draft: [
      {
        action: "start",
        label: "Start event",
        description:
          "Open all configured rooms and record the common event start. Prize policy and challenge order become fixed.",
      },
    ],
    live: [
      {
        action: "pause",
        label: "Pause event",
        description:
          "Pause challenge starts and submissions for everyone. This interval will be excluded from active times.",
      },
      {
        action: "close",
        label: "Close event",
        description:
          "Record the closing cutoff and stop new qualifying solves. Review the results before publishing.",
      },
    ],
    paused: [
      {
        action: "resume",
        label: "Resume event",
        description: "End this recorded pause and allow teams to continue.",
      },
      {
        action: "close",
        label: "Close event",
        description:
          "Record the closing cutoff. Results can be reviewed before publication.",
      },
    ],
    closed: [
      {
        action: "publish",
        label: "Publish final results",
        description:
          "Store the final award snapshot. Later database edits will not silently change these announced results.",
      },
      {
        action: "reopen",
        label: "Reopen event",
        description:
          "Clear the closing cutoff and return the event to paused. Resume explicitly when the teams are ready. Your reason is recorded.",
      },
    ],
    published: [
      {
        action: "unpublish",
        label: "Unpublish results",
        description:
          "Remove the published snapshot and return the event to closed for review. Your reason is recorded.",
      },
    ],
  };
  return (
    <>
      <section className="admin-panel lifecycle">
        <div className="section-heading">
          <h2>Event lifecycle</h2>
          <span className={`phase phase-${event.status}`}>{event.status}</span>
        </div>
        <ol className="phase-path">
          {["draft", "live", "paused", "closed", "published"].map((phase) => (
            <li className={phase === event.status ? "current" : ""} key={phase}>
              {phase}
            </li>
          ))}
        </ol>
        <div className="timing-facts">
          <span>
            Start <strong>{dateTime(event.start_at)}</strong>
          </span>
          <span>
            Cutoff <strong>{dateTime(event.end_at)}</strong>
          </span>
          <span>
            Roster release <strong>{dateTime(event.rosters_release_at)}</strong>
          </span>
        </div>
        {["closed", "published"].includes(event.status) && (
          <label className="field">
            <span>Reason for reopening or unpublishing</span>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain the organizer correction"
            />
          </label>
        )}
        <div className="actions">
          {transitions[event.status]?.map((action) => (
            <Confirm
              key={action.action}
              label={action.label}
              description={action.description}
              disabled={
                busy ||
                (action.action === "start" &&
                  (demo.active || !onboarding?.can_start)) ||
                (["reopen", "unpublish"].includes(action.action) &&
                  !reason.trim())
              }
              danger={["close", "unpublish"].includes(action.action)}
              onConfirm={() =>
                mutate(
                  "/admin/event/action",
                  "POST",
                  {
                    action: action.action,
                    ...(["reopen", "unpublish"].includes(action.action)
                      ? { reason }
                      : {}),
                  },
                  `${action.label} completed`,
                )
              }
            />
          ))}
        </div>
        {draft && !onboarding?.can_start && (
          <p className="attendance-blocker">
            {onboarding?.start_reason ||
              "Attendance status is not available. Refresh organizer controls before starting."}
          </p>
        )}
      </section>
      <RegistrationControls
        state={registration}
        busy={busy}
        onChange={(enabled) =>
          mutate(
            "/admin/registration",
            "PATCH",
            { enabled },
            enabled
              ? "Public registration opened"
              : "Public registration closed",
          )
        }
      />
      <DemoControls
        state={demo}
        busy={busy}
        onAction={(action) =>
          mutate(
            "/admin/demo",
            "POST",
            { action },
            action === "load"
              ? "Demo content loaded across all five rooms"
              : "Demo content removed",
          )
        }
      />
      <section className="admin-panel">
        <h2>Event configuration</h2>
        <p className="section-copy">
          Prize clocks are fixed when the event starts. All date and time fields
          use your browser’s local time.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            execute(
              "/admin/event",
              "PATCH",
              {
                name: text(f, "name"),
                ...(draft
                  ? {
                      start_at: utcDate(text(f, "start_at")),
                      end_at: utcDate(text(f, "end_at")),
                      rosters_release_at: utcDate(
                        text(f, "rosters_release_at"),
                      ),
                      room_clock: text(f, "room_clock"),
                      overall_clock: text(f, "overall_clock"),
                    }
                  : {}),
              },
              "Event configuration saved",
            );
          }}
        >
          <label className="field">
            <span>Event name</span>
            <input
              name="name"
              defaultValue={event.name}
              required
              maxLength={128}
            />
          </label>
          <fieldset disabled={!draft || busy} className="form-grid">
            <label className="field">
              <span>Scheduled start</span>
              <input
                type="datetime-local"
                name="start_at"
                defaultValue={localDate(event.start_at)}
              />
            </label>
            <label className="field">
              <span>Scheduled end</span>
              <input
                type="datetime-local"
                name="end_at"
                defaultValue={localDate(event.end_at)}
              />
            </label>
            <label className="field">
              <span>Release team rosters</span>
              <input
                type="datetime-local"
                name="rosters_release_at"
                defaultValue={localDate(event.rosters_release_at)}
              />
              <small>Leave empty to release immediately</small>
            </label>
            <label className="field">
              <span>Room timing origin</span>
              <select name="room_clock" defaultValue={event.room_clock}>
                <option value="explicit">Team starts the room</option>
                <option value="event">Common event start</option>
              </select>
            </label>
            <label className="field">
              <span>Overall timing origin</span>
              <select name="overall_clock" defaultValue={event.overall_clock}>
                <option value="event">Common event start</option>
                <option value="team">Team starts its first room</option>
              </select>
            </label>
          </fieldset>
          {!draft && (
            <p className="meta">
              Timing policy and roster settings are locked after draft
            </p>
          )}
          <button className="button" disabled={busy}>
            Save configuration
          </button>
        </form>
      </section>
    </>
  );
}
function RoomsControls({
  data,
  busy,
  execute,
}: {
  data: AdminState;
  busy: boolean;
  execute: Execute;
}) {
  const [slug, setSlug] = useState(data.rooms[0]?.slug || "");
  const room = data.rooms.find((r) => r.slug === slug);
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Room presentation and challenge order</h2>
          <p>
            Challenge descriptions, flags, files and hints stay in native CTFd.
          </p>
        </div>
        <a href="/admin/challenges" className="button secondary">
          Author challenges <Arrow />
        </a>
      </div>
      <div className="admin-room-layout">
        <nav className="admin-room-nav" aria-label="Edit room">
          {data.rooms.map((r) => (
            <button
              key={r.id}
              onClick={() => setSlug(r.slug)}
              className={slug === r.slug ? "active" : ""}
            >
              {r.name}
              <span>{r.steps.length} challenges</span>
            </button>
          ))}
        </nav>
        {room && (
          <RoomForm
            key={room.id}
            room={room}
            data={data}
            busy={busy}
            execute={execute}
          />
        )}
      </div>
    </>
  );
}
function RoomForm({
  room,
  data,
  busy,
  execute,
}: {
  room: Room;
  data: AdminState;
  busy: boolean;
  execute: Execute;
}) {
  const [ids, setIds] = useState(room.steps.map((s) => s.id));
  const [selected, setSelected] = useState("");
  const [introduction, setIntroduction] = useState(room.description);
  const draft = data.event.status === "draft";
  function move(index: number, delta: number) {
    setIds((current) => {
      const next = [...current];
      [next[index], next[index + delta]] = [next[index + delta], next[index]];
      return next;
    });
  }
  return (
    <section className="admin-panel">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          execute(
            `/admin/rooms/${room.slug}`,
            "PATCH",
            {
              name: text(form, "name"),
              subtitle: text(form, "subtitle"),
              description: text(form, "description"),
              theme: {
                accent: text(form, "accent"),
                logo_url: text(form, "logo_url"),
                hero_url: text(form, "hero_url"),
                layout: text(form, "layout"),
              },
              ...(draft ? { challenge_ids: ids } : {}),
            },
            `${room.name} saved`,
          );
        }}
      >
        <div className="form-grid">
          <label className="field">
            <span>Room name</span>
            <input name="name" required defaultValue={room.name} />
          </label>
          <label className="field">
            <span>Subtitle</span>
            <input name="subtitle" defaultValue={room.subtitle} />
          </label>
        </div>
        <label className="field">
          <span>Room introduction (Markdown)</span>
          <textarea
            name="description"
            rows={8}
            maxLength={10000}
            value={introduction}
            onChange={(e) => setIntroduction(e.target.value)}
            aria-describedby={`introduction-help-${room.id}`}
          />
          <small id={`introduction-help-${room.id}`}>
            Use ## headings, **bold**, *italic*, lists, [links](https://…), and
            `inline code`. The subtitle stays plain text on the room card.
          </small>
        </label>
        <details className="introduction-preview">
          <summary>Preview introduction</summary>
          <div className="room-description">
            {introduction.trim() ? (
              <Markdown source={introduction} />
            ) : (
              <p className="meta">Write an introduction to preview it here.</p>
            )}
          </div>
        </details>
        <details className="asset-fields">
          <summary>Theme and artwork</summary>
          <div className="form-grid">
            <label className="field">
              <span>Logo URL</span>
              <input
                name="logo_url"
                defaultValue={room.theme.logo_url || ""}
                placeholder="/plugins/open_tech_quest/assets/…"
              />
            </label>
            <label className="field">
              <span>Hero image URL</span>
              <input
                name="hero_url"
                defaultValue={room.theme.hero_url || ""}
                placeholder="/plugins/open_tech_quest/assets/…"
              />
              <small>
                Leave blank to use this theme’s bundled room illustration.
              </small>
            </label>
            <label className="field">
              <span>Theme layout</span>
              <select
                name="layout"
                defaultValue={room.theme.layout || room.slug}
              >
                {["openshift", "ansible", "rhel", "security", "ai"].map(
                  (layout) => (
                    <option key={layout} value={layout}>
                      {layout}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="field">
              <span>Accent color</span>
              <input
                name="accent"
                pattern="#[0-9a-fA-F]{6}"
                defaultValue={room.theme.accent || "#00a5b5"}
              />
            </label>
          </div>
          <p className="meta">
            Use approved local URLs under /plugins/open_tech_quest/assets/. The
            composed room visual works without an image.
          </p>
        </details>
        <div className="section-heading">
          <h3>Ordered challenge path</h3>
          <span className="meta">
            {draft ? "Editable in draft" : "Locked after event start"}
          </span>
        </div>
        {!ids.length && (
          <p className="meta">
            No challenges mapped yet. Author a native challenge, then add it
            here.
          </p>
        )}
        <ol className="challenge-order">
          {ids.map((id, index) => (
            <li key={id}>
              <span className="order-number">{index + 1}</span>
              <span>
                {data.available_challenges.find((c) => c.id === id)?.name ||
                  room.steps.find((s) => s.id === id)?.title ||
                  `Challenge ${id}`}
              </span>
              {draft && (
                <div className="order-actions">
                  <button
                    type="button"
                    aria-label={`Move challenge ${index + 1} up`}
                    disabled={index === 0 || busy}
                    onClick={() => move(index, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    aria-label={`Move challenge ${index + 1} down`}
                    disabled={index === ids.length - 1 || busy}
                    onClick={() => move(index, 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    onClick={() => setIds(ids.filter((x) => x !== id))}
                    disabled={busy}
                  >
                    Remove
                  </button>
                </div>
              )}
            </li>
          ))}
        </ol>
        {draft && (
          <div className="add-challenge">
            <label className="sr-only" htmlFor={`add-${room.id}`}>
              Challenge to add
            </label>
            <select
              id={`add-${room.id}`}
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={busy}
            >
              <option value="">Choose a challenge</option>
              {data.available_challenges
                .filter(
                  (c) =>
                    !ids.includes(c.id) &&
                    (!c.room_slug || c.room_slug === room.slug),
                )
                .map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.name} · {c.state}
                  </option>
                ))}
            </select>
            <button
              type="button"
              className="button secondary"
              disabled={!selected || busy}
              onClick={() => {
                setIds([...ids, Number(selected)]);
                setSelected("");
              }}
            >
              Add step
            </button>
          </div>
        )}
        <p className="meta">
          Saving updates native challenge requirements to match this sequence.
          Each challenge belongs to one room.
        </p>
        <button className="button" disabled={busy}>
          Save room
        </button>
      </form>
    </section>
  );
}
function AwardControls({
  data,
  busy,
  execute,
}: {
  data: AdminState;
  busy: boolean;
  execute: Execute;
}) {
  return (
    <>
      <section className="admin-panel">
        <div className="section-heading">
          <h2>Review and export awards</h2>
          <a className="button secondary" href="/api/v1/quest/admin/export">
            Download standings CSV <Arrow />
          </a>
        </div>
        <p>
          Overall: distinct mapped solves, then active time to the last solve.
          Rooms: consecutive solved prefix, then milestone time. Ties share a
          rank. Teams with no qualifying solves do not win a prize.
        </p>
        <div className="admin-award-summary">
          <div>
            <span>Eligible teams</span>
            <strong>
              {data.standings.teams.filter((t) => t.total > 0).length}
            </strong>
          </div>
          <div>
            <span>Room timing</span>
            <strong>
              {data.event.room_clock === "explicit"
                ? "Room start"
                : "Event start"}
            </strong>
          </div>
          <div>
            <span>Overall timing</span>
            <strong>
              {data.event.overall_clock === "event"
                ? "Event start"
                : "First room"}
            </strong>
          </div>
          <div>
            <span>Results</span>
            <strong>
              {data.event.results_published
                ? "Published snapshot"
                : "Provisional"}
            </strong>
          </div>
        </div>
      </section>
      <section className="admin-panel">
        <h2>Record a timing correction</h2>
        <p>
          Original CTFd solve timestamps stay intact. Corrections require a
          reason and are recorded in the audit log. Enter a negative number to
          reduce active time.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            execute(
              "/admin/corrections",
              "POST",
              {
                team_id: Number(text(f, "team_id")),
                room_slug: text(f, "room_slug"),
                adjustment_ms: Number(text(f, "seconds")) * 1000,
                reason: text(f, "reason"),
              },
              "Timing correction recorded",
            );
          }}
        >
          <fieldset
            disabled={busy || data.event.results_published}
            className="form-grid"
          >
            <label className="field">
              <span>Team</span>
              <select name="team_id" required>
                <option value="">Choose a team</option>
                {data.teams.map((t) => (
                  <option value={t.id} key={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Room</span>
              <select name="room_slug" required>
                {data.rooms.map((r) => (
                  <option value={r.slug} key={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Adjustment in seconds</span>
              <input
                type="number"
                name="seconds"
                min={-86400}
                max={86400}
                step={1}
                required
              />
              <small>Maximum magnitude: 24 hours</small>
            </label>
            <label className="field">
              <span>Organizer reason</span>
              <textarea name="reason" required minLength={3} rows={2} />
            </label>
          </fieldset>
          <button
            className="button"
            disabled={busy || data.event.results_published}
          >
            Record correction
          </button>
          {data.event.results_published && (
            <p className="meta">
              Unpublish explicitly before recording corrections
            </p>
          )}
        </form>
      </section>
    </>
  );
}
function ProjectorControls({
  data,
  busy,
  execute,
}: {
  data: AdminState;
  busy: boolean;
  execute: Execute;
}) {
  const [view, setView] = useState<Projector["view"]>(data.projector.view);
  return (
    <section className="admin-panel">
      <div className="section-heading">
        <h2>The room’s shared screen</h2>
        <a
          href="/quest/stage"
          className="button secondary"
          target="_blank"
          rel="noopener"
        >
          Open stage <Arrow />
        </a>
      </div>
      <p>
        The projector uses the same standings as every participant. At 1080p,
        two stable panels fit 50 teams without rotating pages.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          execute(
            "/admin/projector",
            "PATCH",
            { view, room_slug: view === "room" ? text(f, "room_slug") : null },
            "Projector display updated",
          );
        }}
      >
        <div className="projector-options">
          {(
            [
              {
                id: "overview",
                label: "Every room",
                detail: "The full team progress matrix",
              },
              {
                id: "overall",
                label: "Overall standings",
                detail: "All qualifying solves and milestone time",
              },
              {
                id: "room",
                label: "One room",
                detail: "Focus on a single challenge path",
              },
              {
                id: "awards",
                label: "Award winners",
                detail: "Overall and room leaders, including ties",
              },
            ] as const
          ).map((option) => (
            <label
              key={option.id}
              className={view === option.id ? "selected" : ""}
            >
              <input
                type="radio"
                name="view"
                value={option.id}
                checked={view === option.id}
                onChange={() => setView(option.id)}
              />
              <strong>{option.label}</strong>
              <span>{option.detail}</span>
            </label>
          ))}
        </div>
        {view === "room" && (
          <label className="field">
            <span>Featured room</span>
            <select
              name="room_slug"
              defaultValue={data.projector.room_slug || data.rooms[0]?.slug}
            >
              {data.rooms.map((r) => (
                <option value={r.slug} key={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <button className="button" disabled={busy}>
          Update projector
        </button>
      </form>
    </section>
  );
}
function AuditControls({ data }: { data: AdminState }) {
  return (
    <section className="admin-panel">
      <h2>Organizer audit</h2>
      <p>
        Lifecycle transitions, configuration changes and corrections retain
        their actor and reason.
      </p>
      {!data.audit.length ? (
        <p className="meta">No organizer changes recorded yet</p>
      ) : (
        <div className="audit-list">
          {data.audit.map((entry) => (
            <article key={entry.id}>
              <div>
                <strong>{entry.action}</strong>
                <time>{dateTime(entry.created_at)}</time>
              </div>
              <span className="meta">Organizer {entry.actor_id}</span>
              <pre>
                {typeof entry.detail === "string"
                  ? entry.detail
                  : JSON.stringify(entry.detail, null, 2)}
              </pre>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
