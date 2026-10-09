/**
 * Small, dependency-free input mask helpers (CNPJ, CPF, e-mail, phone, CEP).
 *
 * All functions are pure and safe to use directly in `onChange` handlers:
 * they keep only the meaningful characters, apply the mask progressively
 * (so the user sees the separators while typing) and never throw.
 */

/** Keep only digits from a raw input value. */
export function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}

/** Progressive CPF mask: 000.000.000-00 (max 11 digits). */
export function maskCpf(value: string): string {
  const d = onlyDigits(value).slice(0, 11);
  if (d.length <= 3) return d;
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`;
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`;
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`;
}

/** Progressive CNPJ mask: 00.000.000/0000-00 (max 14 digits). */
export function maskCnpj(value: string): string {
  const d = onlyDigits(value).slice(0, 14);
  if (d.length <= 2) return d;
  if (d.length <= 5) return `${d.slice(0, 2)}.${d.slice(2)}`;
  if (d.length <= 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`;
  if (d.length <= 12)
    return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

/**
 * Progressive CPF/CNPJ mask. Switches automatically to the CNPJ layout once the
 * value exceeds 11 digits — convenient for a single "CPF/CNPJ" field.
 */
export function maskCpfCnpj(value: string): string {
  const d = onlyDigits(value);
  return d.length > 11 ? maskCnpj(value) : maskCpf(value);
}

/** Progressive Brazilian phone mask: (00) 0000-0000 / (00) 00000-0000. */
export function maskPhone(value: string): string {
  const d = onlyDigits(value).slice(0, 11);
  if (d.length === 0) return "";
  if (d.length <= 2) return `(${d}`;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10)
    return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

/** Progressive CEP mask: 00000-000 (max 8 digits). */
export function maskZipCode(value: string): string {
  const d = onlyDigits(value).slice(0, 8);
  if (d.length <= 5) return d;
  return `${d.slice(0, 5)}-${d.slice(5)}`;
}

/**
 * Light e-mail normalisation: trims, removes spaces and keeps only the
 * characters allowed in an e-mail address (no domain masking, just hygiene).
 */
export function maskEmail(value: string): string {
  return value.replace(/\s+/g, "").replace(/[^A-Za-z0-9@._%+\-]/g, "");
}

/**
 * Uppercase + strip non-letters, for the 2-character UF field (e.g. "SP").
 */
export function maskUf(value: string): string {
  return value
    .replace(/[^A-Za-z]/g, "")
    .toUpperCase()
    .slice(0, 2);
}
