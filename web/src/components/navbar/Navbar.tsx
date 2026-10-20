"use client";

import { Menu, SettingsIcon, X as XIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Wordmark } from "@/components/marketing/Wordmark";
import { ThemeToggle } from "@/components/navbar/ThemeToggle";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 z-50 w-full border-b border-border bg-background">
      <div className="container flex h-[85px] items-center justify-between">
        <Link href="/" aria-label="Voxora home">
          <Wordmark size="lg" />
        </Link>

        <div className="flex items-center gap-1">
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
          <ThemeToggle />
          <button
            type="button"
            className="flex size-9 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:hidden"
            onClick={() => setIsMenuOpen((open) => !open)}
            aria-label="Toggle navigation"
            aria-expanded={isMenuOpen}
          >
            {isMenuOpen ? (
              <XIcon className="size-5" />
            ) : (
              <Menu className="size-5" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
