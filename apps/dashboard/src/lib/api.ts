/** Typed client for the Aether Core v1 API. */

export interface Instance {
  id: string;
  name: string;
  provider_id: string;
  root_dir: string;
  content_dirs: Record<string, string>;
  created_at: string;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
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
};

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}
