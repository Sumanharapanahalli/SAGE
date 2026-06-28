import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LlmProviderForm } from "@/components/domain/LlmProviderForm";

describe("LlmProviderForm", () => {
  it("submits chosen provider + model", async () => {
    const onSubmit = vi.fn();
    render(
      <LlmProviderForm
        current={{ provider_name: "GeminiCLIProvider", model: "gemini-2.0-flash-001", available_providers: ["gemini", "ollama"] }}
        onSubmit={onSubmit}
        isPending={false}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText(/provider/i), "ollama");
    await userEvent.clear(screen.getByLabelText(/model/i));
    await userEvent.type(screen.getByLabelText(/model/i), "llama3.2");
    await userEvent.click(screen.getByRole("checkbox", { name: /save as default/i }));
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      provider: "ollama",
      model: "llama3.2",
      save_as_default: true,
    });
  });

  it("disables submit while pending", () => {
    render(
      <LlmProviderForm
        current={{ provider_name: "X", model: "m", available_providers: ["gemini"] }}
        onSubmit={() => {}}
        isPending={true}
      />,
    );
    expect(screen.getByRole("button", { name: /applying/i })).toBeDisabled();
  });
});
