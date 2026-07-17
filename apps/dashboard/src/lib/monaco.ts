/** Monaco bundled locally (no CDN): workers via Vite + loader config. */

import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import jsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";

self.MonacoEnvironment = {
  getWorker: (_workerId: string, label: string) =>
    label === "json" ? new jsonWorker() : new editorWorker(),
};

loader.config({ monaco });

const EXT_LANGUAGE: Record<string, string> = {
  json: "json",
  mcmeta: "json",
  json5: "json",
  yml: "yaml",
  yaml: "yaml",
  toml: "ini",
  properties: "ini",
  cfg: "ini",
  ini: "ini",
  conf: "ini",
  sh: "shell",
  bat: "bat",
  md: "markdown",
  js: "javascript",
  log: "plaintext",
  txt: "plaintext",
};

export function languageFor(fileName: string): string {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  return EXT_LANGUAGE[ext] ?? "plaintext";
}
