/** Acesso aos providers do Core.
 *
 * A lista muda apenas com deploy do servidor, então o cache é longo — e todo
 * componente que liga/desliga telas por capability lê daqui, nunca de um id
 * de provider fixo no código.
 */

import { useQuery } from "@tanstack/react-query";
import type { ProviderInfo } from "./api";
import { api } from "./api";

export function useProviders(): ProviderInfo[] {
  const query = useQuery({
    queryKey: ["providers"],
    queryFn: api.providers,
    staleTime: 5 * 60 * 1000,
  });
  return query.data ?? [];
}

export function useProvider(providerId: string): ProviderInfo | undefined {
  return useProviders().find((p) => p.manifest.id === providerId);
}
