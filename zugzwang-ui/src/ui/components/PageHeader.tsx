type PageHeaderProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
};

export function PageHeader({ eyebrow, title, subtitle }: PageHeaderProps) {
  return (
    <header className="mb-6">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#617988]">{eyebrow}</p>
      <h2 className="text-3xl font-semibold tracking-tight text-[#142a38]">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm text-[#4f6370]">{subtitle}</p>
    </header>
  );
}

