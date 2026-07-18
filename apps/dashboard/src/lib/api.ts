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

/** Upload multipart: o navegador define o Content-Type com o boundary. */
async function upload<T>(path: string, form: FormData, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(path, { method: "POST", headers, body: form });

  if (res.status === 401 && !retried) {
    if (await tryRefresh()) return upload<T>(path, form, true);
    clearTokens();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
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

export interface BrowseResult {
  path: string | null;
  parent: string | null;
  separator: string;
  entries: { name: string; path: string }[];
}

export const api = {
  authStatus: () => request<{ setup_required: boolean }>("/api/v1/auth/status"),
  browse: (path?: string | null) =>
    request<BrowseResult>(
      `/api/v1/fs/browse${path ? `?path=${encodeURIComponent(path)}` : ""}`,
    ),
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
  listFiles: (id: string, path = "") =>
    request<FileEntry[]>(`/api/v1/instances/${id}/files?path=${encodeURIComponent(path)}`),
  readFile: (id: string, path: string) =>
    request<{ path: string; content: string }>(
      `/api/v1/instances/${id}/files/content?path=${encodeURIComponent(path)}`,
    ),
  writeFile: (id: string, path: string, content: string) =>
    request<void>(`/api/v1/instances/${id}/files/content`, {
      method: "PUT",
      body: JSON.stringify({ path, content }),
    }),
  uploadFiles: (id: string, path: string, files: FileList | File[], overwrite = false) => {
    const form = new FormData();
    form.append("path", path);
    form.append("overwrite", String(overwrite));
    for (const f of Array.from(files)) form.append("uploads", f, f.name);
    return upload<{ saved: { name: string; size: number }[] }>(
      `/api/v1/instances/${id}/files/upload`,
      form,
    );
  },
  fileOp: (id: string, op: "mkdir" | "rename" | "delete", path: string, newName?: string) =>
    request<{ ok: boolean }>(`/api/v1/instances/${id}/files/op`, {
      method: "POST",
      body: JSON.stringify({ op, path, new_name: newName }),
    }),
  configs: (id: string) => request<InstanceConfig[]>(`/api/v1/instances/${id}/config`),
  updateConfig: (id: string, schemaId: string, values: Record<string, string>) =>
    request<void>(`/api/v1/instances/${id}/config`, {
      method: "PUT",
      body: JSON.stringify({ schema_id: schemaId, values }),
    }),
  syncProfiles: (id: string) => request<SyncProfileOut[]>(`/api/v1/instances/${id}/sync-profiles`),
  createSyncProfile: (id: string, body: { name: string; channel: string; rules: SyncRules }) =>
    request<SyncProfileOut>(`/api/v1/instances/${id}/sync-profiles`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  publishSyncProfile: (id: string, profileId: string) =>
    request<SyncProfileOut>(`/api/v1/instances/${id}/sync-profiles/${profileId}/publish`, {
      method: "POST",
    }),
  updateSyncRules: (id: string, profileId: string, rules: SyncRules) =>
    request<SyncProfileOut>(`/api/v1/instances/${id}/sync-profiles/${profileId}/rules`, {
      method: "PUT",
      body: JSON.stringify({ rules }),
    }),
  deleteSyncProfile: (id: string, profileId: string) =>
    request<void>(`/api/v1/instances/${id}/sync-profiles/${profileId}`, { method: "DELETE" }),
};

export interface SyncRule {
  dir: string;
  patterns: string[];
  recursive: boolean;
  action: "require" | "optional";
}

export interface SyncRules {
  rules: SyncRule[];
  exclude: string[];
}

export interface SyncProfileOut {
  id: string;
  instance_id: string;
  name: string;
  channel: string;
  rules: SyncRules;
  published_at: string | null;
  files: number | null;
  total_size: number | null;
}

export interface FileEntry {
  name: string;
  is_dir: boolean;
  size: number;
  mtime: number;
}

export interface ConfigFieldDef {
  key: string;
  label: string;
  type: "string" | "integer" | "boolean" | "enum";
  description: string;
  default: string;
  options: string[];
  section: string;
}

export interface InstanceConfig {
  schema: { id: string; label: string; file: string; fields: ConfigFieldDef[] };
  values: Record<string, string>;
  file_exists: boolean;
}

const ROLE_PERMS: Record<AuthUser["role"], string[]> = {
  owner: ["*"],
  admin: [
    "instances.read", "instances.write", "content.read", "content.write",
    "power.use", "console.use", "audit.read",
    "files.read", "files.write", "config.read", "config.write",
    "sync.read", "sync.write",
  ],
  moderator: ["instances.read", "content.read", "power.use", "console.use"],
  viewer: ["instances.read", "content.read"],
};

export function can(user: AuthUser | null, permission: string): boolean {
  if (!user) return false;
  const perms = ROLE_PERMS[user.role] ?? [];
  return perms.includes("*") || perms.includes(permission);
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}
