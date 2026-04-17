import { useState } from "react";
import {
  useFeatureRequests,
  useSubmitFeatureRequest,
  useUpdateFeatureRequest,
} from "@/hooks/useBacklog";
import { FeatureRequestRow } from "@/components/domain/FeatureRequestRow";
import type { FeatureRequestAction, FeatureRequestScope } from "@/api/types";

export default function Backlog() {
  const [scope, setScope] = useState<FeatureRequestScope>("solution");
  const list = useFeatureRequests({ scope });
  const submit = useSubmitFeatureRequest();
  const update = useUpdateFeatureRequest();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const handleAction = (id: string, action: FeatureRequestAction) => {
    update.mutate({ id, action });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    submit.mutate(
      { title, description, scope },
      {
        onSuccess: () => {
          setTitle("");
          setDescription("");
        },
      },
    );
  };

  return (
    <div className="p-6">
      <div className="mb-4 flex gap-2">
        {(["solution", "sage"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`rounded px-3 py-1 text-sm ${
              scope === s ? "bg-sage-600 text-white" : "bg-gray-100"
            }`}
          >
            {s === "solution" ? "Solution backlog" : "SAGE framework"}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="mb-6 space-y-3 rounded border border-gray-200 p-4">
        <h2 className="font-semibold">Submit request</h2>
        <label className="block">
          <span className="block text-sm font-medium">Title</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Description</span>
          <textarea
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <button
          type="submit"
          disabled={submit.isPending}
          className="rounded bg-sage-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {submit.isPending ? "Submitting…" : "Submit"}
        </button>
      </form>

      <div className="space-y-3">
        {list.isLoading && <p>Loading…</p>}
        {list.isSuccess && list.data.length === 0 && (
          <p className="text-sm text-gray-500">No feature requests.</p>
        )}
        {list.data?.map((fr) => (
          <FeatureRequestRow
            key={fr.id}
            item={fr}
            onAction={handleAction}
            isPending={update.isPending}
          />
        ))}
      </div>
    </div>
  );
}
