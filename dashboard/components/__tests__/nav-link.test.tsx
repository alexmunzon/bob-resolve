import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NavLink } from "@/components/nav-link";

vi.mock("next/navigation", () => ({ usePathname: () => "/clusters/crm-C-00023" }));

describe("NavLink", () => {
  it("marks the section you are in as the current page, and every item is a link", () => {
    render(
      <>
        <NavLink href="/" label="Overview" />
        <NavLink href="/clusters" label="Clusters" />
        <NavLink href="/review" label="Review queue" />
      </>,
    );
    expect(screen.getByRole("link", { name: "Clusters" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Review queue" })).toHaveAttribute("href", "/review");
    expect(screen.queryByText(/coming soon/)).not.toBeInTheDocument();
  });
});
