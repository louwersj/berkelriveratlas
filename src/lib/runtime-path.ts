export function resolveRuntimePath(path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("#")) {
    return path;
  }
  const clean = path.replace(/^\.?\//, "").replace(/^app\//, "");
  return import.meta.env.DEV ? `/app/${clean}` : `./${clean}`;
}

