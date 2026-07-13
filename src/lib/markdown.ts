import { load as parseYaml } from "js-yaml";
import { marked } from "marked";
import type { LanguageCode, ParsedMarkdownDocument } from "./types";
import { resolveRuntimePath } from "./runtime-path";

const languageSectionPattern = /^##\s+(en|de|nl)\s*$/gm;

export async function fetchAndParseMarkdown(url: string): Promise<ParsedMarkdownDocument> {
  const response = await fetch(resolveRuntimePath(url));
  if (!response.ok) {
    throw new Error(`Failed to fetch Markdown: ${url}`);
  }
  const raw = await response.text();
  return parseMarkdownDocument(raw);
}

export function parseMarkdownDocument(raw: string): ParsedMarkdownDocument {
  const frontMatterMatch = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!frontMatterMatch) {
    return { frontMatter: {}, bodyByLanguage: { en: raw } };
  }
  const [, frontMatterRaw, bodyRaw] = frontMatterMatch;
  const frontMatter = (parseYaml(frontMatterRaw) as Record<string, unknown>) ?? {};
  const bodyByLanguage = splitBodyByLanguage(bodyRaw);
  return { frontMatter, bodyByLanguage };
}

function splitBodyByLanguage(body: string): Partial<Record<LanguageCode, string>> {
  const matches = [...body.matchAll(languageSectionPattern)];
  if (matches.length === 0) {
    return { en: body.trim() };
  }

  const output: Partial<Record<LanguageCode, string>> = {};
  for (let index = 0; index < matches.length; index += 1) {
    const match = matches[index];
    const language = match[1] as LanguageCode;
    const start = (match.index ?? 0) + match[0].length;
    const end = index + 1 < matches.length ? matches[index + 1].index ?? body.length : body.length;
    output[language] = body.slice(start, end).trim();
  }
  return output;
}

export function renderMarkdown(markdown: string): string {
  return marked.parse(markdown) as string;
}
