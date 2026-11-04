import { withBase } from "../consts";

export const LOCALES = ["en", "vi"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  vi: "Tiếng Việt",
};

export function isLocale(value: string | undefined): value is Locale {
  return value === "en" || value === "vi";
}

/** Prefix a canonical route with the locale segment and base path. */
export function localePath(locale: Locale, path = "/"): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (locale === "en") return withBase(normalized);
  return withBase(normalized === "/" ? "/vi/" : `/vi${normalized}`);
}

/** Localize an internal href while preserving a hash fragment. */
export function localeHref(locale: Locale, href: string): string {
  if (!href.startsWith("/") || href.startsWith("//")) return href;
  const hashIndex = href.indexOf("#");
  const path = hashIndex === -1 ? href : href.slice(0, hashIndex);
  const hash = hashIndex === -1 ? "" : href.slice(hashIndex);
  return `${localePath(locale, path)}${hash}`;
}

export function alternateLocale(locale: Locale): Locale {
  return locale === "vi" ? "en" : "vi";
}

export function alternateLocalePath(locale: Locale, path = "/"): string {
  return localePath(alternateLocale(locale), path);
}
