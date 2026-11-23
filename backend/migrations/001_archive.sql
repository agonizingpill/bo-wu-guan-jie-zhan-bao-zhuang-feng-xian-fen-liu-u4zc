CREATE TABLE IF NOT EXISTS staff (
    username text PRIMARY KEY,
    display_name text NOT NULL,
    password_hash text NOT NULL,
    role text NOT NULL CHECK (role IN ('operator', 'supervisor', 'viewer'))
);
CREATE TABLE IF NOT EXISTS exhibit_loan (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    accession text NOT NULL UNIQUE,
    object_name text NOT NULL,
    lender text NOT NULL,
    gallery text NOT NULL,
    must_arrive timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'registered' CHECK (status IN (
        'registered', 'packing', 'triage_pending', 'ready', 'review_required',
        'sampling', 'hold', 'dispatched'
    )),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS crate_check (
    loan_id bigint PRIMARY KEY REFERENCES exhibit_loan,
    crate_code text NOT NULL UNIQUE,
    seal_code text UNIQUE,
    material text NOT NULL CHECK(material IN ('porcelain', 'paper', 'bronze')),
    packing text NOT NULL CHECK(packing IN ('foam', 'suspension', 'double_wall')),
    route_type text NOT NULL CHECK(route_type IN ('direct', 'transfer', 'mountain')),
    max_rh integer NOT NULL CHECK(max_rh BETWEEN 0 AND 100),
    transfers integer NOT NULL CHECK(transfers BETWEEN 0 AND 8),
    noted_by text NOT NULL REFERENCES staff,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS transit_window (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loan_id bigint REFERENCES exhibit_loan,
    gallery text NOT NULL,
    vehicle text,
    label text NOT NULL,
    begins_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL CHECK (ends_at > begins_at),
    status text NOT NULL CHECK (status IN ('setup', 'booked', 'conflict', 'superseded', 'dispatched')),
    conflict_reason text,
    recorded_by text NOT NULL REFERENCES staff,
    CHECK ((status = 'setup' AND loan_id IS NULL AND vehicle IS NULL) OR
           (status <> 'setup' AND loan_id IS NOT NULL AND vehicle IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS current_transit_window ON transit_window (loan_id)
    WHERE status IN ('booked', 'conflict', 'dispatched');
CREATE UNIQUE INDEX IF NOT EXISTS setup_window_natural ON transit_window (gallery, begins_at, ends_at)
    WHERE status = 'setup';
CREATE TABLE IF NOT EXISTS triage_case (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loan_id bigint NOT NULL UNIQUE REFERENCES exhibit_loan,
    status text NOT NULL CHECK (status IN ('queued', 'scored', 'failed')),
    input_snapshot jsonb NOT NULL,
    probability double precision CHECK(probability BETWEEN 0 AND 1),
    risk text CHECK(risk IN ('low', 'high')),
    evidence jsonb,
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts >= 0),
    error text,
    requested_by text NOT NULL REFERENCES staff,
    created_at timestamptz NOT NULL DEFAULT now(),
    computed_at timestamptz
);
CREATE TABLE IF NOT EXISTS unpack_review (
    case_id bigint PRIMARY KEY REFERENCES triage_case,
    status text NOT NULL CHECK (status IN ('awaiting_witness', 'awaiting_supervisor', 'sampling', 'held', 'cleared')),
    witness_by text REFERENCES staff,
    witness_note text,
    witnessed_at timestamptz,
    supervisor_by text REFERENCES staff,
    decision_reason text,
    decided_at timestamptz,
    sample_by text REFERENCES staff,
    sample_seal text,
    sampled_at timestamptz,
    CHECK (witness_by IS DISTINCT FROM supervisor_by OR witness_by IS NULL),
    CHECK (supervisor_by IS DISTINCT FROM sample_by OR supervisor_by IS NULL)
);
CREATE TABLE IF NOT EXISTS audit_entry (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loan_id bigint REFERENCES exhibit_loan,
    actor text NOT NULL,
    action text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}',
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS loan_audit_history ON audit_entry (loan_id, id DESC);
