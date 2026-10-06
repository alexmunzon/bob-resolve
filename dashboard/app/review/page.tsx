import { HowToDecide } from "@/components/how-to-decide";
import { PageHeader } from "@/components/page-header";
import { ReviewQueue } from "@/components/review-queue";
import { filterOptions, reviewItems } from "@/lib/review";
import { parseReviewQuery } from "@/lib/review-query";
import { loadDemoRun } from "@/lib/run-dir";

export const metadata = { title: "Review queue | bob-resolve" };

// Rendered per request because it reads the page and filters from the URL. It only reads the demo run; nothing is written.
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

export default async function ReviewPage({ searchParams }: { searchParams?: SearchParams }) {
  const items = reviewItems(await loadDemoRun());
  const initial = parseReviewQuery(searchParams ? await searchParams : {}, filterOptions(items));
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Bob Resolve / Human review" title="What needs a human, most important first?">
        <p className="page-description">
          {items.length} items, in the engine&apos;s order: high severity first, then the closest calls (the score
          nearest a cutoff line). Synthetic data only; no full MBI is shown.
        </p>
      </PageHeader>
      <HowToDecide />
      <ReviewQueue items={items} initialPage={initial.page} initialSuggestion={initial.suggestion} initialRule={initial.rule} />
    </div>
  );
}
