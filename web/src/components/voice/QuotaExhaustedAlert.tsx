"use client";

import { Clock3Icon, KeyRoundIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type QuotaExhaustedAlertProps = {
  limit: number;
  retryAt: number;
  onDismiss: () => void;
  onExpired: () => void;
};

function countdown(remainingMs: number): string {
  const totalSeconds = Math.max(0, Math.ceil(remainingMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function QuotaExhaustedAlert({
  limit,
  retryAt,
  onDismiss,
  onExpired,
}: QuotaExhaustedAlertProps) {
  const [now, setNow] = useState(() => Date.now());
  const remaining = retryAt - now;

  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const timer = window.setInterval(tick, 1_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (remaining <= 0) onExpired();
  }, [onExpired, remaining]);

  return (
    <div className="container pb-2">
      <Alert className="relative border-brand/35 bg-brand/5 shadow-sm">
        <span className="row-span-2 flex size-9 items-center justify-center rounded-full bg-brand/15 text-brand">
          <Clock3Icon className="size-4" aria-hidden="true" />
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onDismiss}
          aria-label="Dismiss quota notice"
          className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
        >
          <XIcon />
        </Button>
        <AlertTitle>Free query credits exhausted</AlertTitle>
        <AlertDescription className="max-w-2xl pr-8">
          You have used all {limit} free platform queries for this rolling
          one-hour window. Add your own API keys to keep chatting without
          platform limits, or wait{" "}
          <span className="font-mono font-medium text-foreground tabular-nums">
            {remaining > 0 ? countdown(remaining) : "0:00"}
          </span>{" "}
          for the next query.
        </AlertDescription>
        <AlertAction>
          <Link
            href="/settings"
            className={cn(
              buttonVariants({ variant: "default", size: "sm" }),
              "rounded-full px-3",
            )}
          >
            <KeyRoundIcon className="size-3.5" aria-hidden="true" />
            Bring your own keys
          </Link>
          <span className="text-xs text-muted-foreground">
            Your provider keys stay in this browser.
          </span>
        </AlertAction>
      </Alert>
    </div>
  );
}
