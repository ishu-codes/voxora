"use client";

import { Menu, X as XIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Pill } from "@/components/marketing/Pill";
import { Wordmark } from "@/components/marketing/Wordmark";
import { ThemeToggle } from "@/components/navbar/ThemeToggle";

const NAV_LINKS = [
  { label: "How it works", href: "/#pipeline" },
  { label: "Capabilities", href: "/#capabilities" },
  { label: "Latency", href: "/#latency" },
  { label: "FAQ", href: "/#faq" },
  { label: "Deployment", href: "/#deployment" },
  { label: "Pitch", href: "/pitch" },
];

export function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 z-50 w-full border-b border-border bg-background">
      <div className="container flex h-[85px] items-center justify-between">
        <Link href="/" aria-label="Voxora home">
          <Wordmark size="lg" />
        </Link>

        <nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="rounded-full px-4 py-2 text-sm font-medium text-muted-foreground/80 transition-colors duration-300 hover:bg-foreground hover:text-background"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 lg:flex">
          <ThemeToggle />
          <Pill asLink to="/app">
            Start talking
          </Pill>
        </div>

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

      {isMenuOpen && (
        <div className="border-t border-border bg-background px-4 py-5 lg:hidden">
          <nav className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setIsMenuOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="mt-4 flex items-center justify-between gap-2 border-t border-border pt-4">
            <ThemeToggle />
            <Pill asLink to="/app" className="flex-1 justify-center">
              Start talking
            </Pill>
          </div>
        </div>
      )}
    </header>
  );
}
