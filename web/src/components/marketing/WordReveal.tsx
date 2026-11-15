"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type WordRevealProps = {
  text: string;
  className?: string;
};

export function WordReveal({ text, className }: WordRevealProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [visible, setVisible] = useState(false);
  const words = text.split(" ").map((word, index) => ({
    id: `${word}-${index}`,
    word,
  }));

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.35 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <p
      ref={ref}
      className={cn(
        "max-w-[680px] text-4xl font-semibold tracking-tighter text-balance sm:text-5xl lg:text-6xl",
        className,
      )}
    >
      {words.map((entry, index) => (
        <span
          key={entry.id}
          className={cn(
            "inline opacity-30 transition-opacity duration-700 ease-[cubic-bezier(0.32,0.72,0,1)]",
            visible && "opacity-100",
          )}
          style={{ transitionDelay: `${index * 55}ms` }}
        >
          {entry.word}
          {index < words.length - 1 ? " " : ""}
        </span>
      ))}
    </p>
  );
}
