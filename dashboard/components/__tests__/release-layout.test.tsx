import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout from "@/app/layout";

vi.mock("next/navigation", () => ({ usePathname: () => "/review" }));

describe("Release navigation", () => {
  it("links only delivered local pages and preserves keyboard access", () => {
    const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>page</RootLayout>);
    const doc = new DOMParser().parseFromString(html, "text/html");
    const links = [...doc.querySelectorAll('nav[aria-label="Main"] a')];
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      const href = link.getAttribute("href")!;
      expect(existsSync(resolve(import.meta.dirname, `../../app${href}/page.tsx`))).toBe(true);
    }
    expect(doc.querySelector('nav[aria-label="Main"] a[aria-current="page"]')?.getAttribute("href")).toBe("/review");
    expect(doc.querySelector('nav[aria-label="Main"] a[href="/workflow"]')?.textContent).toBe("Evidence workflow");
    expect(doc.querySelector('a[href="#main-content"]')).not.toBeNull();
    expect(doc.querySelector("main")?.getAttribute("tabindex")).toBe("-1");
  });

  it("distinguishes deterministic matching and browser review from evidenced human approval", () => {
    const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>page</RootLayout>);
    const doc = new DOMParser().parseFromString(html, "text/html");
    const scope = doc.querySelector('[aria-label="Review scope"]');
    expect(scope?.textContent).toContain("A deterministic match does not confirm a person");
    expect(scope?.textContent).toContain("Browser review labels are not authenticated approval");
    expect(scope?.textContent).toContain("real agency data and production access remain separate gates");
  });
});
