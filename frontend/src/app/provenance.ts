import type { MetadataEntry } from "../api";

function formatMetadataValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function humanizeFieldName(key: string): string {
  const words = key
    .replace(/[._]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  return words.join(" ") || key;
}

function capitalize(sentence: string): string {
  return sentence.length ? sentence.charAt(0).toUpperCase() + sentence.slice(1) : sentence;
}

export function describeMetadataEntry(entry: Pick<MetadataEntry, "key" | "value" | "source">): string {
  return capitalize(
    `${humanizeFieldName(entry.key)} is ${formatMetadataValue(entry.value)}, set by ${entry.source}.`,
  );
}

export function describeProvenanceMetadata(metadata: Record<string, unknown>): string | null {
  const entries = Object.entries(metadata);
  if (entries.length === 0) {
    return null;
  }
  const clauses = entries.map(
    ([key, value]) => `${humanizeFieldName(key)} is ${formatMetadataValue(value)}`,
  );
  return capitalize(`${clauses.join("; ")}.`);
}
