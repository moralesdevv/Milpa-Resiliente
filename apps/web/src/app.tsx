import { lazy, Suspense } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import i18n from "./i18n";
import { apiMode } from "./api/config";
import { SessionControl } from "./components/auth/SessionControl";
import { BrandMark, Icon } from "./components/common/Icon";
import type { IconName } from "./components/common/Icon";

const MyZoneScreen = lazy(() => import("./screens/MyZoneScreen").then(({ MyZoneScreen }) => ({ default: MyZoneScreen })));
const CalendarScreen = lazy(() => import("./screens/CalendarScreen").then(({ CalendarScreen }) => ({ default: CalendarScreen })));
const RotationLabScreen = lazy(() => import("./screens/RotationLabScreen").then(({ RotationLabScreen }) => ({ default: RotationLabScreen })));
const ReportScreen = lazy(() => import("./screens/ReportScreen").then(({ ReportScreen }) => ({ default: ReportScreen })));

const navigation: ReadonlyArray<{ to: string; key: string; icon: IconName }> = [
  { to: "/my-zone", key: "app.navigation.myZone", icon: "location" },
  { to: "/calendar", key: "app.navigation.calendarChange", icon: "history" },
  { to: "/rotations", key: "app.navigation.rotationLab", icon: "sliders" },
  { to: "/report", key: "app.navigation.decisionReport", icon: "document" },
];

export function App() {
  const { t } = useTranslation();
  const location = useLocation();
  const search = location.search;

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">{t("app.skipToContent")}</a>
    <header className="topbar">
      <Link className="brand" to={{ pathname: "/my-zone", search }}>
        <span className="brand__mark" aria-hidden="true"><BrandMark /></span>
        <span><strong>{t("app.title")}</strong><small>3.3 · R4</small></span>
      </Link>
      <nav className="primary-nav" aria-label={t("app.mainNavigation")}>
        {navigation.map(({ to, key, icon }) => <NavLink key={to} to={{ pathname: to, search }} className={({ isActive }) => `nav-link${isActive ? " is-active" : ""}`}>
          <Icon name={icon} size={18} /><span className="nav-link__label">{t(key)}</span>
        </NavLink>)}
      </nav>
      <div className="topbar__tools">
        <label className="language-picker"><span>{t("app.language")}</span>
          <select aria-label={t("app.language")} value={i18n.language.startsWith("en") ? "en" : "es"} onChange={(event) => void i18n.changeLanguage(event.currentTarget.value)}>
            <option value="es">{t("app.spanish")}</option><option value="en">{t("app.english")}</option>
          </select>
        </label>
        <SessionControl />
      </div>
    </header>
    {apiMode === "mock" && <div className="mock-mode-banner" role="status">{t("common.mockMode")}</div>}
    <main id="main-content" className="main-content" tabIndex={-1}>
      <Suspense fallback={<div className="state-card" role="status" aria-live="polite">{t("common.loading")}</div>}>
        <Routes>
          <Route path="/" element={<Navigate to={{ pathname: "/my-zone", search }} replace />} />
          <Route path="/my-zone" element={<MyZoneScreen />} />
          <Route path="/calendar" element={<CalendarScreen />} />
          <Route path="/rotations" element={<RotationLabScreen />} />
          <Route path="/report" element={<ReportScreen />} />
          <Route path="*" element={<Navigate to={{ pathname: "/my-zone", search }} replace />} />
        </Routes>
      </Suspense>
    </main>
    <footer className="app-footer">
      <span>{t("common.notAutomaticRecommendation")}</span>
      <span>{t("common.notExpectedYield")}</span>
    </footer>
  </div>;
}
