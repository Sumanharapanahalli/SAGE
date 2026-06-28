import { useState } from "react";

import type {
  DesktopError,
  HitlLevel,
  StartBuildParams,
} from "@/api/types";

const MIN_DESC = 30;

interface Props {
  isPending: boolean;
  error: DesktopError | null;
  onStart: (p: Required<StartBuildParams>) => void;
}

function errorMessage(error: DesktopError): string {
  if (error.kind === "InvalidParams" || error.kind === "SidecarDown") {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Build start failed (${error.kind}).`;
}

export function StartBuildForm({ isPending, error, onStart }: Props) {
  const [description, setDescription] = useState("");
  const [solutionName, setSolutionName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [workspaceDir, setWorkspaceDir] = useState("");
  const [criticThreshold, setCriticThreshold] = useState("70");
  const [hitlLevel, setHitlLevel] = useState<HitlLevel>("standard");

  const trimmedDesc = description.trim();
  const descOk = trimmedDesc.length >= MIN_DESC;
  const canSubmit = descOk && !isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const threshold = Number.parseInt(criticThreshold, 10);
        onStart({
          product_description: trimmedDesc,
          solution_name: solutionName.trim(),
          repo_url: repoUrl.trim(),
          workspace_dir: workspaceDir.trim(),
          critic_threshold: Number.isFinite(threshold) ? threshold : 70,
          hitl_level: hitlLevel,
        });
      }}
    >
      <label className="block">
        <span className="block text-sm font-medium">Product description</span>
        <textarea
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          rows={4}
          placeholder="What should the orchestrator build? Be specific about features and users."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <span className="text-xs text-gray-500">
          {trimmedDesc.length}/{MIN_DESC} chars minimum
        </span>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-sm font-medium">
            Solution name (optional)
          </span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono"
            placeholder="yoga"
            value={solutionName}
            onChange={(e) => setSolutionName(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">HITL level</span>
          <select
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={hitlLevel}
            onChange={(e) => setHitlLevel(e.target.value as HitlLevel)}
          >
            <option value="permissive">permissive</option>
            <option value="standard">standard</option>
            <option value="strict">strict</option>
          </select>
        </label>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-sm font-medium">Repo URL (optional)</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="https://github.com/…"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">
            Workspace dir (optional)
          </span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono"
            placeholder="/abs/path/to/workspace"
            value={workspaceDir}
            onChange={(e) => setWorkspaceDir(e.target.value)}
          />
        </label>
      </div>
      <label className="block">
        <span className="block text-sm font-medium">Critic threshold (0–100)</span>
        <input
          type="number"
          min={0}
          max={100}
          className="mt-1 block w-24 rounded border border-gray-300 p-2"
          value={criticThreshold}
          onChange={(e) => setCriticThreshold(e.target.value)}
        />
      </label>
      {error && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {errorMessage(error)}
        </div>
      )}
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-sage-600 px-4 py-2 text-white hover:bg-sage-700 disabled:opacity-50"
      >
        {isPending ? "Starting…" : "Start build"}
      </button>
    </form>
  );
}
