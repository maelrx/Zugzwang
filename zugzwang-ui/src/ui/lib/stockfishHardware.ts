export type StockfishResourceMode = "auto" | "manual";

export type StockfishResources = {
  mode: StockfishResourceMode;
  threads: number;
  hashMb: number;
  source: "auto" | "manual";
  hardwareConcurrency: number | null;
  deviceMemoryGb: number | null;
};

export function resolveStockfishResources(input: {
  mode: StockfishResourceMode;
  manualThreads: number;
  manualHashMb: number;
}): StockfishResources {
  if (input.mode === "manual") {
    return {
      mode: "manual",
      threads: clampThreads(input.manualThreads),
      hashMb: clampHashMb(input.manualHashMb),
      source: "manual",
      hardwareConcurrency: null,
      deviceMemoryGb: null,
    };
  }

  const hardwareConcurrency = readHardwareConcurrency();
  const deviceMemoryGb = readDeviceMemoryGb();
  return {
    mode: "auto",
    threads: recommendThreads(hardwareConcurrency),
    hashMb: recommendHashMb(deviceMemoryGb),
    source: "auto",
    hardwareConcurrency,
    deviceMemoryGb,
  };
}

export function clampThreads(value: number): number {
  if (!Number.isFinite(value)) {
    return 4;
  }
  return Math.max(1, Math.min(64, Math.round(value)));
}

export function clampHashMb(value: number): number {
  if (!Number.isFinite(value)) {
    return 512;
  }
  return Math.max(64, Math.min(8192, Math.round(value)));
}

function recommendThreads(hardwareConcurrency: number | null): number {
  const cores = hardwareConcurrency ?? 8;
  if (cores <= 2) {
    return 1;
  }
  if (cores <= 4) {
    return 2;
  }
  if (cores <= 8) {
    return 4;
  }
  if (cores <= 16) {
    return 8;
  }
  return 12;
}

function recommendHashMb(deviceMemoryGb: number | null): number {
  if (deviceMemoryGb === null) {
    return 512;
  }
  if (deviceMemoryGb <= 4) {
    return 128;
  }
  if (deviceMemoryGb <= 8) {
    return 256;
  }
  if (deviceMemoryGb <= 16) {
    return 512;
  }
  if (deviceMemoryGb <= 32) {
    return 1024;
  }
  return 2048;
}

function readHardwareConcurrency(): number | null {
  try {
    if (typeof navigator === "undefined") {
      return null;
    }
    const value = navigator.hardwareConcurrency;
    if (!Number.isFinite(value) || value <= 0) {
      return null;
    }
    return Math.round(value);
  } catch {
    return null;
  }
}

function readDeviceMemoryGb(): number | null {
  try {
    if (typeof navigator === "undefined") {
      return null;
    }
    const value = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
    if (!Number.isFinite(value) || (value ?? 0) <= 0) {
      return null;
    }
    return Number(value);
  } catch {
    return null;
  }
}
