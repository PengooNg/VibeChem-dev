// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/App.tsx — root component: an empty window that shows the app name in each language.
import { useTranslation } from "react-i18next";

import { LANGUAGES } from "./i18n";

export function App() {
  const { i18n } = useTranslation();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      {LANGUAGES.map((lng) => {
        const t = i18n.getFixedT(lng);
        return (
          <section key={lng} lang={lng} className="text-center">
            <h1 className="text-xl font-semibold">{t("app.name")}</h1>
            <p className="text-muted-foreground">{t("app.tagline")}</p>
          </section>
        );
      })}
    </main>
  );
}
