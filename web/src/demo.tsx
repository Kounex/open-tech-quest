import type { DemoContentState } from "./types";
import { Arrow, Confirm, Link } from "./ui";

export function DemoControls({
  state,
  busy,
  onAction,
}: {
  state: DemoContentState;
  busy: boolean;
  onAction: (action: "load" | "unload") => Promise<void>;
}) {
  return (
    <section className="admin-panel">
      <div className="section-heading">
        <h2>Demo content</h2>
        <span className="meta">
          {state.active
            ? `${state.challenge_count} demo challenges loaded`
            : "Preview a populated quest"}
        </span>
      </div>
      <p className="section-copy">
        {state.active
          ? "The demo includes sample challenge chains, hints and Markdown introductions. Preview them with your organizer account while the event stays in draft. Remove the demo before starting the competition."
          : "Populate the supported demo rooms with sample challenges, hints, practice answers and Markdown introductions. The examples are self-contained and need no external cluster or lab. Participants and teams are not created."}
      </p>
      {state.reason && <p className="meta">{state.reason}</p>}
      <div className="actions">
        {state.active ? (
          <>
            <Link href="/quest" className="button secondary">
              Preview the rooms <Arrow />
            </Link>
            <Confirm
              label="Remove demo content"
              description="Remove the loaded demo challenges and restore the previous room introductions where they have not been edited. Unrelated challenges, participants, teams and your later introduction edits are preserved."
              danger
              disabled={busy || !state.can_unload}
              onConfirm={() => onAction("unload")}
            />
          </>
        ) : (
          <Confirm
            label="Load demo content"
            description="Create clearly marked demo challenges in the supported demo rooms and temporarily replace room introductions and subtitles with formatted examples. Existing unmapped challenges, participants and teams are preserved. You can remove the demo again while in draft."
            disabled={busy || !state.can_load}
            onConfirm={() => onAction("load")}
          />
        )}
      </div>
    </section>
  );
}
