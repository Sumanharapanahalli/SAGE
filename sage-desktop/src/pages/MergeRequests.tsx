import { useState } from "react";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useCommentOnMr,
  useMrConfig,
  useOpenMrs,
  useProposeMr,
  useReviewMr,
} from "@/hooks/useMr";

/**
 * GitLab merge requests, via the DeveloperAgent.
 *
 * Distinct from SAGE's own Merge-Gate — these act on a real GitLab instance,
 * addressed by numeric project/MR IDs.
 *
 * Creating an MR is PROPOSED, not done: the web endpoint opens it immediately
 * from an LLM-drafted title and description, which is an irreversible write to
 * a shared external system with no human in the loop. Here it files an
 * EXTERNAL proposal and only the approved executor POSTs — so the copy says
 * "queued for approval", never "created".
 */
export default function MergeRequests() {
  const config = useMrConfig();
  const [projectId, setProjectId] = useState<number | null>(null);
  const [projectInput, setProjectInput] = useState("");
  const [issueIid, setIssueIid] = useState("");
  const [commentText, setCommentText] = useState("");
  const [activeMr, setActiveMr] = useState<number | null>(null);

  const mrs = useOpenMrs(projectId);
  const review = useReviewMr();
  const propose = useProposeMr();
  const comment = useCommentOnMr();

  if (config.data && !config.data.configured) {
    return (
      <div className="space-y-3 p-6">
        <div
          role="alert"
          className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          <div className="font-semibold">GitLab is not configured</div>
          <div className="mt-1 text-xs">{config.data.message}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-6">
      <ErrorBanner error={config.error} />
      <ErrorBanner error={mrs.error} />
      <ErrorBanner error={review.error} />
      <ErrorBanner error={propose.error} />
      <ErrorBanner error={comment.error} />

      <div className="flex items-end gap-2">
        <label className="text-xs text-sage-700">
          GitLab project ID
          <input
            className="mt-1 block rounded border border-sage-200 px-2 py-1 text-sm"
            value={projectInput}
            onChange={(e) => setProjectInput(e.target.value)}
          />
        </label>
        <button
          className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
          disabled={!/^\d+$/.test(projectInput.trim())}
          onClick={() => setProjectId(Number(projectInput.trim()))}
        >
          Load open MRs
        </button>
      </div>

      {mrs.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {mrs.data && (
        <ul className="space-y-2">
          {mrs.data.merge_requests.length === 0 && (
            <li className="text-sm text-slate-500">No open merge requests.</li>
          )}
          {mrs.data.merge_requests.map((m, i) => {
            const iid = Number(m.iid);
            return (
              <li
                key={i}
                className="rounded border border-sage-100 bg-white p-3 text-sm"
              >
                <div className="font-medium text-sage-900">
                  !{String(m.iid)} {String(m.title ?? "")}
                </div>
                <div className="mt-2 flex gap-2">
                  <button
                    className="rounded border border-sage-200 px-2 py-1 text-xs text-sage-700 hover:bg-sage-50"
                    onClick={() =>
                      review.mutate({
                        project_id: projectId as number,
                        mr_iid: iid,
                      })
                    }
                  >
                    Review
                  </button>
                  <button
                    className="rounded border border-sage-200 px-2 py-1 text-xs text-sage-700 hover:bg-sage-50"
                    onClick={() => setActiveMr(activeMr === iid ? null : iid)}
                  >
                    Comment
                  </button>
                </div>

                {activeMr === iid && (
                  <div className="mt-2 flex gap-2">
                    <label className="sr-only" htmlFor={`c-${iid}`}>
                      Comment
                    </label>
                    <input
                      id={`c-${iid}`}
                      className="flex-1 rounded border border-sage-200 px-2 py-1 text-xs"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                    />
                    <button
                      className="rounded bg-sage-500 px-3 py-1 text-xs text-white disabled:opacity-50"
                      disabled={!commentText.trim() || comment.isPending}
                      onClick={() =>
                        comment.mutate(
                          {
                            project_id: projectId as number,
                            mr_iid: iid,
                            comment: commentText,
                          },
                          { onSuccess: () => setCommentText("") },
                        )
                      }
                    >
                      Post
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {review.data && (
        <div className="rounded border border-sage-100 bg-sage-50 px-4 py-3 text-sm">
          Review started as job{" "}
          <span className="font-mono text-xs">{review.data.job_id}</span> — it
          runs in the background.
        </div>
      )}

      <div className="rounded border border-sage-100 bg-white p-4">
        <div className="mb-2 text-sm font-medium text-sage-900">
          Create an MR from an issue
        </div>
        <div className="flex items-end gap-2">
          <label className="text-xs text-sage-700">
            Issue IID
            <input
              className="mt-1 block rounded border border-sage-200 px-2 py-1 text-sm"
              value={issueIid}
              onChange={(e) => setIssueIid(e.target.value)}
            />
          </label>
          <button
            className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
            disabled={
              propose.isPending ||
              projectId === null ||
              !/^\d+$/.test(issueIid.trim())
            }
            onClick={() =>
              propose.mutate({
                project_id: projectId as number,
                issue_iid: Number(issueIid.trim()),
              })
            }
          >
            Propose MR
          </button>
        </div>

        {propose.data && (
          <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="font-semibold">Queued for approval</div>
            <div className="mt-1 text-xs">
              {propose.data.description}. Nothing has been created in GitLab —
              the merge request is opened only once the proposal is approved.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
