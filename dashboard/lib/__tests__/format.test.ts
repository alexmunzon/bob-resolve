import { describe, expect, it } from "vitest";

import { percent } from "@/lib/format";

describe("percent", () => {
  it("shows exact 0 and 1 as 0.0% and 100.0%", () => {
    expect(percent(0)).toBe("0.0%");
    expect(percent(1)).toBe("100.0%");
  });

  it("shows ordinary rates with one decimal", () => {
    expect(percent(0.9)).toBe("90.0%");
    expect(percent(0.996308)).toBe("99.6%");
    expect(percent(0.9994)).toBe("99.9%");
    expect(percent(0.0005)).toBe("0.1%");
    expect(percent(0.5)).toBe("50.0%");
  });

  it("never rounds a rate below 1 up to 100.0%", () => {
    expect(percent(0.9996)).toBe(">99.9%");
    expect(percent(0.99999)).toBe(">99.9%");
    expect(percent(1 - Number.EPSILON)).toBe(">99.9%");
  });

  it("never rounds a rate above 0 down to 0.0%", () => {
    expect(percent(0.0004)).toBe("<0.1%");
    expect(percent(0.00001)).toBe("<0.1%");
    expect(percent(Number.MIN_VALUE)).toBe("<0.1%");
  });
});
