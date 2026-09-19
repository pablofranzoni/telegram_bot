-- Registra intentos de login para rate limiting.
-- La tabla es idempotente: CREATE IF NOT EXISTS permite reejecutarla sin errores.

CREATE TABLE IF NOT EXISTS login_attempts (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,
    username VARCHAR(255),
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time
    ON login_attempts(ip_address, attempted_at);

CREATE INDEX IF NOT EXISTS idx_login_attempts_user_time
    ON login_attempts(username, attempted_at);
