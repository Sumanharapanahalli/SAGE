import { useState } from "react";
import { useLocation } from "react-router-dom";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useChatSend,
  useConversation,
  useConversations,
  useDeleteConversation,
} from "@/hooks/useChat";

/**
 * Conversational agent over the solution.
 *
 * A reply of type "action" is NOT executed. The sidecar turns it into a
 * pending proposal and the operator decides in the Approvals inbox — the web
 * API instead runs the action directly on a confirm button here. So the banner
 * below says the action is queued, never that it ran.
 */
export default function Chat() {
  const location = useLocation();
  const conversations = useConversations();
  const send = useChatSend();
  const remove = useDeleteConversation();

  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const active = useConversation(activeId);
  const messages = active.data?.conversation.messages ?? [];

  const submit = () => {
    send.mutate(
      {
        message: draft,
        conversation_id: activeId ?? undefined,
        // Lets the router answer "what am I looking at?" usefully.
        page_context: location.pathname,
      },
      {
        onSuccess: (result) => {
          setActiveId(result.conversation_id);
          setDraft("");
        },
      },
    );
  };

  return (
    <div className="flex h-full gap-4 p-6">
      <aside className="w-56 shrink-0 space-y-2">
        <button
          className="w-full rounded border border-sage-200 px-3 py-2 text-sm text-sage-700 hover:bg-sage-50"
          onClick={() => setActiveId(null)}
        >
          New conversation
        </button>
        {conversations.isLoading && (
          <p className="text-sm text-slate-500">Loading…</p>
        )}
        <ul className="space-y-1">
          {(conversations.data?.conversations ?? []).map((c) => (
            <li key={c.id} className="flex items-center gap-1">
              <button
                className={
                  activeId === c.id
                    ? "flex-1 truncate rounded bg-sage-500 px-2 py-1 text-left text-xs text-white"
                    : "flex-1 truncate rounded px-2 py-1 text-left text-xs text-sage-900 hover:bg-sage-100"
                }
                onClick={() => setActiveId(c.id)}
              >
                {c.title || "Untitled"}
              </button>
              <button
                aria-label={`Delete ${c.title || "conversation"}`}
                className="px-1 text-xs text-red-700 hover:underline"
                onClick={() => {
                  remove.mutate(c.id);
                  if (activeId === c.id) setActiveId(null);
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col gap-3">
        <ErrorBanner error={conversations.error} />
        <ErrorBanner error={send.error} />

        <div className="flex-1 space-y-3 overflow-y-auto">
          {messages.length === 0 && !send.isPending && (
            <p className="text-sm text-slate-500">
              Ask about this solution — its agents, proposals, or config.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-lg rounded bg-sage-500 px-3 py-2 text-sm text-white"
                  : "mr-auto max-w-lg rounded bg-sage-50 px-3 py-2 text-sm text-sage-900"
              }
            >
              {m.content}
            </div>
          ))}
          {send.isPending && (
            <p className="text-sm text-slate-500">Thinking…</p>
          )}
        </div>

        {send.data?.proposal && (
          <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="font-semibold">Action queued for approval</div>
            <div className="mt-1 text-xs">
              {send.data.proposal.description}. Nothing has run — decide on it
              in the Approvals inbox.
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <label className="sr-only" htmlFor="chat-message">
            Message
          </label>
          <input
            id="chat-message"
            className="flex-1 rounded border border-sage-200 px-3 py-2 text-sm focus:border-sage-400 focus:outline-none"
            value={draft}
            placeholder="Ask something…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft.trim() && !send.isPending) submit();
            }}
          />
          <button
            className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
            disabled={send.isPending || !draft.trim()}
            onClick={submit}
          >
            Send
          </button>
        </div>
      </section>
    </div>
  );
}
