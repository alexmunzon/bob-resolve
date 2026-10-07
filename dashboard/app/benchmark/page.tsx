import { Benchmark } from "@/components/benchmark";
import { loadDemoBenchmark } from "@/lib/benchmark-loader";

export const metadata = { title: "Benchmark | bob-resolve" };

export default async function BenchmarkPage() {
  return <Benchmark report={await loadDemoBenchmark()} />;
}
