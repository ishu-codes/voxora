import { useEffect, useState } from "react";

import {
  getVoiceCatalog,
  readVoiceCatalogCache,
  type VoiceCatalog,
} from "@/lib/voice-catalog";

/**
 * Loads the backend voice catalog once per mount. A localStorage copy keeps the
 * picker populated across reloads and lets a stale copy survive API downtime.
 */
export function useVoiceCatalog(provider = "sarvam"): VoiceCatalog | null {
  // Start empty so server and client markup agree; the cached copy is applied
  // immediately after hydration.
  const [catalog, setCatalog] = useState<VoiceCatalog | null>(null);

  useEffect(() => {
    let active = true;
    const cached = readVoiceCatalogCache(provider);
    setCatalog(cached?.catalog ?? null);
    void getVoiceCatalog(provider).then((next) => {
      if (active && next) setCatalog(next);
    });
    return () => {
      active = false;
    };
  }, [provider]);

  return catalog;
}
