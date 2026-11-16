import { lazy, Suspense } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { apiMode } from "./api/config";
import { usePublicAccess } from "./api/public-access";
import { useSession } from "./api/session";
import { BrandMark, Icon } from "./components/common/Icon";
import type { IconName } from "./components/common/Icon";

const MyZoneScreen = lazy(() => import("./screens/MyZoneScreen").then(({ MyZoneScreen }) => ({ default: MyZoneScreen })));
const CalendarScreen = lazy(() => import("./screens/CalendarScreen").then(({ CalendarScreen }) => ({ default: CalendarScreen })));
const RotationLabScreen = lazy(() => import("./screens/RotationLabScreen").then(({ RotationLabScreen }) => ({ default: RotationLabScreen })));
const HomeScreen = lazy(() => import("./screens/HomeScreen").then(({ HomeScreen }) => ({ default: HomeScreen })));
const DemoScreen = lazy(() => import("./screens/DemoScreen").then(({ DemoScreen }) => ({ default: DemoScreen })));
const MvpScreen = lazy(() => import("./screens/MvpScreen").then(({ MvpScreen }) => ({ default: MvpScreen })));
const PlantsScreen = lazy(() => import("./screens/PlantsScreen").then(({ PlantsScreen }) => ({ default: PlantsScreen })));
const ReportScreen = lazy(() => import("./screens/ReportScreen").then(({ ReportScreen }) => ({ default: ReportScreen })));

const navigation: ReadonlyArray<{ to: string; key: string; icon: IconName }> = [
  { to: "/mvp", key: "app.navigation.mvp", icon: "compare" },
  { to: "/my-zone", key: "app.navigation.myZone", icon: "location" },
  { to: "/calendar", key: "app.navigation.calendarChange", icon: "history" },
  { to: "/rotations", key: "app.navigation.rotationLab", icon: "sliders" },
  { to: "/report", key: "app.navigation.decisionReport", icon: "document" },
  { to: "/plants", key: "app.navigation.plants", icon: "crop" },
];

export function App() {
  const { t } = useTranslation();
  const location = useLocation();
  const search = location.search;
  const session = useSession();
  // The index and the demo launcher have their own full-bleed layout (no application top bar).
  const standalone = location.pathname === "/" || location.pathname === "/demo";
  // No sign-in anywhere: the public demo session is obtained silently for every in-app page.
  const access = usePublicAccess(!standalone);
  if (standalone) {
    return <Suspense fallback={<div className="state-card" role="status" aria-live="polite">{t("common.loading")}</div>}>
      <Routes>
        <Route path="/demo" element={<DemoScreen />} />
        <Route path="*" element={<HomeScreen />} />
      </Routes>
    </Suspense>;
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">{t("app.skipToContent")}</a>
    <header className="topbar">
      <Link className="brand" to="/" aria-label="MILPA RESILIENTE home">
        <span className="brand__mark" aria-hidden="true"><BrandMark /></span>
        <span><strong>{t("app.title")}</strong><small>3.3 · MVP</small></span>
      </Link>
      <nav className="primary-nav" aria-label={t("app.mainNavigation")}>
        {navigation.map(({ to, key, icon }) => <NavLink key={to} to={{ pathname: to, search }} className={({ isActive }) => `nav-link${isActive ? " is-active" : ""}`}>
          <Icon name={icon} size={18} /><span className="nav-link__label">{t(key)}</span>
        </NavLink>)}
      </nav>
    </header>
    {session?.demo && <div className="demo-banner" role="status">Public demo · the data are real NASA POWER / GPM IMERG series for an approximate test polygon in Chiquimula, Guatemala · parameters are sandbox values, so every result is provisional (evidence level C) · private data and administration are not available in the demo.</div>}
    {apiMode === "mock" && <div className="mock-mode-banner" role="status">{t("common.mockMode")}</div>}
    <main id="main-content" className="main-content" tabIndex={-1}>
      {access === "pending" && <div className="state-card" role="status" aria-live="polite">{t("common.loading")}</div>}
      {access === "unavailable" && <div className="state-card" role="alert"><strong>Public access is not enabled on this server.</strong> <span>Start the server with <code>DEMO_PUBLIC_ACCESS=true</code>.</span></div>}
      {access === "ready" && <Suspense fallback={<div className="state-card" role="status" aria-live="polite">{t("common.loading")}</div>}>
        <Routes>
          <Route path="/mvp" element={<MvpScreen />} />
          <Route path="/plants" element={<PlantsScreen />} />
          <Route path="/my-zone" element={<MyZoneScreen />} />
          <Route path="/calendar" element={<CalendarScreen />} />
          <Route path="/rotations" element={<RotationLabScreen />} />
          <Route path="/report" element={<ReportScreen />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>}
    </main>
    <footer className="app-footer">
      <span>{t("common.notAutomaticRecommendation")}</span>
      <span>{t("common.notExpectedYield")}</span>
    </footer>
  </div>;
}
