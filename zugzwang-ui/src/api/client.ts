export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const text = await response.text();
  const maybeJson = text ? safeJsonParse(text) : null;

  if (!response.ok) {
    const detail =
      maybeJson && typeof maybeJson === "object" && "detail" in maybeJson ? (maybeJson as { detail: unknown }).detail : null;
    throw new ApiError(response.status, typeof detail === "string" ? detail : response.statusText, maybeJson ?? text);
  }

  return (maybeJson as T) ?? ({} as T);
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

