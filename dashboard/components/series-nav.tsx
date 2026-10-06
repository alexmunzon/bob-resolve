import Link from "next/link";

const LINK = "rounded px-2 py-1.5 text-indigo-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-indigo-600 dark:text-indigo-300";

export function SeriesNav() {
  return (
    <nav aria-label="Agency Data Trust Series" className="border-t border-slate-200 px-3 py-3 text-xs lg:mx-3 lg:px-0 dark:border-slate-800">
      <p className="px-2 font-semibold text-slate-600 dark:text-slate-400">Agency Data Trust Series</p>
      <ul className="mt-1 flex flex-wrap gap-1 lg:flex-col">
        <li className="flex"><a className={LINK} href="https://agency-intake-kit.vercel.app">1. Intake Kit</a></li>
        <li className="flex"><Link className={LINK} href="/" aria-current="true">2. Bob Resolve</Link></li>
        <li className="flex"><a className={LINK} href="https://plan-diff.vercel.app">3. Plan Diff</a></li>
      </ul>
      <p className="mt-2 px-2 text-slate-600 dark:text-slate-400">Separate demos, shared trust principles.</p>
    </nav>
  );
}
