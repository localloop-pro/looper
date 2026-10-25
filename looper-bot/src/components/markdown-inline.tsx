import type { ReactNode } from "react";

export function renderInline(text: string) {
  const parts: ReactNode[] = [];
  // Consume escaped delimiters before attempting link recognition. Cell text
  // must never become a link merely because it contains markdown syntax.
  const linkRegex = /\\([|\[\]`])|\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = linkRegex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    if (match[1] !== undefined) {
      parts.push(match[1]);
    } else {
      parts.push(
        <a href={match[3]} key={`${match[3]}-${match.index}`} target="_blank" rel="noreferrer">
          {match[2]}
        </a>,
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length > 0 ? parts : text;
}

