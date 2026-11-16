import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import es from "./es.json";

// The product is English-only (NASA Space Apps audience); Spanish resources remain for reference.
const language = "en";

void i18n.use(initReactI18next).init({
  resources: {
    es: { translation: es },
    en: { translation: en },
  },
  lng: language,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

if (typeof document !== "undefined") {
  document.documentElement.lang = language;
  i18n.on("languageChanged", (nextLanguage) => {
    document.documentElement.lang = nextLanguage.split("-")[0] || "en";
  });
}

export default i18n;
