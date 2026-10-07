import "./workflow.css";
import { BrokerWorkflow } from "@/components/broker-workflow";

export const metadata = { title: "Evidence workflow | bob-resolve" };
export default function WorkflowPage() {
  return <div className="page-stack"><h1>Identity evidence workflow</h1><BrokerWorkflow /></div>;
}
