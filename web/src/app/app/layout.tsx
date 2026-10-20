import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Voice studio",
  description:
    "Talk to Voxora in real time over a streaming WebSocket voice session.",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return children;
}
