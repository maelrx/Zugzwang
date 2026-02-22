export function RouterErrorFallback({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Unexpected route error.";
  return (
    <div className="rounded-xl border border-[#cf8f8f] bg-[#fff1ef] p-4 text-sm text-[#8a3434]">
      <p className="font-semibold">Page failed to render.</p>
      <p className="mt-1">{message}</p>
    </div>
  );
}
