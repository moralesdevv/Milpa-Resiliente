-- OWNER: R3. README §13.3. Extensiones R3 marcadas con "R3-EXT".
CREATE TABLE auth.app_user (
  user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  role user_role_t NOT NULL,
  disabled_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),                       -- R3-EXT (auditoría)
  failed_login_count smallint NOT NULL DEFAULT 0,                      -- R3-EXT (bloqueo progresivo)
  last_failed_login_at timestamptz,                                    -- R3-EXT
  locked_until timestamptz,                                            -- R3-EXT
  CONSTRAINT app_user_email_lower CHECK (email = lower(email))
);

CREATE TABLE auth.consent (
  consent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_user_id uuid NOT NULL REFERENCES auth.app_user,
  purpose text NOT NULL CHECK (purpose IN ('analysis','report_sharing','exact_geometry')),
  text_version text NOT NULL,
  granted_at timestamptz NOT NULL,
  withdrawn_at timestamptz,
  CHECK (withdrawn_at IS NULL OR withdrawn_at >= granted_at)
);
-- R3-EXT: un solo consentimiento vigente por sujeto y propósito.
CREATE UNIQUE INDEX consent_one_active ON auth.consent (subject_user_id, purpose) WHERE withdrawn_at IS NULL;

-- R3-EXT: bitácora de auditoría mínima. Solo identificadores técnicos y fecha (spec R3 §9.7).
CREATE TABLE auth.audit_log (
  audit_id bigserial PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid,
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id uuid,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);
