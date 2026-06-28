import { AgentCard } from "@/components/domain/AgentCard";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useAgents } from "@/hooks/useAgents";

export function Agents() {
  const { data, isLoading, error } = useAgents();
  if (isLoading) return <p className="text-sm text-slate-500">Loading agents…</p>;
  if (error) return <ErrorBanner error={error} />;
  if (!data || data.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
        No agents configured for this solution.
      </div>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.map((a) => (
        <AgentCard key={a.name} agent={a} />
      ))}
    </div>
  );
}
