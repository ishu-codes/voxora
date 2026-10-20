/**
 * Tracks which assistant turns have been interrupted.
 *
 * A turn id is marked the moment the user barges in, before the backend has
 * acknowledged the cancellation. Every later event for that id is ignored, so
 * a late LLM token or TTS chunk cannot revive the old response or overwrite a
 * newer one.
 */
export class InterruptedTurns {
  private readonly cancelled = new Set<string>();
  private active: string | null = null;
  private readonly limit: number;

  constructor(limit = 32) {
    this.limit = limit;
  }

  begin(turnId: string): void {
    this.active = turnId;
  }

  /** Mark a turn as interrupted and drop it from the active slot. */
  interrupt(turnId: string | null | undefined): void {
    if (!turnId) return;
    this.cancelled.add(turnId);
    if (this.active === turnId) this.active = null;
    while (this.cancelled.size > this.limit) {
      const oldest = this.cancelled.values().next().value;
      if (oldest === undefined) break;
      this.cancelled.delete(oldest);
    }
  }

  isCancelled(turnId: string | null | undefined): boolean {
    return Boolean(turnId && this.cancelled.has(turnId));
  }

  isActive(turnId: string | null | undefined): boolean {
    return Boolean(turnId && this.active === turnId);
  }

  get activeTurn(): string | null {
    return this.active;
  }

  /** A turn finished normally (or failed); it is no longer active. */
  settle(turnId: string | null | undefined): void {
    if (turnId && this.active === turnId) this.active = null;
  }

  reset(): void {
    this.cancelled.clear();
    this.active = null;
  }
}
