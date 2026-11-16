import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { useLogin } from "../../api/queries";
import { setSession, useSession } from "../../api/session";
import { ErrorState } from "../common/states";

/** Sign-in control for the top bar. The token stays in sessionStorage only. */
export function SessionControl() {
  const { t } = useTranslation();
  const session = useSession();
  const login = useLogin();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    login.mutate({ email, password }, {
      onSuccess: (data) => {
        setSession({ token: data.access_token, role: data.role, expiresInSeconds: data.expires_in });
        setPassword("");
        setOpen(false);
      },
    });
  };

  if (session) {
    return <div className="session-control" data-testid="session-control">
      <span className="session-control__role">{t("auth.signedInAs", { role: t(`auth.roles.${session.role}`, session.role) })}</span>
      <button className="button button--secondary button--compact" type="button" onClick={() => { setSession(null); login.reset(); }}>{t("auth.signOut")}</button>
    </div>;
  }

  return <div className="session-control" data-testid="session-control">
    <button className="button button--secondary button--compact" type="button" aria-expanded={open} aria-controls="login-panel" onClick={() => setOpen((value) => !value)}>
      {t("auth.signIn")}
    </button>
    {open && <form id="login-panel" className="login-panel" onSubmit={submit} aria-label={t("auth.signIn")}>
      <label className="field"><span>{t("auth.email")}</span>
        <input type="email" name="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.currentTarget.value)} />
      </label>
      <label className="field"><span>{t("auth.password")}</span>
        <input type="password" name="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.currentTarget.value)} />
      </label>
      <button className="button" type="submit" disabled={login.isPending}>{login.isPending ? t("common.loading") : t("auth.submit")}</button>
      {login.isError && <ErrorState error={login.error} />}
      <p className="chart-caption">{t("auth.readOnlyNote")}</p>
    </form>}
  </div>;
}
