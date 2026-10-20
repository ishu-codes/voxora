const INSTALLATION_KEY = "voxora.installation-id.v1";

export type ClientFingerprint = {
  installation_id: string;
  screen_width: number;
  screen_height: number;
  viewport_width: number;
  viewport_height: number;
  pixel_ratio: number;
  color_depth: number;
  timezone: string;
  language: string;
  platform: string;
  hardware_concurrency: number;
  device_memory: number;
  touch_points: number;
  webdriver: boolean;
};

function installationId(): string {
  if (typeof window === "undefined") return "";
  try {
    const existing = window.localStorage.getItem(INSTALLATION_KEY);
    if (existing) return existing;
    const created =
      typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(INSTALLATION_KEY, created);
    return created;
  } catch {
    return "";
  }
}

/**
 * Coarse, non-intrusive device signals used by the server to group anonymous
 * sessions. No canvas, audio or WebGL fingerprinting is performed here.
 */
export function collectClientFingerprint(): ClientFingerprint {
  if (typeof window === "undefined") {
    return {
      installation_id: "",
      screen_width: 0,
      screen_height: 0,
      viewport_width: 0,
      viewport_height: 0,
      pixel_ratio: 0,
      color_depth: 0,
      timezone: "",
      language: "",
      platform: "",
      hardware_concurrency: 0,
      device_memory: 0,
      touch_points: 0,
      webdriver: false,
    };
  }

  const navigatorWithMemory = navigator as Navigator & {
    deviceMemory?: number;
  };

  return {
    installation_id: installationId(),
    screen_width: window.screen.width,
    screen_height: window.screen.height,
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    pixel_ratio: window.devicePixelRatio,
    color_depth: window.screen.colorDepth,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? "",
    language: navigator.language,
    platform: navigator.platform,
    hardware_concurrency: navigator.hardwareConcurrency,
    device_memory: navigatorWithMemory.deviceMemory ?? 0,
    touch_points: navigator.maxTouchPoints,
    webdriver: navigator.webdriver,
  };
}
