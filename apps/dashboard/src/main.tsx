import {
  QueryClient,
  QueryClientProvider,
  focusManager,
  onlineManager,
} from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { DialogProvider } from "./components/Dialog.tsx";
import { applyTheme, currentTheme } from "./lib/themes.ts";
import { AuthGate } from "./modules/auth/AuthGate.tsx";
import "./index.css";

// Aplica o tema salvo antes do primeiro render (evita flash do padrão).
applyTheme(currentTheme());

// O Core é o próprio host servindo a página: "offline"/"sem foco" do navegador
// (LAN sem internet, webview embutida, aba em segundo plano) não significam
// nada aqui — e pausariam retries de query num spinner eterno. Forçamos os
// dois gerenciadores; o refetch-por-foco já fica desligado logo abaixo.
onlineManager.setOnline(true);
focusManager.setFocused(true);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, networkMode: "always" },
    mutations: { networkMode: "always" },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Fora do AuthGate: a tela de login também pode precisar avisar algo. */}
      <DialogProvider>
        <AuthGate>
          <App />
        </AuthGate>
      </DialogProvider>
    </QueryClientProvider>
  </StrictMode>,
);
