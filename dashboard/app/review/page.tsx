import { HowToDecide } from "@/components/how-to-decide";
import { ReviewQueue } from "@/components/review-queue";
import { reviewItems } from "@/lib/review";
import { loadDemoRun } from "@/lib/run-dir";

export const metadata = { title: "Review queue | bob-resolve" };

// Built once from the committed demo run. Filters run in the browser; nothing is written.
export default async function ReviewPage() {
  const items = reviewItems(await loadDemoRun());
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">What needs a human, most important first?</h1>
        <p className="mt-1 text-sm">
          {items.length} items, in the engine&apos;s order: high severity first, then the closest calls (the score
          nearest a cutoff line). Synthetic data only; no full MBI is shown.
        </p>
      </header>
      <HowToDecide />
      <ReviewQueue items={items} />
    </div>
  );
}
