import { FIELD_LABELS, PICK_RULES, sourceLabel, tierLabel } from "@/lib/explain";
import { GOLDEN_FIELDS, type MergeLine, type Member, type Person, type Run } from "@/lib/run-loader";

// Turns a run into what the Clusters pages show. Pure, so tests check it without rendering.

/** "person:crm:C-00023" is served at /clusters/crm-C-00023 (no colons in the address). */
export const slugOf = (personId: string) => personId.replace(/^person:/, "").replace(":", "-");
export const personIdOf = (slug: string) => `person:${slug.replace("-", ":")}`;
export const clusterHref = (personId: string) => `/clusters/${slugOf(personId)}`;

export const fullName = (p: Person) =>
  [p.fields.first_name.value, p.fields.last_name.value, p.fields.suffix.value].filter(Boolean).join(" ") || "No name";

interface Index {
  people: Map<string, Person>;
  members: Map<string, Member[]>;
  lines: Map<string, MergeLine[]>;
  household: Map<string, string[]>;
}
const indexes = new WeakMap<Run, Index>();

function index(run: Run): Index {
  const hit = indexes.get(run);
  if (hit) return hit;
  const group = <T,>(items: T[], keys: (t: T) => string[]) => {
    const out = new Map<string, T[]>();
    for (const item of items) {
      for (const k of keys(item)) {
        const list = out.get(k);
        if (list) list.push(item);
        else out.set(k, [item]);
      }
    }
    return out;
  };
  const built: Index = {
    people: new Map(run.people.map((p) => [p.personId, p])),
    members: group(run.members, (m) => [m.person_id]),
    lines: group(run.mergeLog.entries, (e) => [e.a, e.b]),
    household: new Map(run.households.map((h) => [h.household_id, h.person_ids])),
  };
  indexes.set(run, built);
  return built;
}

/**
 * Which people get a page (built at build time): every person made of two or more records,
 * because only they have a merge to explain. A one-record person has nothing to explain.
 * Hard-case people are covered by the same rule when a demo run holds them.
 */
export const clusterPeople = (run: Run) => run.people.filter((p) => p.recordIds.length > 1);

export function clusterList(run: Run) {
  return clusterPeople(run).map((p) => {
    const crm = p.recordIds.filter((r) => r.startsWith("crm:")).length;
    return {
      personId: p.personId,
      href: clusterHref(p.personId),
      name: fullName(p),
      records: p.recordIds.length,
      aliases: p.aliases,
      duplicateClient: crm > 1,
    };
  });
}

export function clusterView(run: Run, personId: string) {
  const ix = index(run);
  const person = ix.people.get(personId);
  if (!person) return null;
  const seen = new Set<number>();
  const lines = person.recordIds
    .flatMap((r) => ix.lines.get(r) ?? [])
    .filter((e) => !seen.has(e.line) && seen.add(e.line))
    .sort((x, y) => x.line - y.line);
  const others = (ix.household.get(person.householdId) ?? [personId]).map((id) => {
    const p = ix.people.get(id);
    return {
      id,
      label: p ? fullName(p) : id,
      href: p && p.recordIds.length > 1 && id !== personId ? clusterHref(id) : undefined,
      current: id === personId,
    };
  });
  return {
    personId,
    name: fullName(person),
    recordIds: person.recordIds,
    aliases: person.aliases,
    golden: GOLDEN_FIELDS.map((f) => {
      const v = person.fields[f];
      return {
        field: FIELD_LABELS[f],
        value: v.value || "None",
        from: v.source ? `${sourceLabel(v.source.split(":")[0])} ${v.source}` : "None",
        where: v.sourceFile ? `${v.sourceFile}, row ${v.row}` : "",
        why: PICK_RULES[v.rule] ?? v.rule,
        tier: tierLabel(v.tier),
      };
    }),
    members: ix.members.get(personId) ?? [],
    lines,
    household: { id: person.householdId, members: others },
  };
}

export type ClusterView = NonNullable<ReturnType<typeof clusterView>>;
