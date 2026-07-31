import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  chatSend,
  clearChatHistory,
  deleteConversation,
  getConversation,
  listConversations,
} from "@/api/client";
import type {
  ChatClearResult,
  ChatConversationResult,
  ChatConversationsResult,
  ChatDeleteResult,
  ChatSendResult,
  DesktopError,
} from "@/api/types";
import { approvalsKey } from "@/hooks/useApprovals";

export const conversationsKey = ["conversations"] as const;
export const conversationKey = (id: string) => ["conversation", id] as const;

export function useConversations() {
  return useQuery<ChatConversationsResult, DesktopError>({
    queryKey: conversationsKey,
    queryFn: () => listConversations(),
  });
}

export function useConversation(id: string | null) {
  return useQuery<ChatConversationResult, DesktopError>({
    queryKey: conversationKey(id ?? ""),
    queryFn: () => getConversation(id as string),
    enabled: Boolean(id),
  });
}

interface SendVars {
  message: string;
  conversation_id?: string;
  page_context?: string;
}

/**
 * Send a message.
 *
 * A reply that is an ACTION comes back with a pending proposal, so the
 * approvals cache is invalidated too — the badge must move the moment chat
 * queues something for the operator to decide.
 */
export function useChatSend() {
  const qc = useQueryClient();
  return useMutation<ChatSendResult, DesktopError, SendVars>({
    mutationFn: (v) => chatSend(v.message, v.conversation_id, v.page_context),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: conversationsKey });
      qc.invalidateQueries({ queryKey: conversationKey(result.conversation_id) });
      if (result.proposal) {
        qc.invalidateQueries({ queryKey: approvalsKey });
      }
    },
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation<ChatDeleteResult, DesktopError, string>({
    mutationFn: (id) => deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });
}

export function useClearChatHistory() {
  const qc = useQueryClient();
  return useMutation<ChatClearResult, DesktopError, void>({
    mutationFn: () => clearChatHistory(),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });
}
