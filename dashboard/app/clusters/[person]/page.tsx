import { notFound } from "next/navigation";

import { Cluster } from "@/components/cluster";
import { clusterPeople, clusterView, personIdOf, slugOf } from "@/lib/clusters";
import { loadDemoRun } from "@/lib/run-dir";

// One static page per person made of two or more records (the rule lives in lib/clusters.ts).
// Any other address is a 404, never rendered on request.
export const dynamicParams = false;

export async function generateStaticParams() {
  return clusterPeople(await loadDemoRun()).map((p) => ({ person: slugOf(p.personId) }));
}

export async function generateMetadata({ params }: PageProps<"/clusters/[person]">) {
  return { title: `${(await params).person} | Clusters | Bob Resolve` };
}

export default async function ClusterPage({ params }: PageProps<"/clusters/[person]">) {
  const view = clusterView(await loadDemoRun(), personIdOf((await params).person));
  if (!view) notFound();
  return <Cluster view={view} />;
}
