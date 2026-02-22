type InfoCardProps = {
  title: string;
  value: string;
  hint: string;
};

export function InfoCard({ title, value, hint }: InfoCardProps) {
  return (
    <article className="rounded-2xl border border-[#d6d1c8] bg-white/80 p-4 shadow-[0_10px_30px_rgba(22,42,55,0.06)]">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5d7380]">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-[#112835]">{value}</p>
      <p className="mt-1 text-xs text-[#5a6f7b]">{hint}</p>
    </article>
  );
}

