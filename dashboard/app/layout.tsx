import type { Metadata } from "next";

import { NavLink } from "@/components/nav-link";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "bob-resolve",
  description:
    "How many real people are in this book of business, and how sure are we? Every merge explained. Synthetic data only.",
};

// Only built pages are in the nav, so every item is a link a keyboard can reach. Changes joins
// when its PR lands; a line under the nav says so.
const PAGES: { label: string; href: string }[] = [
  { label: "Overview", href: "/" },
  { label: "Clusters", href: "/clusters" },
  { label: "Review queue", href: "/review" },
  { label: "Benchmark", href: "/benchmark" },
];

// Runs before the first paint, so a dark page never flashes white. The saved choice wins;
// without one (or with storage blocked) the system setting decides. Copied from plan-diff (c13d5c3).
const THEME_SCRIPT = `(function(){var d=null;try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light")d=t==="dark"}catch(e){}if(d===null)d=matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d)})()`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col bg-slate-50 font-sans text-slate-900 lg:flex-row dark:bg-slate-950 dark:text-slate-100">
        <nav aria-label="Main" className="border-b border-slate-200 bg-white lg:w-60 lg:shrink-0 lg:border-r lg:border-b-0 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-2 px-4 pt-3 pb-2 lg:px-5 lg:pt-6">
            <p className="text-sm font-semibold">bob-resolve</p>
            <ThemeToggle />
          </div>
          <ul className="flex gap-1 overflow-x-auto px-2 pb-2 text-sm lg:flex-col lg:px-3">
            {PAGES.map(({ label, href }) => (
              <li key={label} className="shrink-0">
                <NavLink href={href} label={label} />
              </li>
            ))}
          </ul>
          <p className="hidden px-5 pb-4 text-xs text-slate-600 lg:block dark:text-slate-400">The Changes page comes in a later release.</p>
        </nav>
        <main className="mx-auto w-full max-w-[1120px] min-w-0 px-4 py-6 sm:px-10">{children}</main>
      </body>
    </html>
  );
}
