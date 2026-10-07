type QueryValue = string | string[] | undefined;
type Option = { value: string };

function single(value: QueryValue) {
  return typeof value === "string" ? value : "";
}

// Reads the bookmarkable review URL. Unknown filters and malformed pages fall back to "all" and page 1.
export function parseReviewQuery(
  query: { [key: string]: QueryValue },
  options: { suggestions: Option[]; rules: Option[] },
) {
  const suggestion = single(query.suggestion);
  const rule = single(query.rule);
  const rawPage = single(query.page);
  const parsedPage = /^[1-9]\d*$/.test(rawPage) ? Number(rawPage) : 1;
  return {
    page: Number.isSafeInteger(parsedPage) ? parsedPage : 1,
    suggestion: options.suggestions.some((option) => option.value === suggestion) ? suggestion : "",
    rule: options.rules.some((option) => option.value === rule) ? rule : "",
  };
}
