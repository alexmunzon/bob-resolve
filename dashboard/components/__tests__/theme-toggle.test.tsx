import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/theme-toggle";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.classList.remove("dark");
  localStorage.clear();
});

describe("Sidebar theme control", () => {
  it("keeps focus and saves both choices after repeated toggles", async () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Dark mode" });
    button.focus();
    for (let i = 0; i < 2; i++) {
      fireEvent.click(button);
      await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "true"));
      expect(document.documentElement).toHaveClass("dark");
      expect(localStorage.getItem("theme")).toBe("dark");
      expect(button).toHaveFocus();
      fireEvent.click(button);
      await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "false"));
      expect(document.documentElement).not.toHaveClass("dark");
      expect(localStorage.getItem("theme")).toBe("light");
    }
  });

  it("reflects the restored theme and still works with storage blocked", async () => {
    document.documentElement.classList.add("dark");
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage blocked"); });
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Dark mode" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(button);
    await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "false"));
    expect(document.documentElement).not.toHaveClass("dark");
  });
});
