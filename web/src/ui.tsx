import {
  useEffect,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { navigate } from "./hooks";
export function Link({
  href = "",
  children,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      href={href}
      {...props}
      onClick={(event) => {
        props.onClick?.(event);
        if (
          !event.defaultPrevented &&
          !event.metaKey &&
          !event.ctrlKey &&
          !event.shiftKey &&
          event.button === 0 &&
          href.startsWith("/quest")
        ) {
          event.preventDefault();
          navigate(href);
        }
      }}
    >
      {children}
    </a>
  );
}
export function Arrow() {
  return (
    <svg
      viewBox="0 0 20 20"
      width="20"
      height="20"
      fill="none"
      aria-hidden="true"
    >
      <path d="M3 10h13m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
export function Check() {
  return (
    <svg
      viewBox="0 0 20 20"
      width="20"
      height="20"
      fill="none"
      aria-hidden="true"
    >
      <path d="m4 10 4 4 8-8" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
export function Notice({
  children,
  tone = "info",
  retry,
}: {
  children: ReactNode;
  tone?: "info" | "error" | "success";
  retry?: () => void;
}) {
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
      {retry && (
        <button className="text-button" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
export function Markdown({ source }: { source: string }) {
  return (
    <div
      className="prose"
      dangerouslySetInnerHTML={{
        __html: DOMPurify.sanitize(
          marked.parse(source, { async: false }) as string,
          {
            ADD_ATTR: ["target"],
            FORBID_TAGS: [
              "form",
              "input",
              "button",
              "style",
              "iframe",
              "object",
              "embed",
            ],
          },
        ),
      }}
    />
  );
}
export function Confirm({
  label,
  description,
  onConfirm,
  disabled = false,
  danger = false,
}: {
  label: string;
  description: string;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
  danger?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        className={danger ? "button danger" : "button secondary"}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        {label}
      </button>
      {open && (
        <ConfirmDialog
          label={label}
          description={description}
          onConfirm={onConfirm}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
function ConfirmDialog({
  label,
  description,
  onConfirm,
  onClose,
}: {
  label: string;
  description: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={label}
      className="dialog"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <h2>{label}?</h2>
      <p>{description}</p>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="actions">
        <button
          className="button secondary"
          autoFocus
          disabled={busy}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          className="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await onConfirm();
              onClose();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Working…" : label}
        </button>
      </div>
    </dialog>
  );
}
