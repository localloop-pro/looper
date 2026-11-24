-- Onboard join-code SMS send ledger (rolling per-mobile cap + daily global cap).
-- Applied automatically by models.init_db() — safe to run manually on production once.
CREATE TABLE IF NOT EXISTS onboard_sms_sends (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    mobile_key VARCHAR(64) NOT NULL,
    sent_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_onboard_sms_sends_mobile_key ON onboard_sms_sends (mobile_key);
CREATE INDEX IF NOT EXISTS ix_onboard_sms_sends_sent_at ON onboard_sms_sends (sent_at);