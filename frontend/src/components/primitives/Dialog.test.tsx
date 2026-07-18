import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./Dialog";

describe("ConfirmDialog", () => {
  it("labels guarded actions and returns focus to the trigger", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        confirmLabel="Remove member"
        description="This member will lose Project access."
        onConfirm={onConfirm}
        title="Remove Project member?"
        trigger={<button type="button">Open confirmation</button>}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Open confirmation" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(await screen.findByRole("alertdialog", { name: "Remove Project member?" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Remove member" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
