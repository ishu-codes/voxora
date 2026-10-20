import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Voice settings",
  description:
    "Use the Voxora platform trial or bring your own Sarvam and OpenAI-compatible provider keys.",
};

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
