import { useEffect, useMemo, useReducer } from "react";

export type JobLogLine = {
  stream: "stdout" | "stderr" | "system";
  text: string;
};

type UseJobLogsResult = {
  lines: JobLogLine[];
  done: boolean;
  error: string | null;
};

type DonePayload = {
  status?: string;
};

const MAX_LINES = 500;

export function useJobLogs(jobId: string | null, enabled = true): UseJobLogsResult {
  const [state, dispatch] = useReducer(logsReducer, {
    lines: [],
    done: false,
    error: null,
  });

  const base = useMemo(() => {
    const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "");
    return raw ?? "";
  }, []);

  useEffect(() => {
    dispatch({ type: "reset" });

    if (!jobId || !enabled) {
      dispatch({ type: "done" });
      return;
    }

    if (typeof EventSource === "undefined") {
      dispatch({ type: "append", payload: { stream: "system", text: "EventSource is not available in this runtime." } });
      dispatch({ type: "error", payload: "EventSource unavailable" });
      dispatch({ type: "done" });
      return;
    }

    const url = `${base}/api/jobs/${jobId}/logs`;
    let source: EventSource;
    try {
      source = new EventSource(url);
    } catch (error) {
      const message = toErrorMessage(error);
      if (!isBenignStreamError(message)) {
        dispatch({
          type: "append",
          payload: { stream: "system", text: message || "Unable to start log stream." },
        });
        dispatch({ type: "error", payload: "Log stream error" });
      }
      dispatch({ type: "done" });
      return;
    }

    let isDisposed = false;

    source.addEventListener("stdout", (event) => {
      dispatch({ type: "append", payload: { stream: "stdout", text: event.data } });
    });
    source.addEventListener("stderr", (event) => {
      dispatch({ type: "append", payload: { stream: "stderr", text: event.data } });
    });
    source.addEventListener("error", (event) => {
      if (isDisposed || source.readyState === EventSource.CLOSED) {
        return;
      }

      const message = stringifyEventData(event);
      if (isBenignStreamError(message)) {
        dispatch({ type: "done" });
        source.close();
        return;
      }

      dispatch({ type: "append", payload: { stream: "system", text: stringifyEventData(event) || "log stream error" } });
      dispatch({ type: "error", payload: "Log stream error" });
      source.close();
    });
    source.addEventListener("done", (event) => {
      const payload = safeJsonParse(event.data) as DonePayload | string | null;
      const status =
        payload && typeof payload === "object" && "status" in payload
          ? String(payload.status ?? "completed")
          : "completed";
      dispatch({ type: "append", payload: { stream: "system", text: `[stream closed: ${status}]` } });
      dispatch({ type: "done" });
      source.close();
    });

    return () => {
      isDisposed = true;
      source.close();
    };
  }, [base, enabled, jobId]);

  return state;
}

function safeJsonParse(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function stringifyEventData(event: Event): string {
  if ("data" in (event as { data?: unknown })) {
    const data = (event as { data?: unknown }).data;
    if (typeof data === "string") {
      return data;
    }
    return JSON.stringify(data);
  }
  return "";
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error ?? "");
}

function isBenignStreamError(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("ns_binding_aborted") ||
    normalized.includes("interrupted while the page was loading") ||
    normalized.includes("networkerror when attempting to fetch resource")
  );
}

type LogsAction =
  | { type: "reset" }
  | { type: "append"; payload: JobLogLine }
  | { type: "done" }
  | { type: "error"; payload: string };

function logsReducer(state: UseJobLogsResult, action: LogsAction): UseJobLogsResult {
  if (action.type === "reset") {
    return { lines: [], done: false, error: null };
  }
  if (action.type === "append") {
    const lines = [...state.lines, action.payload];
    return {
      ...state,
      lines: lines.length <= MAX_LINES ? lines : lines.slice(lines.length - MAX_LINES),
    };
  }
  if (action.type === "done") {
    return { ...state, done: true };
  }
  if (action.type === "error") {
    return { ...state, error: action.payload };
  }
  return state;
}
