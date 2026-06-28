import { useEffect, useState } from "react";

import type { DesktopError, YamlFileName } from "@/api/types";
import { useReadYaml, useWriteYaml } from "@/hooks/useYamlEdit";

const FILES: { value: YamlFileName; label: string }[] = [
  { value: "project", label: "project.yaml" },
  { value: "prompts", label: "prompts.yaml" },
  { value: "tasks", label: "tasks.yaml" },
];

function errorMessage(error: DesktopError): string {
  if (error.kind === "InvalidParams" || error.kind === "SidecarDown") {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Failed (${error.kind}).`;
}

export default function YamlEdit() {
  const [file, setFile] = useState<YamlFileName>("project");
  const [draft, setDraft] = useState<string>("");
  const [saved, setSaved] = useState<boolean>(false);

  const read = useReadYaml(file);
  const write = useWriteYaml();

  const loadedContent = read.data?.content;
  useEffect(() => {
    if (loadedContent !== undefined) {
      setDraft(loadedContent);
      setSaved(false);
    }
  }, [loadedContent, file]);

  const dirty = read.data ? draft !== read.data.content : false;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <div>
        <h2 className="text-lg font-semibold">Edit YAML</h2>
        <p className="text-sm text-gray-600">
          Read and overwrite the active solution's YAML triad. YAML syntax
          is validated on the sidecar before the file is touched.
        </p>
      </div>

      <div className="flex items-baseline gap-2">
        <label htmlFor="yaml-file" className="text-sm font-medium">
          File
        </label>
        <select
          id="yaml-file"
          className="rounded border border-gray-300 p-2 font-mono text-sm"
          value={file}
          onChange={(e) => setFile(e.target.value as YamlFileName)}
        >
          {FILES.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        {read.data?.path && (
          <span className="ml-auto font-mono text-xs text-slate-500">
            {read.data.path}
          </span>
        )}
      </div>

      {read.isError && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          Could not load {file}.yaml: {errorMessage(read.error!)}
        </div>
      )}

      <label className="block">
        <span className="sr-only">Editor</span>
        <textarea
          aria-label="editor"
          className="block h-96 w-full rounded border border-gray-300 p-3 font-mono text-xs"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setSaved(false);
          }}
          spellCheck={false}
        />
      </label>

      {write.error && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {errorMessage(write.error)}
        </div>
      )}

      {saved && !dirty && (
        <div
          role="status"
          className="rounded border border-green-200 bg-green-50 p-2 text-xs text-green-900"
        >
          Saved {file}.yaml ({write.data?.bytes ?? "?"} bytes).
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          disabled={!dirty || write.isPending}
          className="rounded bg-sage-600 px-4 py-2 text-sm text-white hover:bg-sage-700 disabled:opacity-50"
          onClick={() =>
            write.mutate(
              { file, content: draft },
              { onSuccess: () => setSaved(true) },
            )
          }
        >
          {write.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          disabled={!dirty}
          className="rounded border border-gray-300 px-4 py-2 text-sm disabled:opacity-50"
          onClick={() => {
            if (read.data) setDraft(read.data.content);
            setSaved(false);
          }}
        >
          Revert
        </button>
      </div>
    </div>
  );
}
