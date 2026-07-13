import type { LanguageCode, LanguageMap } from "./types";

const fallbackOrder: LanguageCode[] = ["en", "nl", "de"];

export function getBrowserLanguage(supported: LanguageCode[], defaultLanguage: LanguageCode): LanguageCode {
  const candidate = navigator.language.slice(0, 2) as LanguageCode;
  return supported.includes(candidate) ? candidate : defaultLanguage;
}

export function pickLanguageValue(
  map: LanguageMap | undefined,
  language: LanguageCode
): { value: string; fallbackUsed: boolean; languageUsed?: string } {
  if (!map) {
    return { value: "", fallbackUsed: false };
  }
  if (map[language]) {
    return { value: map[language] ?? "", fallbackUsed: false, languageUsed: language };
  }
  for (const code of fallbackOrder) {
    if (map[code]) {
      return { value: map[code] ?? "", fallbackUsed: code !== language, languageUsed: code };
    }
  }
  const first = Object.entries(map).find(([, value]) => value);
  return {
    value: first?.[1] ?? "",
    fallbackUsed: Boolean(first && first[0] !== language),
    languageUsed: first?.[0]
  };
}

export function normalizeLanguage(input: string | undefined, supported: LanguageCode[], defaultLanguage: LanguageCode): LanguageCode {
  if (!input) {
    return defaultLanguage;
  }
  return supported.includes(input as LanguageCode) ? (input as LanguageCode) : defaultLanguage;
}

