import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout from "@/app/layout";

vi.mock("next/navigation", () => ({ usePathname: () => "/benchmark" }));

// jsdom cannot measure layout, so this pins the intent: on a phone the tabs wrap onto a
// second line instead of scrolling sideways, where the last tab was cut off.
function layout() {
  const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>page</RootLayout>);
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc;
}

function nav() {
  return layout().querySelector('nav[aria-label="Main"]')!;
}

describe("Main nav", () => {
  it("shows all four tabs as links", () => {
    const links = [...nav().querySelectorAll("ul a")].map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["Overview", "/"],
      ["Clusters", "/clusters"],
      ["Review queue", "/review"],
      ["Benchmark", "/benchmark"],
    ]);
  });

  it("wraps the tab row on small screens instead of scrolling it sideways", () => {
    const list = nav().querySelector("ul")!;
    expect(list.classList).toContain("flex-wrap");
    expect(list.className).not.toMatch(/overflow-x-(auto|scroll)/);
    expect(list.className).not.toMatch(/whitespace-nowrap/);
  });

  it("keeps the current-page highlight", () => {
    expect(nav().querySelector('a[aria-current="page"]')?.textContent).toBe("Benchmark");
  });
});

describe("Agency Data Trust Series navigation", () => {
  it("links all three demos and identifies the current build", () => {
    const series = layout().querySelector('nav[aria-label="Agency Data Trust Series"]')!;
    expect(series).not.toBeNull();
    expect(series.textContent).toContain("Separate demos, shared trust principles.");
    const links = [...series.querySelectorAll("a")].map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["1. Intake Kit", "https://agency-intake-kit.vercel.app"],
      ["2. Bob Resolve", "/"],
      ["3. Plan Diff", "https://plan-diff.vercel.app"],
    ]);
    expect(series.querySelector('[aria-current="true"]')?.textContent).toBe("2. Bob Resolve");
  });
});
