-- QueryMind - Banco de produção: Corretora "SeguraPro"
-- 16 tabelas, PostgreSQL 16

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE brokers (
    id SERIAL PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    registration_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    phone VARCHAR(20),
    hire_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','inactive','on_leave')),
    commission_rate DECIMAL(5,2) NOT NULL DEFAULT 10.00,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    client_type VARCHAR(2) NOT NULL CHECK (client_type IN ('PF','PJ')),
    document_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(300) NOT NULL,
    trade_name VARCHAR(300),
    email VARCHAR(200),
    phone VARCHAR(20),
    birth_date DATE,
    address_street VARCHAR(300),
    address_number VARCHAR(20),
    address_complement VARCHAR(100),
    address_neighborhood VARCHAR(100),
    address_city VARCHAR(100) NOT NULL DEFAULT 'Fortaleza',
    address_state VARCHAR(2) NOT NULL DEFAULT 'CE',
    address_zip VARCHAR(10),
    broker_id INTEGER REFERENCES brokers(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','inactive','prospect')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE insurers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    cnpj VARCHAR(20) UNIQUE NOT NULL,
    susep_code VARCHAR(20),
    website VARCHAR(200),
    contact_email VARCHAR(200),
    contact_phone VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','inactive','suspended')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE insurance_branches (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    susep_group VARCHAR(50) NOT NULL
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    insurer_id INTEGER NOT NULL REFERENCES insurers(id),
    branch_id INTEGER NOT NULL REFERENCES insurance_branches(id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    min_premium DECIMAL(12,2),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','inactive','discontinued')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE policies (
    id SERIAL PRIMARY KEY,
    policy_number VARCHAR(30) UNIQUE NOT NULL,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    premium_amount DECIMAL(12,2) NOT NULL,
    insured_amount DECIMAL(14,2) NOT NULL,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'boleto'
        CHECK (payment_method IN ('boleto','cartao_credito','debito_conta','pix')),
    installments INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','expired','cancelled','pending','renewed')),
    issued_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CHECK (end_date > start_date)
);

CREATE TABLE policy_coverages (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id),
    coverage_name VARCHAR(200) NOT NULL,
    coverage_amount DECIMAL(14,2) NOT NULL,
    deductible DECIMAL(12,2) NOT NULL DEFAULT 0,
    is_main BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE endorsements (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id),
    endorsement_number VARCHAR(30) NOT NULL,
    type VARCHAR(30) NOT NULL
        CHECK (type IN ('inclusion','exclusion','modification','cancellation')),
    description TEXT,
    premium_difference DECIMAL(12,2) NOT NULL DEFAULT 0,
    effective_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE claims (
    id SERIAL PRIMARY KEY,
    claim_number VARCHAR(30) UNIQUE NOT NULL,
    policy_id INTEGER NOT NULL REFERENCES policies(id),
    occurrence_date DATE NOT NULL,
    notification_date DATE NOT NULL,
    description TEXT NOT NULL,
    estimated_loss DECIMAL(14,2),
    approved_amount DECIMAL(14,2),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','in_analysis','approved','denied','paid','closed')),
    denial_reason TEXT,
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    CHECK (notification_date >= occurrence_date)
);

CREATE TABLE claim_documents (
    id SERIAL PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    document_type VARCHAR(50) NOT NULL
        CHECK (document_type IN ('boletim_ocorrencia','laudo_pericial',
            'foto','nota_fiscal','orcamento','receita_medica','outros')),
    file_name VARCHAR(300) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE commissions (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    commission_rate DECIMAL(5,2) NOT NULL,
    commission_amount DECIMAL(12,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','paid','cancelled')),
    due_date DATE,
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id),
    installment_number INTEGER NOT NULL,
    due_date DATE NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    paid_amount DECIMAL(12,2),
    paid_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','paid','overdue','cancelled')),
    payment_method VARCHAR(30),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quotes (
    id SERIAL PRIMARY KEY,
    quote_number VARCHAR(30) UNIQUE NOT NULL,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    branch_id INTEGER NOT NULL REFERENCES insurance_branches(id),
    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
    valid_until DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','sent','accepted','rejected','expired')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quote_items (
    id SERIAL PRIMARY KEY,
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    insurer_id INTEGER NOT NULL REFERENCES insurers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    premium_amount DECIMAL(12,2) NOT NULL,
    insured_amount DECIMAL(14,2) NOT NULL,
    is_selected BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indices
CREATE INDEX idx_brokers_dept ON brokers(department_id);
CREATE INDEX idx_clients_broker ON clients(broker_id);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_products_insurer ON products(insurer_id);
CREATE INDEX idx_products_branch ON products(branch_id);
CREATE INDEX idx_policies_client ON policies(client_id);
CREATE INDEX idx_policies_broker ON policies(broker_id);
CREATE INDEX idx_policies_status ON policies(status);
CREATE INDEX idx_policies_dates ON policies(start_date, end_date);
CREATE INDEX idx_coverages_policy ON policy_coverages(policy_id);
CREATE INDEX idx_endorsements_policy ON endorsements(policy_id);
CREATE INDEX idx_claims_policy ON claims(policy_id);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_commissions_broker ON commissions(broker_id);
CREATE INDEX idx_commissions_status ON commissions(status);
CREATE INDEX idx_payments_policy ON payments(policy_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_due ON payments(due_date);
CREATE INDEX idx_quotes_client ON quotes(client_id);
CREATE INDEX idx_quotes_broker ON quotes(broker_id);
CREATE INDEX idx_quote_items_quote ON quote_items(quote_id);
