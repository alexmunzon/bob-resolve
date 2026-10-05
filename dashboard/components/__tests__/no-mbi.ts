import { expect } from "vitest";

// An MBI is 11 characters, letters and digits, sometimes written with dashes after the 4th and 7th.
export const MBI_SHAPES = [
  /\b[0-9A-Z]{4}-[0-9A-Z]{3}-[0-9A-Z]{4}\b/,
  /\b(?=[0-9A-Z]*\d)(?=[0-9A-Z]*[A-Z])[0-9A-Z]{11}\b/,
];

/** Checks every rendered text node: no MBI-shaped value, no en or em dash. Text nodes, not the
 *  joined page text, because adjacent table cells join into false hits ("ZIP" + "81273" + "CRM"). */
export function expectNoMbiOrDash(root: HTMLElement): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts: string[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) texts.push(n.textContent ?? "");
  for (const text of texts) {
    for (const shape of MBI_SHAPES) expect(text).not.toMatch(shape);
    expect(text).not.toMatch(/[\u2013\u2014]/);
  }
}
