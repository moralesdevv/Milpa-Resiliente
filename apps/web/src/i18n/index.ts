import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import es from "./es.json";

const language = typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("en")
  ? "en"
  : "es";

void i18n.use(initReactI18next).init({
  resources: {
    es: { translation: es },
    en: { translation: en },
  },
  lng: language,
  fallbackLng: "es",
  interpolation: { escapeValue: false },
  returnNull: false,
});

if (typeof document !== "undefined") {
  document.documentElement.lang = language;
  i18n.on("languageChanged", (nextLanguage) => {
    document.documentElement.lang = nextLanguage.split("-")[0] || "es";
  });
}

export default i18n;
