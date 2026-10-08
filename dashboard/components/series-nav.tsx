import Link from "next/link";

const LINK = "series-link";

export function SeriesNav() {
  return (
    <nav aria-label="Agency Data Trust Series" className="series-nav">
      <p className="series-title">Agency Data Trust Series</p>
      <ul className="mt-1 flex flex-wrap gap-1 lg:flex-col">
        <li className="flex"><a className={LINK} href="https://agency-intake-kit.vercel.app">1. Agency Intake Kit</a></li>
        <li className="flex"><Link className={LINK} href="/" aria-current="true">2. Bob Resolve</Link></li>
        <li className="flex"><a className={LINK} href="https://plan-diff.vercel.app">3. Plan Diff</a></li>
      </ul>
      <p className="series-description">Separate demos, shared trust principles.</p>
    </nav>
  );
}
