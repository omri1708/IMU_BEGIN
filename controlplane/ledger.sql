-- Postgres ledger for budgets/rates/prices
CREATE TABLE IF NOT EXISTS provider_budget (
  provider TEXT, month TEXT, spent NUMERIC, cap NUMERIC, PRIMARY KEY(provider,month)
);
CREATE TABLE IF NOT EXISTS prices (
  provider TEXT, model TEXT, pin NUMERIC, pout NUMERIC, updated_at TIMESTAMP DEFAULT now(), PRIMARY KEY(provider,model)
);
CREATE TABLE IF NOT EXISTS token_samples (
  provider TEXT, model TEXT, text TEXT, n INT, PRIMARY KEY(provider,model)
);
