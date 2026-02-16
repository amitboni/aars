import AgentDetail from "./AgentDetail";

export async function generateStaticParams() {
  return [{ id: "_" }];
}

export default function AgentDetailPage() {
  return <AgentDetail />;
}
