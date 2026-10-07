import type { Metadata } from "next";
import { ScanLine } from "lucide-react";

import { NavLink } from "@/components/nav-link";
import { SeriesNav } from "@/components/series-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "bob-resolve",
  description:
    "How many real people are in this book of business, and how sure are we? Every merge explained. Synthetic data only.",
};

// Only delivered pages are in the nav, so every item is a link a keyboard can reach.
const PAGES: { label: string; href: string }[] = [
  { label: "Overview", href: "/" },
  { label: "Clusters", href: "/clusters" },
  { label: "Review queue", href: "/review" },
  { label: "Evidence workflow", href: "/workflow" },
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
      <body className="app-shell font-sans">
        <a href="#main-content" className="skip-link">Skip to content</a>
        <aside className="app-sidebar">
          <div className="sidebar-brand">
            <span className="brand-mark"><ScanLine aria-hidden className="size-4" /></span>
            <div>
              <p className="brand-name">bob-resolve</p>
              <p className="brand-caption">Identity resolution</p>
            </div>
          </div>
          <p className="sidebar-section">Workspace</p>
          <nav aria-label="Main">
            <ul className="main-nav-list flex flex-wrap gap-1 lg:flex-col lg:flex-nowrap">
              {PAGES.map(({ label, href }) => (
                <li key={label} className="shrink-0">
                  <NavLink href={href} label={label} />
                </li>
              ))}
            </ul>
          </nav>
          <p className="sidebar-note">Separate synthetic identity evidence. Review decisions require human evidence.</p>
          <div className="sidebar-tools"><ThemeToggle /></div>
          <SeriesNav />
        </aside>
        <main id="main-content" tabIndex={-1} className="app-main">
          <aside aria-label="Review scope" className="surface mb-6 p-4 text-sm muted">
            Synthetic identity review. A deterministic match does not confirm a person. Browser review labels are not authenticated approval; real agency data and production access remain separate gates.
          </aside>
          {children}
        </main>
      </body>
    </html>
  );
}
