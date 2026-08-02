import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Chat from "@/pages/Chat";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    chatSend: vi.fn(),
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    deleteConversation: vi.fn(),
    clearChatHistory: vi.fn(),
  };
});

const CONV = {
  id: "c1",
  user_id: "desktop-operator",
  solution: "alpha",
  role_id: "chat",
  role_name: "Chat",
  title: "First chat",
  messages: [
    { role: "user" as const, content: "hi" },
    { role: "assistant" as const, content: "hello there" },
  ],
  created_at: "2026-07-31T00:00:00Z",
  updated_at: "2026-07-31T00:00:00Z",
};

const PROPOSAL = {
  trace_id: "tr-1",
  created_at: "2026-07-31T00:00:00Z",
  action_type: "chat_action",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "chat",
  description: "Chat action: yaml_edit — update the analyst prompt",
  payload: {},
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
  approver_role: null,
  approver_email: null,
} as never;

function renderChat() {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Chat />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Chat page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.listConversations).mockResolvedValue({ conversations: [] });
    vi.mocked(client.getConversation).mockResolvedValue({ conversation: CONV });
  });

  it("does not send on mount", () => {
    renderChat();
    expect(client.chatSend).not.toHaveBeenCalled();
  });

  it("requires a message before sending", () => {
    renderChat();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("sends the message with the current page as context", async () => {
    vi.mocked(client.chatSend).mockResolvedValue({
      conversation_id: "c1",
      reply: "hello there",
      type: "answer",
      action: null,
      proposal: null,
    });
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText(/message/i), "hi");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(client.chatSend).toHaveBeenCalledWith("hi", undefined, "/"),
    );
  });

  it("shows the conversation after a reply", async () => {
    vi.mocked(client.chatSend).mockResolvedValue({
      conversation_id: "c1",
      reply: "hello there",
      type: "answer",
      action: null,
      proposal: null,
    });
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText(/message/i), "hi");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText("hello there")).toBeInTheDocument(),
    );
  });

  it("says an action is QUEUED, never that it ran", async () => {
    // Law 1: the web API executes a chat action on confirm; desktop turns it
    // into a proposal. Claiming it ran would be false.
    vi.mocked(client.chatSend).mockResolvedValue({
      conversation_id: "c1",
      reply: "I'll update the analyst prompt",
      type: "action",
      action: "yaml_edit",
      proposal: PROPOSAL,
    });
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText(/message/i), "tweak the prompt");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/queued for approval/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/nothing has run/i)).toBeInTheDocument();
  });

  it("keeps the second message in the same conversation", async () => {
    vi.mocked(client.chatSend).mockResolvedValue({
      conversation_id: "c1",
      reply: "hello there",
      type: "answer",
      action: null,
      proposal: null,
    });
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText(/message/i), "hi");
    await user.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(client.chatSend).toHaveBeenCalledTimes(1));

    await user.type(screen.getByLabelText(/message/i), "again");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(vi.mocked(client.chatSend).mock.calls[1][1]).toBe("c1"),
    );
  });

  it("surfaces a send failure", async () => {
    vi.mocked(client.chatSend).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "LLM gateway is not configured" },
    });
    const user = userEvent.setup();
    renderChat();

    await user.type(screen.getByLabelText(/message/i), "hi");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/not configured/i),
    );
  });
});
