/** Typed client for the Aether Core v1 API. */

export type InstanceState = "stopped" | "starting" | "running" | "stopping" | "crashed";

export type InstanceRuntime = "process" | "docker";

export interface Instance {
  id: string;
  name: string;
  provider_id: string;
  root_dir: string;
  runtime: InstanceRuntime;
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

/** O que o provider sabe fazer — a interface liga telas por capability,
 * nunca por id de provider. */
export interface ProviderCapabilities {
  launch: boolean;
  container: boolean;
  provision: boolean;
  config: boolean;
  backup: boolean;
  sources: boolean;
  game_metadata: boolean;
}

export interface ProviderInfo {
  manifest: {
    id: string;
    name: string;
    version: string;
    games: string[];
    icon_spec?: { file: string; size: number } | null;
  };
  content_types: { id: string; label: string; default_directory: string }[];
  capabilities: ProviderCapabilities;
  provision_schema?: { id: string; label: string; fields: ConfigFieldDef[] };
}

export interface ImageInfo {
  id: string;
  tags: string[];
  size_bytes: number;
}

export interface ImagesPayload {
  referenced: { provider_id: string; image: string }[];
  installed: ImageInfo[];
  pulling: string[];
}

// ------------------------------------------------------------------ auth --
export interface AuthUser {
  id: string;
  username: string;
  role: "owner" | "admin" | "moderator" | "viewer";
  email: string;
  display_name: string;
  /** Nome de exibição, caindo para o de usuário quando vazio. */
  label: string;
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
async function upload<T>(
  path: string,
  form: FormData,
  opts: { method?: string } = {},
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(path, { method: opts.method ?? "POST", headers, body: form });

  if (res.status === 401 && !retried) {
    if (await tryRefresh()) return upload<T>(path, form, opts, true);
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
  setup: (username: string, password: string, email = "", displayName = "") =>
    request<{ user: AuthUser; access_token: string; refresh_token: string }>(
      "/api/v1/auth/setup",
      {
        method: "POST",
        body: JSON.stringify({ username, password, email, display_name: displayName }),
      },
    ),
  login: (username: string, password: string) =>
    request<{ user: AuthUser; access_token: string; refresh_token: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) },
    ),
  me: () => request<AuthUser>("/api/v1/auth/me"),
  updateProfile: (email: string, displayName: string) =>
    request<AuthUser>("/api/v1/auth/me", {
      method: "PUT",
      body: JSON.stringify({ email, display_name: displayName }),
    }),
  changePassword: (current: string, next: string) =>
    request<{ access_token: string; refresh_token: string }>("/api/v1/auth/password", {
      method: "POST",
      body: JSON.stringify({ current_password: current, new_password: next }),
    }),
  resetUserPassword: (userId: string, newPassword: string) =>
    request<void>(`/api/v1/users/${userId}/password`, {
      method: "POST",
      body: JSON.stringify({ new_password: newPassword }),
    }),
  providers: () => request<ProviderInfo[]>("/api/v1/providers"),
  instances: () => request<Instance[]>("/api/v1/instances"),
  createInstance: (body: {
    name: string;
    provider_id: string;
    root_dir?: string;
    runtime?: InstanceRuntime;
    content_dirs?: Record<string, string>;
    provision_values?: Record<string, string>;
  }) => request<Instance>("/api/v1/instances", { method: "POST", body: JSON.stringify(body) }),
  images: () => request<ImagesPayload>("/api/v1/images"),
  pullImage: (image: string) =>
    request<{ image: string }>("/api/v1/images/pull", {
      method: "POST",
      body: JSON.stringify({ image }),
    }),
  removeImage: (image: string) =>
    request<void>(`/api/v1/images?image=${encodeURIComponent(image)}`, { method: "DELETE" }),
  deleteInstance: (id: string) =>
    request<void>(`/api/v1/instances/${id}`, { method: "DELETE" }),
  metrics: () => request<MetricsPayload>("/api/v1/metrics"),
  users: () => request<UserOut[]>("/api/v1/users"),
  createUser: (
    username: string,
    password: string,
    role: string,
    email = "",
    displayName = "",
  ) =>
    request<UserOut>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify({ username, password, role, email, display_name: displayName }),
    }),
  deleteUser: (id: string) => request<void>(`/api/v1/users/${id}`, { method: "DELETE" }),
  audit: (limit = 100) => request<AuditEntry[]>(`/api/v1/audit?limit=${limit}`),
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
  /** `toType` difere de `type` ao levar um mod do servidor para o cliente. */
  copy: (fromId: string, toId: string, file: string, type = "mod", toType?: string) =>
    request<void>(`/api/v1/instances/${fromId}/content/copy`, {
      method: "POST",
      body: JSON.stringify({ type, file, to_instance_id: toId, to_type: toType ?? null }),
    }),
  compare: (aId: string, bId: string, type = "mod", withType?: string) =>
    request<CompareResult>(
      `/api/v1/instances/${aId}/content/compare?with=${bId}&type=${type}` +
        (withType ? `&with_type=${withType}` : ""),
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
  iconUrl: (id: string) => `/api/v1/instances/${id}/config/icon`,
  uploadIcon: (id: string, png: Blob) => {
    const form = new FormData();
    form.append("upload", png, "server-icon.png");
    return upload<{ file: string; size: number }>(`/api/v1/instances/${id}/config/icon`, form, {
      method: "PUT",
    });
  },
  deleteIcon: (id: string) =>
    request<void>(`/api/v1/instances/${id}/config/icon`, { method: "DELETE" }),
  sources: (id: string) => request<SourceInfo[]>(`/api/v1/instances/${id}/sources`),
  catalogFilters: (id: string, sourceId = "modrinth") =>
    request<CatalogFilters>(`/api/v1/instances/${id}/sources/filters?source_id=${sourceId}`),
  searchCatalog: (
    id: string,
    q: string,
    opts: {
      sourceId?: string;
      allVersions?: boolean;
      offset?: number;
      limit?: number;
      categories?: string[];
      loader?: string;
    } = {},
  ) =>
    request<CatalogItem[]>(
      `/api/v1/instances/${id}/sources/search?q=${encodeURIComponent(q)}` +
        `&source_id=${opts.sourceId ?? "modrinth"}` +
        `&all_versions=${opts.allVersions ?? false}` +
        `&offset=${opts.offset ?? 0}&limit=${opts.limit ?? 24}` +
        `&categories=${encodeURIComponent((opts.categories ?? []).join(","))}` +
        `&loader=${encodeURIComponent(opts.loader ?? "")}`,
    ),
  catalogVersions: (id: string, projectId: string, sourceId = "modrinth", allVersions = false) =>
    request<CatalogVersion[]>(
      `/api/v1/instances/${id}/sources/versions?project_id=${encodeURIComponent(projectId)}` +
        `&source_id=${sourceId}&all_versions=${allVersions}`,
    ),
  planInstall: (id: string, body: { source_id: string; version_id: string; type?: string }) =>
    request<InstallPlan>(`/api/v1/instances/${id}/sources/plan`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  installFromCatalog: (
    id: string,
    body: {
      source_id: string;
      version_id: string;
      type?: string;
      overwrite?: boolean;
      with_dependencies?: boolean;
    },
  ) =>
    request<InstallResult>(
      `/api/v1/instances/${id}/sources/install`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  catalogUpdates: (id: string, type = "mod", sourceId = "modrinth") =>
    request<UpdateCandidate[]>(
      `/api/v1/instances/${id}/sources/updates?type=${type}&source_id=${sourceId}`,
    ),
  tasks: (id: string) => request<ScheduledTask[]>(`/api/v1/instances/${id}/tasks`),
  createTask: (id: string, body: TaskInput) =>
    request<ScheduledTask>(`/api/v1/instances/${id}/tasks`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateTask: (id: string, taskId: string, body: TaskInput) =>
    request<ScheduledTask>(`/api/v1/instances/${id}/tasks/${taskId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteTask: (id: string, taskId: string) =>
    request<void>(`/api/v1/instances/${id}/tasks/${taskId}`, { method: "DELETE" }),
  runTask: (id: string, taskId: string) =>
    request<Record<string, unknown>>(`/api/v1/instances/${id}/tasks/${taskId}/run`, {
      method: "POST",
    }),
  backups: (id: string) => request<BackupsPayload>(`/api/v1/instances/${id}/backups`),
  createBackup: (id: string, note = "") =>
    request<BackupEntry>(`/api/v1/instances/${id}/backups`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  deleteBackup: (id: string, backupId: string) =>
    request<void>(`/api/v1/instances/${id}/backups/${backupId}`, { method: "DELETE" }),
  restoreBackup: (id: string, backupId: string) =>
    request<{ restored_files: number; safety_backup_id: string }>(
      `/api/v1/instances/${id}/backups/${backupId}/restore`,
      { method: "POST" },
    ),
  setBackupPolicy: (id: string, schedule: BackupSchedule, keep: number) =>
    request<BackupPolicy>(`/api/v1/instances/${id}/backups/policy`, {
      method: "PUT",
      body: JSON.stringify({ schedule, keep }),
    }),
  backupDownloadUrl: (id: string, backupId: string) =>
    `/api/v1/instances/${id}/backups/${backupId}/download`,
  backupDownloadToken: (id: string, backupId: string) =>
    request<{ token: string }>(
      `/api/v1/instances/${id}/backups/${backupId}/download-token`,
      { method: "POST" },
    ),
  downloadToken: (id: string, path: string) =>
    request<{ token: string }>(
      `/api/v1/instances/${id}/files/download-token?path=${encodeURIComponent(path)}`,
      { method: "POST" },
    ),
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
  downloadUrl: (id: string, path: string) =>
    `/api/v1/instances/${id}/files/download?path=${encodeURIComponent(path)}`,
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

export interface UserOut {
  id: string;
  username: string;
  role: string;
  email: string;
  display_name: string;
  label: string;
  created_at?: string;
}

export interface AuditEntry {
  id: number;
  username: string | null;
  action: string;
  ip: string | null;
  created_at: string;
}

export interface HostMetrics {
  cpu_percent: number; cpu_count: number;
  mem_total: number; mem_used: number; mem_percent: number;
  disk_total: number; disk_used: number; disk_percent: number;
  uptime_seconds: number; load_avg: number[];
}
export interface ProcMetrics {
  instance_id: string; name: string; pid: number | null;
  /** Padrão psutil: 100% = um núcleo saturado. */
  cpu_percent: number;
  /** O mesmo uso relativo à máquina inteira. */
  cpu_percent_total: number;
  cpu_count: number;
  mem_bytes: number; running: boolean;
}
export interface MetricsPayload {
  host: HostMetrics;
  instances: ProcMetrics[];
  history: { ts: number; cpu: number; mem_percent: number; mem_used: number }[];
}

export interface SyncRule {
  dir: string;
  /** Onde cai no PC do jogador. Ausente = mesma pasta de origem. */
  target?: string | null;
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

export interface SourceInfo {
  id: string;
  label: string;
  requires_api_key: boolean;
}

export interface CatalogFilters {
  categories: { id: string; label: string }[];
  loaders: { id: string; label: string }[];
}

export interface CatalogItem {
  source_id: string;
  project_id: string;
  slug: string;
  name: string;
  summary: string;
  author: string;
  downloads: number;
  icon_url: string | null;
  page_url: string | null;
  categories: string[];
}

export interface CatalogVersion {
  source_id: string;
  project_id: string;
  version_id: string;
  version_number: string;
  file_name: string;
  size: number;
  game_versions: string[];
  loaders: string[];
  released_at: string | null;
  dependencies: { project_id: string; kind: string }[];
}

export interface PlannedItem {
  project_id: string;
  version_id: string;
  version_number: string;
  file_name: string;
  size: number;
  required_by: string | null;
}

export interface InstallPlan {
  items: PlannedItem[];
  already_installed: string[];
  missing: string[];
  conflicts: string[];
  ok: boolean;
  total_size: number;
}

/** Instalação simples devolve o arquivo; com dependências, a lista. */
export type InstallResult =
  | { file: string; size: number; version: string }
  | { installed: { file: string; size: number; version: string }[]; count: number };

export interface UpdateCandidate {
  file: string;
  project_id: string;
  source_id: string;
  display_name: string;
  current_version: string;
  latest_version: string;
  latest_version_id: string;
  latest_file_name: string;
  released_at: string | null;
}

export type TaskKind = "restart" | "command" | "backup";
export type TaskSchedule = "hourly" | "daily" | "weekly";

export interface TaskInput {
  kind: TaskKind;
  schedule: TaskSchedule;
  at_hour?: number;
  at_minute?: number;
  weekday?: number;
  enabled?: boolean;
  command?: string;
  warn_minutes?: number;
}

export interface ScheduledTask {
  id: string;
  kind: TaskKind;
  schedule: TaskSchedule;
  at_hour: number;
  at_minute: number;
  weekday: number;
  enabled: boolean;
  command: string;
  warn_minutes: number;
  last_run: string | null;
  /** Frase pronta vinda do Core — a interface não remonta a regra. */
  description: string;
}

export type BackupSchedule = "off" | "hourly" | "daily" | "weekly";

export interface BackupEntry {
  id: string;
  file_name: string;
  size_bytes: number;
  kind: "manual" | "scheduled";
  note: string;
  created_at: string;
}

export interface BackupPolicy {
  schedule: BackupSchedule;
  keep: number;
}

export interface BackupsPayload {
  backups: BackupEntry[];
  policy: BackupPolicy;
  /** O que o provider define como backup — mostrado para não haver surpresa. */
  spec: { include: string[]; exclude: string[]; summary: string };
}

export interface ConfigWarning {
  key: string;
  message: string;
  level: "warning" | "error";
}

export interface ConfigFieldDef {
  advanced?: boolean;
  minimum?: number | null;
  maximum?: number | null;
  key: string;
  label: string;
  type: "string" | "integer" | "boolean" | "enum" | "password";
  description: string;
  default: string;
  options: string[];
  section: string;
}

export interface InstanceConfig {
  warnings?: ConfigWarning[];
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
    "backups.read", "backups.write",
  ],
  // Vê e baixa backup, mas não restaura nem apaga: restaurar sobrescreve o
  // mundo, e isso é decisão de quem administra.
  moderator: ["instances.read", "content.read", "power.use", "console.use", "backups.read"],
  viewer: ["instances.read", "content.read"],
};

export function can(user: AuthUser | null, permission: string): boolean {
  if (!user) return false;
  const perms = ROLE_PERMS[user.role] ?? [];
  return perms.includes("*") || perms.includes(permission);
}

/** Copia texto funcionando também fora de contexto seguro (http://IP).
 *  navigator.clipboard só existe em HTTPS/localhost — no acesso por IP da
 *  rede ele é indefinido, por isso o fallback com textarea. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* cai no fallback */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}
