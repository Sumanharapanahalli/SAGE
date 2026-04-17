import { useState } from "react";

import type { DesktopError, TrainParams, TrainResult } from "@/api/types";

interface Props {
  isPending: boolean;
  error: DesktopError | null;
  result: TrainResult | null;
  onTrain: (p: TrainParams) => void;
}

function errorMessage(error: DesktopError): string {
  if (
    error.kind === "InvalidParams" ||
    error.kind === "SidecarDown" ||
    error.kind === "InvalidRequest"
  ) {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Training failed (${error.kind}).`;
}

export function TrainPanel({ isPending, error, result, onTrain }: Props) {
  const [role, setRole] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [skillName, setSkillName] = useState("");
  const [exerciseId, setExerciseId] = useState("");

  const trimmedRole = role.trim();
  const canSubmit = trimmedRole.length > 0 && !isPending;

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        const params: TrainParams = { role: trimmedRole };
        if (difficulty.trim()) params.difficulty = difficulty.trim();
        if (skillName.trim()) params.skill_name = skillName.trim();
        if (exerciseId.trim()) params.exercise_id = exerciseId.trim();
        onTrain(params);
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-sm font-medium">Agent role *</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono"
            placeholder="developer"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">
            Difficulty (optional)
          </span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="easy | medium | hard"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">
            Skill name (optional)
          </span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="python_debug"
            value={skillName}
            onChange={(e) => setSkillName(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">
            Exercise id (optional)
          </span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono"
            placeholder="ex_001"
            value={exerciseId}
            onChange={(e) => setExerciseId(e.target.value)}
          />
        </label>
      </div>
      {error && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {errorMessage(error)}
        </div>
      )}
      {result && (
        <div className="rounded border border-sage-200 bg-sage-50 p-3 text-sm">
          <div className="font-medium">
            Session {result.session_id} — {result.status}
          </div>
          {result.grade && (
            <div>
              Grade: {result.grade.score.toFixed(1)}{" "}
              ({result.grade.passed ? "passed" : "failed"})
            </div>
          )}
          {typeof result.elo_before === "number" &&
            typeof result.elo_after === "number" && (
              <div>
                Elo: {result.elo_before.toFixed(1)} →{" "}
                {result.elo_after.toFixed(1)}
              </div>
            )}
        </div>
      )}
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-sage-600 px-4 py-2 text-white hover:bg-sage-700 disabled:opacity-50"
      >
        {isPending ? "Training…" : "Run training round"}
      </button>
    </form>
  );
}
