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

/**
 * A 0 to 1 value, such as a match score, with a fixed number of decimals, e.g. 0.998 at 3 is "0.998".
 * Rounding never hides a gap: a value just under 1 shows ">0.999" (only exactly 1 is "1.000"),
 * and a value just over 0 shows "<0.001" (only exactly 0 is "0.000").
 */
export function fixed(value: number, digits: number): string {
  const text = value.toFixed(digits);
  const step = 10 ** -digits;
  if (value < 1 && text === (1).toFixed(digits)) return `>${(1 - step).toFixed(digits)}`;
  if (value > 0 && text === (0).toFixed(digits)) return `<${step.toFixed(digits)}`;
  return text;
}

/** Engine costs are US dollars as JSON numbers (0.0 while Jev and the LLM are off). */
export function formatUsd(amount: number): string {
  if (!Number.isFinite(amount) || amount < 0) throw new Error(`Not a cost: ${amount}`);
  return `$${amount.toFixed(2)}`;
}
