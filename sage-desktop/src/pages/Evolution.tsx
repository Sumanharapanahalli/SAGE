import { useState } from "react";

import { Analytics } from "@/components/domain/Analytics";
import { Leaderboard } from "@/components/domain/Leaderboard";
import { RecentHistory } from "@/components/domain/RecentHistory";
import { TrainPanel } from "@/components/domain/TrainPanel";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useAnalytics,
  useHistory,
  useLeaderboard,
  useTrainAgent,
} from "@/hooks/useEvolution";

export function Evolution() {
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  const leaderboard = useLeaderboard();
  const history = useHistory(25);
  const analytics = useAnalytics(selectedRole ?? "");
  const train = useTrainAgent();

  return (
    <div className="space-y-6">
      <section>
        <header className="mb-2 flex items-baseline justify-between">
          <h2 className="text-lg font-medium">Leaderboard</h2>
          {leaderboard.data?.stats && (
            <div className="text-xs text-slate-500">
              {leaderboard.data.stats.total_agents} agents ·{" "}
              {leaderboard.data.stats.total_sessions} sessions · avg rating{" "}
              {Math.round(leaderboard.data.stats.avg_rating)}
            </div>
          )}
        </header>
        {leaderboard.isLoading && (
          <p className="text-sm text-slate-500">Loading leaderboard…</p>
        )}
        {leaderboard.error && <ErrorBanner error={leaderboard.error} />}
        {leaderboard.data && (
          <Leaderboard
            rows={leaderboard.data.leaderboard}
            selectedRole={selectedRole}
            onSelect={(r) =>
              setSelectedRole((prev) => (prev === r ? null : r))
            }
          />
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div>
          <h2 className="mb-2 text-lg font-medium">Train an agent</h2>
          <TrainPanel
            isPending={train.isPending}
            error={train.error ?? null}
            result={train.data ?? null}
            onTrain={(p) => train.mutate(p)}
          />
        </div>
        <div>
          <h2 className="mb-2 text-lg font-medium">Recent sessions</h2>
          {history.isLoading && (
            <p className="text-sm text-slate-500">Loading history…</p>
          )}
          {history.error && <ErrorBanner error={history.error} />}
          {history.data && <RecentHistory sessions={history.data.sessions} />}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Analytics</h2>
        {analytics.error && <ErrorBanner error={analytics.error} />}
        <Analytics
          data={analytics.data}
          isLoading={analytics.isLoading}
          role={selectedRole}
        />
      </section>
    </div>
  );
}
