import { resolveRuntimePath } from "./runtime-path";

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(resolveRuntimePath(url));
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status}`);
  }
  return (await response.json()) as T;
}
