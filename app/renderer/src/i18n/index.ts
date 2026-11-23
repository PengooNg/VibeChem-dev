// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/i18n/index.ts — i18next set-up with the bundled EN/JA/VI string files.
import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./en/common.json";
import jaCommon from "./ja/common.json";
import viCommon from "./vi/common.json";

export const LANGUAGES = ["en", "ja", "vi"] as const;
export type Language = (typeof LANGUAGES)[number];

export const resources = {
  en: { common: enCommon },
  ja: { common: jaCommon },
  vi: { common: viCommon },
} as const;

void i18next.use(initReactI18next).init({
  resources,
  lng: "en",
  fallbackLng: "en",
  supportedLngs: LANGUAGES,
  defaultNS: "common",
  interpolation: { escapeValue: false }, // React already escapes rendered text
});

export default i18next;
