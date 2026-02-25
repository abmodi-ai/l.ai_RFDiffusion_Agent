/**
 * Parse option blocks from the end of an assistant markdown message.
 *
 * Handles multiple formats the agent may produce:
 *   Format A (numbered):   1. **Label** — description
 *   Format B (numbered):   1. **Label** (extra info) — description
 *   Format C (unnumbered): **Label** — description
 *   Format D (unnumbered): **Label** (extra info) — description
 *
 * Options may be followed by trailing commentary/question lines.
 */

export interface ParsedOption {
  /** Display number (auto-assigned if unnumbered) */
  number: number;
  /** The bold label text */
  label: string;
  /** Optional description after the dash */
  description: string;
  /** Whether this is a freeform / "something else" option */
  isFreeform: boolean;
}

export interface ParsedMessageContent {
  /** Everything above the options block */
  bodyMarkdown: string;
  /** Extracted options (empty array if none found) */
  options: ParsedOption[];
}

// Labels that indicate the user should type their own response
const FREEFORM_RE = /^(something else|other|tell me|custom|specify|my own|i have|describe|explain)/i;

/**
 * Extract the description from text after the bold label.
 * Finds the LAST em-dash (—) or en-dash (–) and takes everything after it.
 * This avoids false matches on en-dashes inside parentheticals like (25–30).
 */
function extractDescription(afterLabel: string): string {
  // Find last em-dash or en-dash that acts as separator
  // Use greedy .* to skip past any dashes inside parentheticals
  const match = afterLabel.match(/.*[—–]\s*(.+)$/);
  return match ? match[1].trim() : '';
}

/**
 * Try to match a line as an option. Handles:
 *  - "1. **Label** (extra) — desc"  (numbered)
 *  - "**Label** (extra) — desc"     (unnumbered)
 */
function matchOptionLine(
  trimmed: string,
): { label: string; description: string; explicitNumber?: number } | null {
  // Numbered: "N. **Label** ..."
  let m = trimmed.match(/^(\d+)\.\s+\*\*(.+?)\*\*(.*)$/);
  if (m) {
    return {
      explicitNumber: parseInt(m[1], 10),
      label: m[2].trim(),
      description: extractDescription(m[3]),
    };
  }

  // Unnumbered: "**Label** ..."
  m = trimmed.match(/^\*\*(.+?)\*\*(.*)$/);
  if (m) {
    return {
      label: m[1].trim(),
      description: extractDescription(m[2]),
    };
  }

  return null;
}

export function parseMessageOptions(content: string): ParsedMessageContent {
  const lines = content.split('\n');

  // Walk backward from the last non-empty line
  let end = lines.length - 1;
  while (end >= 0 && lines[end].trim() === '') {
    end--;
  }

  if (end < 0) {
    return { bodyMarkdown: content, options: [] };
  }

  // Skip trailing non-option lines (recommendations, questions, etc.)
  // Allow up to 3 trailing non-option lines after the options block
  let trailingEnd = end;
  let trailingCount = 0;
  while (trailingEnd >= 0 && trailingCount < 3) {
    const trimmed = lines[trailingEnd].trim();
    if (trimmed === '') {
      trailingEnd--;
      continue;
    }
    if (matchOptionLine(trimmed)) {
      break; // Found an option line, stop skipping
    }
    trailingCount++;
    trailingEnd--;
  }

  if (trailingEnd < 0) {
    return { bodyMarkdown: content, options: [] };
  }

  // Now walk backward from trailingEnd to find contiguous option lines
  let start = trailingEnd;
  const optionLines: { index: number; label: string; description: string; explicitNumber?: number }[] = [];

  while (start >= 0) {
    const trimmed = lines[start].trim();
    if (trimmed === '') {
      start--;
      continue;
    }
    const parsed = matchOptionLine(trimmed);
    if (parsed) {
      optionLines.unshift({ index: start, ...parsed });
      start--;
    } else {
      break;
    }
  }

  // Require at least 2 option lines to be considered a valid option block
  if (optionLines.length < 2) {
    return { bodyMarkdown: content, options: [] };
  }

  const firstOptionIndex = optionLines[0].index;
  const bodyMarkdown = lines.slice(0, firstOptionIndex).join('\n').trimEnd();

  const options: ParsedOption[] = optionLines.map((opt, i) => ({
    number: opt.explicitNumber ?? i + 1,
    label: opt.label,
    description: opt.description,
    isFreeform: FREEFORM_RE.test(opt.label),
  }));

  return { bodyMarkdown, options };
}
