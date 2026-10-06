// A benchmark.json shaped like the demo run, with the agreed field names.
export const benchmarkFixture = () => ({
  schema_version: 1,
  label: "measured on synthetic data",
  generated_at: null,
  runs: [{
    run_id: "demo-run",
    dataset: { side: "derived", label: "derived from the answer key", status: "derived" },
    shared_ids: true,
    candidate_pairs: 3458 as number | null,
    model_tiers_used: [] as string[],
    metrics: {
      automatic_precision: 1, automatic_recall: 0.996308, automatic_f1: 0.998151, recall_if_suggestions_confirmed: 0.996308,
      human_confirmed_merges: 0, awaiting_review: 19,
    } as Record<string, unknown>,
  }],
});
