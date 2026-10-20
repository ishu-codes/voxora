"use client";

import { SettingsIcon } from "lucide-react";
import Link from "next/link";
import { Wordmark } from "@/components/marketing/Wordmark";
import { ThemeToggle } from "@/components/navbar/ThemeToggle";
import { Button } from "@/components/ui/button";

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 h-[85px] w-full shrink-0 border-b border-border bg-background">
      <div className="container flex h-full items-center justify-between">
        <Link href="/" aria-label="Voxora home">
          <Wordmark size="lg" />
        </Link>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="icon"
            render={<Link href="/settings" />}
            aria-label="Provider settings"
            title="Provider settings"
            className="rounded-full text-muted-foreground hover:text-foreground"
          >
            <SettingsIcon className="size-[1.2rem]" />
          </Button>
        </div>
      </div>
    </header>
  );
}
