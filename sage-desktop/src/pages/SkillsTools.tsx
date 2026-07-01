import {
  useMcpTools,
  useReloadSkills,
  useSetSkillVisibility,
  useSkills,
} from "@/hooks/useSkills";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { toDesktopError } from "@/api/client";
import type { SkillVisibility } from "@/api/types";

const VISIBILITY_OPTIONS: SkillVisibility[] = ["public", "private", "disabled"];

/** Read-and-toggle skill registry management: browse registered skills,
 * change visibility tier inline, hot-reload from disk, and see which MCP
 * tools are available. Visibility/reload are framework control — the
 * operator's own action, not an agent proposal — so there is no approval
 * step here (matches the web API's `/skills/visibility` docstring). */
export default function SkillsTools() {
  const skills = useSkills();
  const mcpTools = useMcpTools();
  const setVisibility = useSetSkillVisibility();
  const reload = useReloadSkills();

  const listError = skills.error ? toDesktopError(skills.error) : null;
  const mcpError = mcpTools.error ? toDesktopError(mcpTools.error) : null;
  const mutationError = setVisibility.error
    ? toDesktopError(setVisibility.error)
    : reload.error
      ? toDesktopError(reload.error)
      : null;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-lg">Skills & Tools</h2>
          {skills.data && (
            <p className="text-sm text-slate-500">
              {skills.data.stats.total} skills — {skills.data.stats.public} public,{" "}
              {skills.data.stats.private} private, {skills.data.stats.disabled} disabled
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => reload.mutate()}
          disabled={reload.isPending}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {reload.isPending ? "Reloading…" : "Reload"}
        </button>
      </div>

      <ErrorBanner error={listError ?? mutationError} />

      <div className="rounded border border-sage-100 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-sage-100 text-left text-xs uppercase text-slate-500">
              <th className="p-3">Name</th>
              <th className="p-3">Description</th>
              <th className="p-3">Visibility</th>
            </tr>
          </thead>
          <tbody>
            {(skills.data?.skills ?? []).map((skill) => (
              <tr key={skill.name} className="border-b border-sage-100 last:border-0">
                <td className="p-3 font-medium">{skill.name}</td>
                <td className="p-3 text-slate-600">{skill.description || "—"}</td>
                <td className="p-3">
                  <select
                    className="rounded border border-gray-300 p-1 text-sm"
                    value={skill.visibility}
                    disabled={setVisibility.isPending}
                    onChange={(e) =>
                      setVisibility.mutate({
                        name: skill.name,
                        visibility: e.target.value,
                      })
                    }
                  >
                    {VISIBILITY_OPTIONS.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {skills.data && skills.data.skills.length === 0 && (
          <div className="p-4 text-sm text-slate-500">No skills registered.</div>
        )}
      </div>

      <div>
        <h3 className="font-semibold text-sm mb-2">MCP Tools</h3>
        <ErrorBanner error={mcpError} />
        <div className="rounded border border-sage-100 bg-white divide-y divide-sage-100">
          {(mcpTools.data?.tools ?? []).map((tool) => (
            <div key={tool.name} className="p-3 text-sm">
              <div className="font-medium">{tool.name}</div>
              <div className="text-slate-600">{tool.description || "—"}</div>
            </div>
          ))}
          {mcpTools.data && mcpTools.data.tools.length === 0 && (
            <div className="p-4 text-sm text-slate-500">No MCP tools available.</div>
          )}
        </div>
      </div>
    </div>
  );
}
