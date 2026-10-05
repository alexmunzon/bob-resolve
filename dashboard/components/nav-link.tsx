"use client";
// Copied from plan-diff dashboard/components/nav-link.tsx at c13d5c3 (adapted from agency-intake-kit a54faee).
// PR 9 dropped the "coming soon" text items: they could not take keyboard focus.

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const ITEM = "block rounded-md px-3 py-1.5";

// Only the page you are on is highlighted and announced as the current page.
export function NavLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  // A person's page counts as the Clusters page.
  const current = pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={cn(
        ITEM,
        "focus-visible:outline-2 focus-visible:outline-indigo-600",
        current ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300" : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
      )}
    >
      {label}
    </Link>
  );
}
