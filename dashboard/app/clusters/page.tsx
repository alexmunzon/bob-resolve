import { ClusterList } from "@/components/cluster-list";
import { clusterList } from "@/lib/clusters";
import { loadDemoRun } from "@/lib/run-dir";

export const metadata = { title: "Clusters | Bob Resolve" };

// Built once from the committed demo run. No network calls.
export default async function ClustersPage() {
  return <ClusterList items={clusterList(await loadDemoRun())} />;
}
