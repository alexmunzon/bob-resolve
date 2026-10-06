"use client";
// Copied from plan-diff dashboard/components/nav-link.tsx at c13d5c3 (adapted from agency-intake-kit a54faee).
// PR 9 dropped the "coming soon" text items: they could not take keyboard focus.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChartNoAxesColumnIncreasing, GitMerge, LayoutDashboard, ListChecks } from "lucide-react";

import { cn } from "@/lib/utils";

const ICONS = { "/": LayoutDashboard, "/clusters": GitMerge, "/review": ListChecks, "/benchmark": ChartNoAxesColumnIncreasing };

// Only the page you are on is highlighted and announced as the current page.
export function NavLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  // A person's page counts as the Clusters page.
  const current = pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  const Icon = ICONS[href as keyof typeof ICONS];
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={cn("nav-item", current && "is-current")}
    >
      {Icon && <Icon aria-hidden className="size-4 shrink-0" />}
      {label}
    </Link>
  );
}
