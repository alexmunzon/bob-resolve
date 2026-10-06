// Plain-language words for the engine's codes, shared by the Clusters and Review queue pages.

/** Every rule id a queue item or a merge log line can carry, in words. Source: SPEC section 6 and CLAUDE.md. */
export const RULES: Record<string, { name: string; text: string }> = {
  "GR-001": { name: "Different suffix", text: "The generational suffixes differ (for example Jr and Sr), so the records are never merged automatically." },
  "GR-002": { name: "Shared MBI, far birth dates", text: "The records share an MBI but their birth dates are not close. A pasted MBI is a data entry mistake, not proof of identity." },
  "GR-003": { name: "Only contact details shared", text: "Only a phone number or email is shared. Family members often share these, so that alone never merges." },
  "GR-004": { name: "Ambiguous identity key", text: "The name and birth date are held by records that conflict with each other, so they cannot point to one person. One person's own records (same MBI, phone, email, or street) never count as a conflict." },
  "GR-005": { name: "First names do not match", text: "The first names do not match: they are not nicknames of each other and not a simple typo (for example Patrick and Patricia, or Andrew and Andrea, which differ only at the end)." },
  "GR-006": { name: "Birth year changed by a digit swap", text: "Two swapped digits move the birth year by more than one, and no MBI, phone, email, or street agrees to back it up." },
  "GR-007": { name: "Name and birth date only", text: "Name and birth date are the only evidence. Nothing else agrees (no MBI, phone, email, street, or linking policy), so a person decides." },
  CLUSTER_CONFLICT: { name: "Group split", text: "Automatic matches chained together records that conflict, so every link between them is held for a person to review. None was kept automatically." },
  IDENTITY_CONFLICT: { name: "Trusted sources disagree", text: "Two trusted records disagree on birth date or MBI. The engine never guesses; a person decides." },
  "SCORE-GRAY": { name: "Score in the gray zone", text: "No guard rail fired. The match score sits between the auto-reject and auto-match lines." },
  "AUTO-MATCH-HIGH": { name: "Automatic match", text: "The score is at or above the auto-match line and no guard rail fired." },
  "REVIEW-DECISION": { name: "Human decision", text: "A reviewer decided these records are the same person." },
};

export const ruleName = (id: string) => RULES[id]?.name ?? id;
export const ruleText = (id: string) => RULES[id]?.text ?? "No description recorded for this rule.";

export const SUGGESTIONS: Record<string, string> = {
  same_person: "Same person",
  different_people: "Different people",
  unsure: "Unsure",
};
export const suggestionLabel = (s: string) => SUGGESTIONS[s] ?? s;

export const TIERS: Record<string, string> = {
  rules: "Rules (automatic)",
  single: "Only one record",
  review: "Human review",
  jev: "Jev",
  llm: "LLM",
};
export const tierLabel = (t: string) => TIERS[t] || "None";

export const FIELD_LABELS: Record<string, string> = {
  first_name: "First name",
  last_name: "Last name",
  suffix: "Suffix",
  dob: "Birth date",
  mbi: "MBI (last 4 only)",
  address_line1: "Street",
  city: "City",
  state: "State",
  zip: "ZIP",
  phone: "Phone",
  email: "Email",
};

/** Why a golden field took its value. */
export const PICK_RULES: Record<string, string> = {
  authoritative_source: "Most trusted source (enrollment over CRM)",
  most_recent: "Most recent record",
  no_value: "No record has a value",
  identity_conflict: "Trusted sources disagree, left empty",
};

export const SOURCES: Record<string, string> = { crm: "CRM", enrollment: "Enrollment" };
export const sourceLabel = (s: string) => SOURCES[s] ?? s;
