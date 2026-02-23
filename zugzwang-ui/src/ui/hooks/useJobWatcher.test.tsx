import { act, cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { JobResponse } from "../../api/types";
import { useNotificationStore } from "../../stores/notificationsStore";
import { usePreferencesStore } from "../../stores/preferencesStore";
import { useJobWatcher } from "./useJobWatcher";

let mockJobs: JobResponse[] = [];

vi.mock("../../api/queries", () => ({
  useJobs: () => ({
    data: mockJobs,
  }),
}));

function HookHarness() {
  useJobWatcher();
  return null;
}

describe("useJobWatcher", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockJobs = [];
    useNotificationStore.setState({ toasts: [] });
    usePreferencesStore.setState({
      defaultProvider: null,
      defaultModel: null,
      autoEvaluate: true,
      stockfishDepth: 12,
      notificationsEnabled: true,
      theme: "light",
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("does not emit stale toasts for transitions while notifications were disabled", async () => {
    mockJobs = [buildJob("queued")];
    const view = render(<HookHarness />);

    await waitFor(() => {
      expect(useNotificationStore.getState().toasts).toHaveLength(0);
    });

    act(() => {
      usePreferencesStore.getState().setNotificationsEnabled(false);
    });

    mockJobs = [buildJob("completed")];
    view.rerender(<HookHarness />);

    await waitFor(() => {
      expect(useNotificationStore.getState().toasts).toHaveLength(0);
    });

    act(() => {
      usePreferencesStore.getState().setNotificationsEnabled(true);
    });
    view.rerender(<HookHarness />);

    await waitFor(() => {
      expect(useNotificationStore.getState().toasts).toHaveLength(0);
    });
  });

  it("emits terminal toast for live transitions while notifications are enabled", async () => {
    mockJobs = [buildJob("queued")];
    const view = render(<HookHarness />);

    await waitFor(() => {
      expect(useNotificationStore.getState().toasts).toHaveLength(0);
    });

    mockJobs = [buildJob("completed")];
    view.rerender(<HookHarness />);

    await waitFor(() => {
      const toasts = useNotificationStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0]?.title).toBe("Job completed");
    });
  });
});

function buildJob(status: JobResponse["status"]): JobResponse {
  return {
    job_id: "job-1",
    job_type: "run",
    status,
    pid: 123,
    command: ["python", "-m", "zugzwang.cli", "run"],
    created_at_utc: "2026-02-23T00:00:00Z",
    updated_at_utc: null,
    stdout_path: "results/ui_jobs/logs/job-1.stdout.log",
    stderr_path: "results/ui_jobs/logs/job-1.stderr.log",
    run_id: "run-1",
    run_dir: "results/runs/run-1",
    meta: {},
    result_payload: null,
    exit_code: null,
  };
}
