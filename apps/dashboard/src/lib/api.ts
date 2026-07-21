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
  /** A pasta foi criada pelo painel (some com a instância) ou é do usuário? */
  managed_dir: boolean;
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
  /** O painel instala e atualiza a versão do servidor deste jogo. */
  install: boolean;
  players: boolean;
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

/** O que a remoção de uma instância levou junto. */
export interface RemocaoRelatorio {
  container_removido: boolean;
  pasta_removida: string;
  pasta_preservada: string;
  backups_removidos: number;
  bytes_liberados: number;
  registros_removidos: Record<string, number>;
  falhas: string[];
}

export interface RequisitosDeHardware {
  cpu: string;
  ram: string;
  disco: string;
  rede: string;
  observacao: string;
}

export interface GameCatalogEntry {
  id: string;
  provider_id: string;
  nome: string;
  tagline: string;
  descricao: string;
  genero: string[];
  desenvolvedora: string;
  publicadora: string;
  plataformas_do_cliente: string[];
  so_do_servidor: string[];
  logo_url: string;
  banner_url: string;
  atribuicao_da_imagem: string;
  requisitos_servidor_minimo: RequisitosDeHardware | null;
  requisitos_servidor_recomendado: RequisitosDeHardware | null;
  requisitos_cliente_minimo: RequisitosDeHardware | null;
  requisitos_cliente_recomendado: RequisitosDeHardware | null;
  ram_por_jogadores: { ate_jogadores: number; ram: string; observacao: string }[];
  portas: { numero: number; protocolo: string; descricao: string; obrigatoria: boolean }[];
  observacoes_de_hospedagem: string[];
  links: { titulo: string; url: string }[];
  steam_app_id: number | null;
}

