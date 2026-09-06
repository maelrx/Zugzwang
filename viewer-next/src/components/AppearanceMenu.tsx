import { useEffect, useRef, useState } from "react";
import { FONT_SCALES, THEMES, setAppearance, useAppearance } from "@/lib/appearance";
import type { ThemeId } from "@/lib/appearance";
import { TEXTURES, TEXTURE_ORDER } from "@/lib/textures";

const themeById = (id: ThemeId) => THEMES.find(t => t.id === id)!;

function SlidersIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 7h10 M18 7h2 M14 4.5v5 M4 12h4 M12 12h8 M8 9.5v5 M4 17h9 M17 17h3 M13 14.5v5" />
    </svg>
  );
}

function OptionButton({
  active,
  onClick,
  children,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-pressed={active}
      onClick={onClick}
      className={`flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-[length:calc(10.5px*var(--fs-scale))] font-medium transition-colors ${
        active ? "border-accent bg-panel2 text-accent" : "border-line text-muted hover:border-faint hover:text-paper"
      }`}
    >
      {children}
    </button>
  );
}

export function AppearanceMenu() {
  const appearance = useAppearance();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: PointerEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  const active = themeById(appearance.theme);

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        className="rounded border border-line p-1.5 text-muted hover:text-paper"
        aria-label="Personalizar aparência"
        aria-expanded={open}
        title="Aparência · tema, textura e fonte"
        onClick={() => setOpen(v => !v)}
      >
        <SlidersIcon />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Aparência"
          className="absolute right-0 top-[calc(100%+10px)] z-[90] w-[calc(292px*var(--fs-scale))] rounded-[10px] border border-line bg-panel p-4 shadow-[0_14px_36px_oklch(.08_.005_65_/_0.45)]"
        >
          <p className="mb-2 font-mono text-[length:calc(10px*var(--fs-scale))] uppercase tracking-widest text-faint">Tema</p>
          <div className="grid grid-cols-3 gap-1.5">
            {THEMES.map(t => (
              <OptionButton key={t.id} active={appearance.theme === t.id} onClick={() => setAppearance({ theme: t.id })}>
                <span
                  aria-hidden
                  className="size-3.5 shrink-0 rounded-full border border-line"
                  style={{ background: `linear-gradient(135deg, ${t.bg} 55%, ${t.ac} 55%)` }}
                />
                {t.label}
              </OptionButton>
            ))}
          </div>

          <p className="mb-2 mt-4 font-mono text-[length:calc(10px*var(--fs-scale))] uppercase tracking-widest text-faint">Textura</p>
          <div className="grid grid-cols-5 gap-1.5">
            {TEXTURE_ORDER.map(id => {
              const t = TEXTURES[id];
              const isActive = appearance.texture === id;
              return (
                <button
                  key={id}
                  type="button"
                  title={id === "none" ? "Sem textura" : `Textura ${t.label.toLowerCase()}`}
                  aria-pressed={isActive}
                  onClick={() => setAppearance({ texture: id })}
                  className="flex flex-col items-center gap-1"
                >
                  <span
                    aria-hidden
                    className={`h-8 w-full rounded-md border transition-colors ${isActive ? "border-accent" : "border-line hover:border-faint"}`}
                    style={{
                      backgroundColor: "var(--color-panel2)",
                      backgroundImage: t.uri ? `url("${t.uri}")` : undefined,
                      backgroundSize: `${Math.round(t.tile / 1.5)}px`,
                      backgroundBlendMode: appearance.theme === "light" ? t.light.blend : t.dark.blend,
                    }}
                  />
                  <span className={`text-[length:calc(9px*var(--fs-scale))] ${isActive ? "text-accent" : "text-faint"}`}>{t.label}</span>
                </button>
              );
            })}
          </div>

          <p className="mb-2 mt-4 font-mono text-[length:calc(10px*var(--fs-scale))] uppercase tracking-widest text-faint">Tamanho da fonte</p>
          <div className="grid grid-cols-4 gap-1.5">
            {FONT_SCALES.map(f => (
              <OptionButton
                key={f.value}
                active={appearance.fontScale === f.value}
                onClick={() => setAppearance({ fontScale: f.value })}
                title={`Escala de fonte ${f.label}`}
              >
                {f.label}
              </OptionButton>
            ))}
          </div>

          <p className="mt-3 text-[length:calc(9.5px*var(--fs-scale))] leading-relaxed text-faint">
            Tema {active.label.toLowerCase()} · textura {TEXTURES[appearance.texture].label.toLowerCase()} · fonte {FONT_SCALES.find(f => f.value === appearance.fontScale)?.label}. Salvo neste navegador.
          </p>
        </div>
      )}
    </div>
  );
}
