-- ============================================================================
-- PASSWORD RESET TOKENS TABLE MIGRATION
-- Date: 2025-11-17
-- Purpose: Add password reset functionality via email OTP
-- Safe: Yes (only creates new table, no existing table modifications)
-- ============================================================================

-- Create password_reset_tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    -- Primary key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- User identification
    user_id INTEGER NOT NULL,
    email VARCHAR(255) NOT NULL,
    
    -- OTP code (6 digits like "482916")
    otp_code VARCHAR(6),
    
    -- Token for link-based reset (future feature)
    token VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    
    -- Status tracking
    is_used BOOLEAN DEFAULT 0,
    used_at TIMESTAMP NULL,
    
    -- Audit trail
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Foreign key relationship
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_password_reset_otp_code ON password_reset_tokens(otp_code);
CREATE INDEX IF NOT EXISTS idx_password_reset_email ON password_reset_tokens(email);
CREATE INDEX IF NOT EXISTS idx_password_reset_expires_at ON password_reset_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_is_used ON password_reset_tokens(is_used);
CREATE INDEX IF NOT EXISTS idx_password_reset_user_id ON password_reset_tokens(user_id);

-- Verification query (run this to confirm table was created)
SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset_tokens';
