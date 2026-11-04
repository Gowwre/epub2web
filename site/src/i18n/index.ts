import { DEFAULT_LOCALE, isLocale, type Locale } from "./config";
import { en, type Copy } from "./en";
import { vi } from "./vi";

export {
  DEFAULT_LOCALE,
  LOCALE_LABELS,
  LOCALES,
  alternateLocale,
  alternateLocalePath,
  isLocale,
  localeHref,
  localePath,
} from "./config";
export type { Locale } from "./config";
export type { Copy } from "./en";

const copies: Record<Locale, Copy> = { en, vi };

export function getCopy(locale: string | undefined): Copy {
  return copies[isLocale(locale) ? locale : DEFAULT_LOCALE];
}
