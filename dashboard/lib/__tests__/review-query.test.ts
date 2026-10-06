import { describe, expect, it } from "vitest";

import { parseReviewQuery } from "@/lib/review-query";

const options = {
  suggestions: [{ value: "different_people", label: "Different people" }, { value: "unsure", label: "Unsure" }],
  rules: [{ value: "GR-005", label: "GR-005" }, { value: "GR-007", label: "GR-007" }],
};

describe("parseReviewQuery", () => {
  it("keeps a valid page and known filters", () => {
    expect(parseReviewQuery({ page: "3", suggestion: "unsure", rule: "GR-007" }, options)).toEqual({
      page: 3,
      suggestion: "unsure",
      rule: "GR-007",
    });
  });

  it("falls back to page one for missing, zero, negative, padded, non-numeric or unsafe pages", () => {
    for (const page of [undefined, "", "0", "-1", "007", "abc", "2.5", "999999999999999999999"]) {
      expect(parseReviewQuery({ page }, options).page).toBe(1);
    }
  });

  it("ignores unknown or repeated filter values", () => {
    expect(parseReviewQuery({ suggestion: "same_person", rule: "<script>" }, options)).toEqual({ page: 1, suggestion: "", rule: "" });
    expect(parseReviewQuery({ suggestion: ["unsure", "unsure"], rule: ["GR-005"], page: ["2"] }, options)).toEqual({
      page: 1,
      suggestion: "",
      rule: "",
    });
  });

  it("passes a page past the end through; the queue clamps it to the last page", () => {
    expect(parseReviewQuery({ page: "99" }, options).page).toBe(99);
  });
});
