import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "./page";

describe("Home", () => {
  it("shows the placeholder heading", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { level: 1, name: "bob-resolve: nothing to show yet" }),
    ).toBeInTheDocument();
  });
});
