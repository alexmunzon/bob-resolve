// Display formatting. A fixed locale, so the server and the browser print the same text.
const COUNT = new Intl.NumberFormat("en-US");

export const count = (n: number): string => COUNT.format(n);

export const plural = (n: number, word: string): string => `${count(n)} ${word}${n === 1 ? "" : "s"}`;

/**
 * A 0 to 1 rate as a percent with one decimal, e.g. 0.9 is "90.0%".
 * Rounding never hides a gap: a rate just under 1 shows ">99.9%" (only exactly 1 is "100.0%"),
 * and a rate just over 0 shows "<0.1%" (only exactly 0 is "0.0%").
 */
export function percent(rate: number): string {
  const text = (rate * 100).toFixed(1);
  if (rate < 1 && text === "100.0") return ">99.9%";
  if (rate > 0 && text === "0.0") return "<0.1%";
  return `${text}%`;
}

/** Engine costs are US dollars as JSON numbers (0.0 while Jev and the LLM are off). */
export function formatUsd(amount: number): string {
  if (!Number.isFinite(amount) || amount < 0) throw new Error(`Not a cost: ${amount}`);
  return `$${amount.toFixed(2)}`;
}
