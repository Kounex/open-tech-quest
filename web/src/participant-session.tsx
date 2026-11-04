import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { request } from "./api";
import { useResource } from "./hooks";
import type { Onboarding, Viewer } from "./types";
import { Notice } from "./ui";

type ParticipantState = {
  viewer: Viewer;
  state: Onboarding | null;
  loading: boolean;
  error: string;
  busy: boolean;
  refresh: () => Promise<void>;
  update: (path: string, body: unknown) => Promise<void>;
  openPrompt: () => void;
};
const ParticipantContext = createContext<ParticipantState | null>(null);
export function useParticipantSession() {
  return useContext(ParticipantContext);
}

export function ParticipantSession({
  viewer,
  onChanged,
  children,
}: {
  viewer?: Viewer;
  onChanged: () => Promise<void>;
  children: ReactNode;
}) {
  if (!viewer?.authenticated || viewer.role !== "participant" || !viewer.id)
    return (
      <ParticipantContext.Provider value={null}>
        {children}
      </ParticipantContext.Provider>
    );
  return (
    <AuthenticatedParticipantSession
      key={viewer.id}
      viewer={viewer}
      onChanged={onChanged}
    >
      {children}
    </AuthenticatedParticipantSession>
  );
}

function AuthenticatedParticipantSession({
  viewer,
  onChanged,
  children,
}: {
  viewer: Viewer;
  onChanged: () => Promise<void>;
  children: ReactNode;
}) {
  const resource = useResource<Onboarding>("/onboarding", 5000);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [dismissedGeneration, setDismissedGeneration] = useState<number | null>(
      null,
    );
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  async function update(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      const result = await request<Onboarding>(path, "POST", body);
      if (!mounted.current) return;
      resource.setData(result);
      await Promise.all([resource.refresh(), onChanged()]);
    } catch (error) {
      if (!mounted.current) return;
      setError((error as Error).message);
      await Promise.all([resource.refresh(), onChanged()]);
      throw error;
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  const state = resource.data;
  useEffect(() => setError(""), [state?.attendance?.generation]);
  const eligible =
    !!state?.can_ready && !!state.attendance?.enabled && !state.ready_at;
  const showPrompt =
    eligible && dismissedGeneration !== state?.attendance.generation;
  function dismiss() {
    if (state) setDismissedGeneration(state.attendance.generation);
  }
  function openPrompt() {
    if (eligible) {
      setError("");
      setDismissedGeneration(null);
    }
  }
  return (
    <ParticipantContext.Provider
      value={{
        viewer,
        state,
        loading: resource.loading,
        error: error || resource.error,
        busy,
        refresh: resource.refresh,
        update,
        openPrompt,
      }}
    >
      {children}
      {eligible && (
        <aside
          className="participant-attendance-bar"
          aria-label="Attendance check-in"
        >
          <span>Attendance check-in is open</span>
          <button className="text-button" onClick={openPrompt}>
            Confirm your attendance
          </button>
        </aside>
      )}
      {error && !showPrompt && (
        <div className="participant-attendance-feedback">
          <Notice tone="error">
            {error}{" "}
            <button className="text-button" onClick={() => setError("")}>
              Dismiss notice
            </button>
          </Notice>
        </div>
      )}
      {showPrompt && (
        <AttendancePrompt
          key={state.attendance.generation}
          busy={busy}
          error={error || resource.error}
          onDismiss={dismiss}
          onConfirm={() => update("/onboarding/ready", {})}
        />
      )}
    </ParticipantContext.Provider>
  );
}

function AttendancePrompt({
  busy,
  error,
  onDismiss,
  onConfirm,
}: {
  busy: boolean;
  error: string;
  onDismiss: () => void;
  onConfirm: () => Promise<void>;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    titleId = useId(),
    descriptionId = useId();
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.showModal();
    return () => {
      if (previous instanceof HTMLElement && previous.isConnected)
        previous.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="dialog attendance-prompt"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onDismiss();
      }}
    >
      <p className="eyebrow">Attendance check-in</p>
      <h2 id={titleId}>Are you here and ready to quest?</h2>
      <p id={descriptionId}>
        Confirm that you're at the event and taking part. Your organizers will
        use attendance to prepare the teams.
      </p>
      <p className="meta">This confirmation starts no competition clock</p>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="actions">
        <button
          className="button secondary"
          autoFocus
          disabled={busy}
          onClick={onDismiss}
        >
          Not yet
        </button>
        <button
          className="button"
          disabled={busy}
          onClick={() => void onConfirm().catch(() => {})}
        >
          {busy ? "Confirming…" : "I'm ready to quest"}
        </button>
      </div>
    </dialog>
  );
}
