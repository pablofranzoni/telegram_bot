-- Registra intentos de login para rate limiting.
-- La tabla es idempotente: CREATE IF NOT EXISTS permite reejecutarla sin errores.

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address TEXT NOT NULL,
    username TEXT,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time
    ON login_attempts(ip_address, attempted_at);

CREATE INDEX IF NOT EXISTS idx_login_attempts_user_time
    ON login_attempts(username, attempted_at);
