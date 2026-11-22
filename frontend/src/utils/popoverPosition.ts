/**
 * Top edge for a popover anchored at a word: just below it when the whole popover fits there, else
 * above it, else pinned to the bottom margin so the footer (the save button) stays on screen. A popover
 * taller than the viewport starts at the top margin; the caller caps its height so it can scroll inside.
 */
export function popoverTop(anchorY: number, height: number, viewportHeight: number, gap = 12, margin = 16): number {
  const below = Math.max(margin, anchorY + gap);
  if (below + height <= viewportHeight - margin) return below;
  const above = anchorY - height - gap;
  if (above >= margin) return above;
  return Math.max(margin, viewportHeight - height - margin);
}
