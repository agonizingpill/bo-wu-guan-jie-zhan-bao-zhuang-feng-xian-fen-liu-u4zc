CREATE TABLE IF NOT EXISTS convoy (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label text NOT NULL,
    vehicle text NOT NULL,
    begins_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL CHECK (ends_at > begins_at),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'dispatched')),
    roster_version integer NOT NULL DEFAULT 1 CHECK (roster_version >= 1),
    signed_by text REFERENCES staff,
    signed_reason text,
    signed_at timestamptz,
    signed_roster_version integer,
    signed_roster jsonb,
    created_by text NOT NULL REFERENCES staff,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((signed_by IS NULL) = (signed_roster_version IS NULL))
);
CREATE TABLE IF NOT EXISTS convoy_member (
    convoy_id bigint NOT NULL REFERENCES convoy,
    loan_id bigint NOT NULL REFERENCES exhibit_loan,
    added_by text NOT NULL REFERENCES staff,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (convoy_id, loan_id)
);
CREATE TABLE IF NOT EXISTS convoy_assessment (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    convoy_id bigint NOT NULL REFERENCES convoy,
    roster_version integer NOT NULL,
    roster jsonb NOT NULL,
    member_scores jsonb NOT NULL,
    combined_risk double precision NOT NULL CHECK (combined_risk BETWEEN 0 AND 1),
    threshold double precision NOT NULL,
    assessed_by text NOT NULL REFERENCES staff,
    assessed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS convoy_assessment_history ON convoy_assessment (convoy_id, id DESC);
CREATE TABLE IF NOT EXISTS dispatch_order (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    convoy_id bigint NOT NULL UNIQUE REFERENCES convoy,
    roster jsonb NOT NULL,
    roster_version integer NOT NULL,
    combined_risk double precision NOT NULL,
    signed_by text,
    vehicle text NOT NULL,
    begins_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    issued_by text NOT NULL REFERENCES staff,
    issued_at timestamptz NOT NULL DEFAULT now()
);
