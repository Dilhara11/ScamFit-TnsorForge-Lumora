/**
 * Client-generated idempotency IDs. The server accepts 1–128 characters from
 * `A-Z a-z 0-9 . _ ~ -`; reusing an ID on retry returns the stored result.
 */
export function newId(prefix: string) {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  const rand = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${prefix}-${Date.now().toString(36)}-${rand}`;
}
