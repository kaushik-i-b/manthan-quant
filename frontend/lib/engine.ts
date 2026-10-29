export function apiUrl(path: string): string {
  const configured = process.env.NEXT_PUBLIC_ENGINE_URL?.replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  if (configured) return `${configured}${suffix}`;
  return `/engine${suffix}`;
}

export function wsUrl(): string {
  const configured = process.env.NEXT_PUBLIC_ENGINE_URL?.replace(/\/$/, "");
  if (configured) return `${configured.replace(/^http/, "ws")}/api/ws`;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/engine/api/ws`;
}
