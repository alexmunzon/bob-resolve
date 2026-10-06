import { describe, expect, it } from "vitest";

import { fixed, percent } from "@/lib/format";

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

describe("fixed", () => {
  it("shows exact 0 and 1 as plain numbers", () => {
    expect(fixed(0, 3)).toBe("0.000");
    expect(fixed(1, 3)).toBe("1.000");
    expect(fixed(1, 4)).toBe("1.0000");
  });

  it("shows ordinary scores with the given decimals", () => {
    expect(fixed(0.998, 3)).toBe("0.998");
    expect(fixed(0.5, 4)).toBe("0.5000");
    expect(fixed(0.9994, 3)).toBe("0.999");
    expect(fixed(0.0005, 3)).toBe("0.001");
    expect(fixed(0.9996, 4)).toBe("0.9996");
  });

  it("never rounds a score below 1 up to 1", () => {
    expect(fixed(0.9996, 3)).toBe(">0.999");
    expect(fixed(0.99996, 3)).toBe(">0.999");
    expect(fixed(0.99996, 4)).toBe(">0.9999");
    expect(fixed(1 - Number.EPSILON, 3)).toBe(">0.999");
    expect(fixed(1 - Number.EPSILON, 4)).toBe(">0.9999");
  });

  it("never rounds a value above 0 down to 0", () => {
    expect(fixed(0.0004, 3)).toBe("<0.001");
    expect(fixed(0.00004, 4)).toBe("<0.0001");
    expect(fixed(Number.MIN_VALUE, 3)).toBe("<0.001");
  });
});
