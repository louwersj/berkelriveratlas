import { getBrowserLanguage, normalizeLanguage } from "./i18n";
import type { LanguageCode, RouteState } from "./types";

export function parseRoute(hash: string, supported: LanguageCode[], defaultLanguage: LanguageCode): RouteState {
  const clean = hash.replace(/^#\/?/, "");
  if (!clean) {
    return {
      language: getBrowserLanguage(supported, defaultLanguage),
      view: "explore"
    };
  }

  const [languagePart, viewPart, ...rest] = clean.split("/");
  const language = normalizeLanguage(languagePart, supported, defaultLanguage);

  if (viewPart === "object") {
    return { language, view: "object", id: rest.join("/") || undefined };
  }

  if (viewPart === "page") {
    return { language, view: "page", id: rest.join("/") || undefined };
  }

  if (viewPart === "graph") {
    return { language, view: "graph" };
  }

  if (viewPart === "sources") {
    return { language, view: "sources" };
  }

  return { language, view: "explore" };
}

export function buildRoute(route: RouteState): string {
  if (route.view === "explore") {
    return `#/${route.language}/explore`;
  }
  if (route.id) {
    return `#/${route.language}/${route.view}/${route.id}`;
  }
  return `#/${route.language}/${route.view}`;
}

