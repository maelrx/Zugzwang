import { useEffect } from "react";
import { type ToastTone, useNotificationStore } from "../../stores/notificationsStore";

const AUTO_DISMISS_MS = 8_000;

export function ToastContainer() {
  const toasts = useNotificationStore((state) => state.toasts);
  const dismissToast = useNotificationStore((state) => state.dismissToast);

  useEffect(() => {
    const timers = toasts.map((toast) => window.setTimeout(() => dismissToast(toast.id), AUTO_DISMISS_MS));
    return () => {
      for (const timer of timers) {
        window.clearTimeout(timer);
      }
    };
  }, [dismissToast, toasts]);

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[min(92vw,360px)] flex-col gap-2">
      {toasts.map((toast) => (
        <article key={toast.id} className={["pointer-events-auto rounded-xl border px-3 py-2 shadow-lg", toneClassName(toast.tone)].join(" ")}>
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold">{toast.title}</p>
              <p className="mt-0.5 text-xs opacity-90">{toast.message}</p>
              {toast.linkTo ? (
                <a href={toast.linkTo} className="mt-1 inline-flex text-xs font-semibold underline underline-offset-2">
                  {toast.linkLabel ?? "Open"}
                </a>
              ) : null}
            </div>
            <button
              type="button"
              className="rounded-md border border-current/30 px-2 py-0.5 text-[11px] font-semibold"
              onClick={() => dismissToast(toast.id)}
            >
              Dismiss
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}

function toneClassName(tone: ToastTone): string {
  if (tone === "success") {
    return "border-[var(--color-success-border)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]";
  }
  if (tone === "warning") {
    return "border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] text-[var(--color-warning-text)]";
  }
  if (tone === "error") {
    return "border-[var(--color-error-border)] bg-[var(--color-error-bg)] text-[var(--color-error-text)]";
  }
  return "border-[var(--color-info-border)] bg-[var(--color-info-bg)] text-[var(--color-info-text)]";
}
