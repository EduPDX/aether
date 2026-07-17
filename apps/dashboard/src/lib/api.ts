/** Typed client for the Aether Core v1 API. */

export type InstanceState = "stopped" | "starting" | "running" | "stopping" | "crashed";

export interface Instance {
  id: string;
  name: string;
  provider_id: string;
  root_dir: string;
  content_dirs: Record<string, string>;
  provider_data: Record<string, unknown>;
  created_at: string;
  state: InstanceState;
}

export interface ContentDependency {
  content_id: string;
  version_range: string;
  mandatory: boolean;
}

export interface ContentMetadata {
  content_id: string;
  display_name: string;
  version: string;
  description: string;
  authors: string;
  license: string;
  homepage: string;
  game_version: string;
  loader: string;
  client_only: boolean;
  dependencies: ContentDependency[];
  error: string | null;
}

export interface ContentItem {
  file: string;
  enabled: boolean;
  size_bytes: number;
  mtime: number;
  duplicate: boolean;
  icon_url: string | null;
  metadata: ContentMetadata;
}

export interface VersionDiff {
  content_id: string;
  a: { file: string; version: string };
  b: { file: string; version: string };
}

export interface CompareResult {
  only_in_a: ContentItem[];
  only_in_b: ContentItem[];
  version_diffs: VersionDiff[];
}

export interface ProviderInfo {
  manifest: { id: string; name: string; version: string; games: string[] };
  content_types: { id: string; label: string; default_directory: string }[];
}

// ------------------------------------------------------------------ auth --
export interface AuthUser {
  id: string;
  username: string;
  role: "owner" | "admin" | "moderator" | "viewer";
}

let accessToken = localStorage.getItem("aether.access") ?? "";
let refreshToken = localStorage.getItem("aether.refresh") ?? "";

export function getAccessToken(): string {
  return accessToken;
}

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  localStorage.setItem("aether.access", access);
  localStorage.setItem("aether.refresh", refresh);
}

export function clearTokens() {
  accessToken = "";
  refreshToken = "";
  localStorage.removeItem("aether.access");
  localStorage.removeItem("aether.refresh");
  window.dispatchEvent(new Event("aether:logout"));
}

async function tryRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  const res = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return false;
  const body = await res.json();
  accessToken = body.access_token;
  localStorage.setItem("aether.access", accessToken);
  return true;
}

async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(path, { ...init, headers });

  if (res.status === 401 && !retried && !path.startsWith("/api/v1/auth/")) {
    if (await tryRefresh()) return request<T>(path, init, true);
    clearTokens();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  authStatus: () => request<{ setup_required: boolean }>("/api/v1/auth/status"),
  setup: (username: string, password: string) =>
    request<{ user: AuthUser; access_token: string; refresh_token: string }>(
      "/api/v1/auth/setup",
      { method: "POST", body: JSON.stringify({ username, password }) },
    ),
  login: (username: string, password: string) =>
    request<{ user: AuthUser; access_token: string; refresh_token: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) },
    ),
  me: () => request<AuthUser>("/api/v1/auth/me"),
  providers: () => request<ProviderInfo[]>("/api/v1/providers"),
  instances: () => request<Instance[]>("/api/v1/instances"),
  createInstance: (body: {
    name: string;
    provider_id: string;
    root_dir: string;
    content_dirs: Record<string, string>;
  }) => request<Instance>("/api/v1/instances", { method: "POST", body: JSON.stringify(body) }),
  deleteInstance: (id: string) =>
    request<void>(`/api/v1/instances/${id}`, { method: "DELETE" }),
  content: (id: string, type = "mod") =>
    request<ContentItem[]>(`/api/v1/instances/${id}/content?type=${type}`),
  toggle: (id: string, file: string, type = "mod") =>
    request<{ file: string }>(`/api/v1/instances/${id}/content/toggle`, {
      method: "POST",
      body: JSON.stringify({ type, file }),
    }),
  trash: (id: string, file: string, type = "mod") =>
    request<{ moved_to: string }>(`/api/v1/instances/${id}/content/trash`, {
      method: "POST",
      body: JSON.stringify({ type, file }),
    }),
  copy: (fromId: string, toId: string, file: string, type = "mod") =>
    request<void>(`/api/v1/instances/${fromId}/content/copy`, {
      method: "POST",
      body: JSON.stringify({ type, file, to_instance_id: toId }),
    }),
  compare: (aId: string, bId: string, type = "mod") =>
    request<CompareResult>(
      `/api/v1/instances/${aId}/content/compare?with=${bId}&type=${type}`,
    ),
  power: (id: string, action: "start" | "stop" | "restart" | "kill") =>
    request<{ state: InstanceState }>(`/api/v1/instances/${id}/power`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  status: (id: string) => request<{ state: InstanceState }>(`/api/v1/instances/${id}/status`),
  command: (id: string, command: string) =>
    request<void>(`/api/v1/instances/${id}/command`, {
      method: "POST",
      body: JSON.stringify({ command }),
    }),
  logs: (id: string, tail = 500) =>
    request<{ lines: string[] }>(`/api/v1/instances/${id}/logs?tail=${tail}`),
};

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}
