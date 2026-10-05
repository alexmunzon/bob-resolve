import { Overview } from "@/components/overview";
import { overview } from "@/lib/overview";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

// The committed demo run is read at build time from public/demo-run. No network calls.
export default async function OverviewPage() {
  return <Overview data={overview(await loadRunDir(DEMO_RUN_DIR))} />;
}
