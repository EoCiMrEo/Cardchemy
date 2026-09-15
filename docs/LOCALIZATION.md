# Localization policy

Cardchemy v1 supports English only. All user-facing frontend copy lives in the
typed catalog at `frontend/src/i18n/en.ts`; components reference catalog keys
instead of embedding prose. This keeps wording consistent and creates a stable
contract for future locale files without adding an i18n runtime before a second
language is approved.

Before adding another language:

1. Add a catalog with the same shape as the English catalog and validate it with
   TypeScript's `satisfies` operator.
2. Add an explicit locale-selection and fallback policy, including persisted
   preference, browser-language behavior, and server-rendered/error copy.
3. Use `Intl` for locale-sensitive dates, numbers, plurals, and currency; do not
   translate by concatenating sentence fragments.
4. Add browser coverage for selection, fallback, interpolation, long text, and
   missing keys.

Backend error details remain server-owned English diagnostics for v1. The
frontend presents them through the bounded API error parser and uses catalog
fallbacks whenever a response is absent or unsafe.
