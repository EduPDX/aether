import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { DialogProvider } from "./components/Dialog.tsx";
import { applyTheme, currentTheme } from "./lib/themes.ts";
import { AuthGate } from "./modules/auth/AuthGate.tsx";
import "./index.css";

// Aplica o tema salvo antes do primeiro render (evita flash do padrão).
applyTheme(currentTheme());

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
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
