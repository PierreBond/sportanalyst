"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, LayoutDashboard, ScrollText, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/matches", label: "Matches", icon: CalendarDays },
  { href: "/value-bets", label: "Value bets", icon: TrendingUp },
  { href: "/reports", label: "Reports", icon: ScrollText },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="flex gap-1 overflow-x-auto px-3 pb-3 pt-1 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:pb-0 lg:pt-0"
    >
      {ITEMS.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-3 text-[13.5px] transition-colors duration-150 ease-out",
              active
                ? "bg-accent/10 text-accent"
                : "text-ink-soft hover:bg-white/[0.05] hover:text-ink"
            )}
          >
            <Icon className="h-4 w-4" strokeWidth={1.75} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
