import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { Compass, FlaskConical, Home, ListTree, Settings, SplitSquareHorizontal, TableProperties } from "lucide-react";
import { type ComponentType } from "react";

type NavItem = {
  label: string;
  to: string;
  icon: ComponentType<{ className?: string }>;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/", icon: Home },
  { label: "Run Lab", to: "/run-lab", icon: FlaskConical },
  { label: "Jobs", to: "/jobs", icon: ListTree },
  { label: "Runs", to: "/runs", icon: TableProperties },
  { label: "Compare", to: "/runs/compare", icon: SplitSquareHorizontal },
  { label: "Settings", to: "/settings", icon: Settings },
];

export function AppShell() {
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_20%_0%,#fbe7c7_0%,#f5f1e8_45%,#f0efe9_100%)] text-[#102029]">
      <div className="mx-auto grid min-h-screen w-full max-w-[1440px] grid-cols-1 md:grid-cols-[280px_1fr]">
        <aside className="border-b border-[#d7d0c2] bg-[#f7f1e5]/85 p-5 backdrop-blur md:border-b-0 md:border-r">
          <div className="mb-7">
            <p className="mb-2 inline-flex items-center gap-2 rounded-full border border-[#ceb98f] bg-[#fff6e2] px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[#6c5022]">
              <Compass className="h-3.5 w-3.5" />
              Frontend Track
            </p>
            <h1 className="text-2xl font-semibold tracking-tight text-[#162a37]">Zugzwang UI</h1>
            <p className="mt-1 text-sm text-[#4d6070]">FastAPI + React workspace for experiments and analysis.</p>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.to;
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={[
                    "flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors",
                    active
                      ? "border-[#0f5a74] bg-[#0f5a74] text-[#eff9ff]"
                      : "border-[#d8d3c9] bg-white/70 text-[#28404e] hover:border-[#8ca4af] hover:bg-white",
                  ].join(" ")}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="mt-7 rounded-xl border border-[#d7d0c2] bg-white/70 p-3 text-xs text-[#4f5f69]">
            <p className="font-semibold text-[#213745]">Current milestone</p>
            <p className="mt-1">M8: parity and UX polish</p>
          </div>
        </aside>

        <main className="p-5 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
