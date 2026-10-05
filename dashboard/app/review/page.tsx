import { HowToDecide } from "@/components/how-to-decide";
import { ReviewQueue } from "@/components/review-queue";
import { filterOptions, reviewItems } from "@/lib/review";
import { loadDemoRun } from "@/lib/run-dir";

export const metadata = { title: "Review queue | bob-resolve" };

// Built once from the committed demo run. Filters run in the browser; nothing is written.
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

function single(value: string | string[] | undefined) {
  return typeof value === "string" ? value : "";
}

export default async function ReviewPage({ searchParams }: { searchParams?: SearchParams }) {
  const items = reviewItems(await loadDemoRun());
  const query = searchParams ? await searchParams : {};
  const options = filterOptions(items);
  const requestedSuggestion = single(query.suggestion);
  const requestedRule = single(query.rule);
  const initialSuggestion = options.suggestions.some((option) => option.value === requestedSuggestion) ? requestedSuggestion : "";
  const initialRule = options.rules.some((option) => option.value === requestedRule) ? requestedRule : "";
  const rawPage = single(query.page);
  const parsedPage = /^[1-9]\d*$/.test(rawPage) ? Number(rawPage) : 1;
  const initialPage = Number.isSafeInteger(parsedPage) ? parsedPage : 1;
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
      <ReviewQueue items={items} initialPage={initialPage} initialSuggestion={initialSuggestion} initialRule={initialRule} />
    </div>
  );
}
