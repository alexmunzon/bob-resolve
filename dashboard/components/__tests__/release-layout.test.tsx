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

  it("uses one concise review notice and puts theme controls after the series links", () => {
    const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>page</RootLayout>);
    const doc = new DOMParser().parseFromString(html, "text/html");
    expect(doc.querySelector('[aria-label="Review scope"]')?.textContent?.trim()).toBe("Synthetic demo · human review required");
    expect(doc.querySelectorAll('[aria-label="Review scope"]')).toHaveLength(1);
    expect(doc.querySelector(".sidebar-note")).toBeNull();
    expect(doc.querySelector(".brand-name")?.textContent).toMatch(/^Bob Resolve /);
    const footer = doc.querySelector(".sidebar-footer")!;
    expect(footer.querySelector('nav[aria-label="Agency Data Trust Series"]')).not.toBeNull();
    expect(footer.lastElementChild?.querySelector(".theme-toggle")).not.toBeNull();
    expect(doc.querySelector('nav[aria-label="Main"] a[href="/workflow"] svg')).not.toBeNull();
  });
});