/** Estado da instalação para a autoatualização. */
export interface UpdateStatus {
  version: string;
  gerenciavel: boolean;
  motivo: string;
  branch: string;
  commit: string;
  commit_curto: string;
  data_do_commit: string;
  assunto: string;
  alteracoes_locais: string[];
  commits_atras: number;
  atualizando: boolean;
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
  catalog: () => request<GameCatalogEntry[]>("/api/v1/catalog"),
  catalogGame: (id: string, atualizar = false) =>
    request<GameCatalogEntry>(`/api/v1/catalog/${id}${atualizar ? "?atualizar=true" : ""}`),
  updateStatus: () => request<UpdateStatus>("/api/v1/system/update"),
  runUpdate: () =>
    request<{ commit_curto: string; assunto: string; banco_salvo_em: string }>(
      "/api/v1/system/update",
      { method: "POST" },
    ),
  instances: () => request<Instance[]>("/api/v1/instances"),
  createInstance: (body: {
    name: string;
    provider_id: string;
    root_dir?: string;
    runtime?: InstanceRuntime;
    content_dirs?: Record<string, string>;
    provision_values?: Record<string, string>;
    /** Versão a instalar; a criação já dispara a instalação. */
    version?: string;
  }) => request<Instance>("/api/v1/instances", { method: "POST", body: JSON.stringify(body) }),
  images: () => request<ImagesPayload>("/api/v1/images"),
  pullImage: (image: string) =>
    request<{ image: string }>("/api/v1/images/pull", {
      method: "POST",
      body: JSON.stringify({ image }),
    }),
  removeImage: (image: string) =>
    request<void>(`/api/v1/images?image=${encodeURIComponent(image)}`, { method: "DELETE" }),
  deleteInstance: (id: string, keepFiles = false) =>
    request<RemocaoRelatorio>(
      `/api/v1/instances/${id}${keepFiles ? "?keep_files=true" : ""}`,
      { method: "DELETE" },
    ),
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
    request<{ trash_item_id: string }>(`/api/v1/instances/${id}/content/trash`, {
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
  /** Conteúdo da lixeira. Não confundir com `trash`, que *manda* um mod para lá. */
  players: (id: string) => request<{ lists: PlayerList[] }>(`/api/v1/instances/${id}/players`),
  playerAction: (id: string, action: PlayerAction, name: string, reason = "") =>
    request<{ applied_via: "console" | "arquivo" | "recarga" }>(
      `/api/v1/instances/${id}/players/action`,
      { method: "POST", body: JSON.stringify({ action, name, reason }) },
    ),
  listTrash: (id: string) => request<TrashPayload>(`/api/v1/instances/${id}/trash`),
  restoreTrash: (id: string, itemId: string) =>
    request<{ restored_to: string }>(`/api/v1/instances/${id}/trash/${itemId}/restore`, {
      method: "POST",
    }),
  purgeTrash: (id: string, itemId: string) =>
    request<void>(`/api/v1/instances/${id}/trash/${itemId}`, { method: "DELETE" }),
  emptyTrash: (id: string) =>
    request<{ removed: number }>(`/api/v1/instances/${id}/trash`, { method: "DELETE" }),
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
  // --------------------------------------------------- config em modo avançado
  rawConfig: (id: string, schemaId: string) =>
    request<RawConfig>(`/api/v1/instances/${id}/config/raw?schema_id=${schemaId}`),
  validateRawConfig: (id: string, schemaId: string, content: string) =>
    request<RawConfigValidation>(`/api/v1/instances/${id}/config/raw/validate`, {
      method: "POST",
      body: JSON.stringify({ schema_id: schemaId, content }),
    }),
  writeRawConfig: (id: string, schemaId: string, content: string) =>
    request<{ file: string; has_previous: boolean }>(`/api/v1/instances/${id}/config/raw`, {
      method: "PUT",
      body: JSON.stringify({ schema_id: schemaId, content }),
    }),
  restoreRawConfig: (id: string, schemaId: string) =>
    request<{ file: string; content: string }>(
      `/api/v1/instances/${id}/config/raw/restore?schema_id=${schemaId}`,
      { method: "POST" },
    ),
  // ------------------------------------------------------ versão do servidor
  providerVersions: (providerId: string, atualizar = false) =>
    request<VersionInfo[]>(
      `/api/v1/providers/${providerId}/versions${atualizar ? "?atualizar=true" : ""}`,
    ),
  // ------------------------------------------------------------------ portas
  instancePorts: (id: string) => request<InstancePorts>(`/api/v1/instances/${id}/ports`),
  saveInstancePorts: (id: string, ports: Omit<InstancePort, "from_provider">[]) =>
    request<InstancePorts>(`/api/v1/instances/${id}/ports`, {
      method: "PUT",
      body: JSON.stringify({ ports }),
    }),
  instanceVersion: (id: string) =>
    request<InstanceVersion>(`/api/v1/instances/${id}/version`),
  installVersion: (id: string, version: string, skipBackup = false) =>
    request<ServerInstallResult>(`/api/v1/instances/${id}/install`, {
      method: "POST",
      body: JSON.stringify({ version, skip_backup: skipBackup }),
    }),
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

export interface TrashItem {
  id: string;
  /** Nome original — `original_path` é o que permite devolver ao lugar. */
  name: string;
  original_path: string;
  is_dir: boolean;
  size_bytes: number;
  origin: "files" | "content";
  content_type: string;
  trashed_at: string;
}

export interface TrashPayload {
  items: TrashItem[];
  total_bytes: number;
}

export type PlayerAction =
  | "allow_add"
  | "allow_remove"
  | "admin_add"
  | "admin_remove"
  | "ban"
  | "unban"
  | "kick";

export interface PlayerEntry {
  name: string;
  id: string;
  /** Texto do jogo: motivo do ban, nível do operador. O front não interpreta. */
  detail: string;
}

export interface PlayerList {
  kind: "allow" | "admin" | "banned";
  label: string;
  /** Falso quando o servidor está ignorando a lista (white-list=false). */
  enforced: boolean;
  entries: PlayerEntry[];
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
  /** Só aparece quando outro campo tem certo valor (semente/tamanho ↔ RWG). */
  depends_on?: Record<string, string>;
  key: string;
  label: string;
  type: "string" | "integer" | "boolean" | "enum" | "password";
  description: string;
  default: string;
  options: string[];
  section: string;
}

export interface RawConfig {
  file: string;
  format: string;
  content: string;
  has_previous: boolean;
}

export interface RawConfigValidation {
  valid: boolean;
  message?: string;
  line?: number;
  column?: number;
}

export interface VersionInfo {
  id: string;
  label: string;
  description: string;
  build: string;
  stable: boolean;
}

export interface InstanceVersion {
  installed: string;
  requested: string;
  installing: boolean;
  /** Motivo da última instalação que falhou; vazio quando correu bem. */
  error: string;
  disk_free: number;
  /** 0 quando o provider não sabe declarar o tamanho da instalação. */
  disk_required: number;
}

export interface InstancePort {
  container_port: number;
  protocol: string;
  host_port: number;
  description: string;
  /** Porta que o jogo exige: a interna não é editável e a linha não some. */
  from_provider: boolean;
}

export interface InstancePorts {
  runtime: string;
  ports: InstancePort[];
  restart_required: boolean;
}

/** Resultado de instalar/atualizar a versão do servidor (não confundir com
 * o InstallResult do catálogo de mods). */
export interface ServerInstallResult {
  version: string;
  status?: string;
  install?: { config_seeded?: boolean; new_properties?: string[]; build?: string };
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
