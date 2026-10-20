import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type PillProps = {
  children: ReactNode;
  className?: string;
  asLink?: boolean;
  to?: string;
  href?: string;
  target?: string;
  rel?: string;
};

const pillBase =
  "inline-flex items-center justify-center gap-2 rounded-[100px] px-5 py-2.5 text-sm font-medium transition-colors duration-300 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none sm:px-6 sm:py-3 sm:text-base";

export function Pill({
  children,
  className,
  to,
  href,
  target,
  rel,
}: PillProps) {
  const classes = cn(
    pillBase,
    "bg-brand text-brand-foreground shadow hover:bg-brand/85",
    className,
  );

  if (to) {
    return (
      <Link href={to} className={classes} target={target} rel={rel}>
        {children}
      </Link>
    );
  }

  return (
    <a href={href} className={classes} target={target} rel={rel}>
      {children}
    </a>
  );
}

export function OutlinePill({
  children,
  className,
  to,
  href,
  target,
  rel,
}: PillProps) {
  const classes = cn(
    pillBase,
    "border border-input bg-transparent text-foreground shadow hover:bg-muted/80",
    className,
  );

  if (to) {
    return (
      <Link href={to} className={classes} target={target} rel={rel}>
        {children}
      </Link>
    );
  }

  return (
    <a href={href} className={classes} target={target} rel={rel}>
      {children}
    </a>
  );
}
