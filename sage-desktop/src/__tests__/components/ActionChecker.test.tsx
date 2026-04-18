import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  constitutionCheckAction: vi.fn(),
}));

import * as client from "@/api/client";
import { ActionChecker } from "@/components/domain/ActionChecker";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("ActionChecker", () => {
  beforeEach(() => vi.clearAllMocks());

  it("disables the button until the textarea has content", () => {
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <ActionChecker />
      </Wrapper>,
    );
    expect(screen.getByRole("button", { name: /check/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/action description/i), {
      target: { value: "read logs" },
    });
    expect(screen.getByRole("button", { name: /check/i })).toBeEnabled();
  });

  it("shows a blocked result when the sidecar reports a violation", async () => {
    vi.mocked(client.constitutionCheckAction).mockResolvedValue({
      allowed: false,
      violations: ["Never touch /prod/"],
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <ActionChecker />
      </Wrapper>,
    );
    fireEvent.change(screen.getByLabelText(/action description/i), {
      target: { value: "rm -rf /prod/" },
    });
    fireEvent.click(screen.getByRole("button", { name: /check/i }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/blocked/i),
    );
    expect(screen.getByRole("status")).toHaveTextContent(/never touch \/prod\//i);
  });

  it("shows an allowed result when no violations are reported", async () => {
    vi.mocked(client.constitutionCheckAction).mockResolvedValue({
      allowed: true,
      violations: [],
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <ActionChecker />
      </Wrapper>,
    );
    fireEvent.change(screen.getByLabelText(/action description/i), {
      target: { value: "read staging logs" },
    });
    fireEvent.click(screen.getByRole("button", { name: /check/i }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/allowed/i),
    );
  });
});
