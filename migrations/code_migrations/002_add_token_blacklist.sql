-- ================================================
-- Migration: Add Token Blacklist Table
-- Version: 2.0
-- Date: 2025-11-03
-- Environment: LOCAL DEVELOPMENT
-- Description: Enable logout and token revocation
-- ================================================

USE hrm_db;
GO

PRINT '========================================';
PRINT 'STARTING TOKEN BLACKLIST MIGRATION';
PRINT 'Timestamp: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '========================================';
PRINT '';

-- ================================================
-- STEP 1: Create token_blacklist table
-- ================================================
PRINT '→ Step 1: Creating token_blacklist table...';

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'token_blacklist')
BEGIN
    CREATE TABLE token_blacklist (
        id INT PRIMARY KEY IDENTITY(1,1),
        jti NVARCHAR(50) NOT NULL UNIQUE,
        user_id INT NOT NULL,
        username NVARCHAR(15) NOT NULL,
        blacklisted_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        token_exp DATETIME NOT NULL,
        reason NVARCHAR(50) DEFAULT 'user_logout',
        
        CONSTRAINT FK_token_blacklist_user_id 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    
    PRINT '  ✓ Token blacklist table created';
END
ELSE
BEGIN
    PRINT '  ! Token blacklist table already exists';
END
GO

-- ================================================
-- STEP 2: Create indexes for performance
-- ================================================
PRINT '';
PRINT '→ Step 2: Creating indexes...';

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_blacklist_jti' AND object_id = OBJECT_ID('token_blacklist'))
BEGIN
    CREATE INDEX idx_blacklist_jti ON token_blacklist(jti);
    PRINT '  ✓ Index on jti created';
END

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_blacklist_user_id' AND object_id = OBJECT_ID('token_blacklist'))
BEGIN
    CREATE INDEX idx_blacklist_user_id ON token_blacklist(user_id);
    PRINT '  ✓ Index on user_id created';
END

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_blacklist_exp' AND object_id = OBJECT_ID('token_blacklist'))
BEGIN
    CREATE INDEX idx_blacklist_exp ON token_blacklist(token_exp);
    PRINT '  ✓ Index on token_exp created';
END
GO

-- ================================================
-- STEP 3: Verification
-- ================================================
PRINT '';
PRINT '========================================';
PRINT 'MIGRATION VERIFICATION';
PRINT '========================================';
PRINT '';

SELECT 
    'token_blacklist' as table_name,
    COUNT(*) as row_count,
    (SELECT COUNT(*) FROM sys.indexes WHERE object_id = OBJECT_ID('token_blacklist')) as index_count,
    (SELECT COUNT(*) FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID('token_blacklist')) as fk_count
FROM token_blacklist;

PRINT '';
PRINT '→ Summary:';
PRINT '  Table: token_blacklist';
PRINT '  Indexes: 3 (jti, user_id, token_exp)';
PRINT '  Foreign Keys: 1 (user_id -> users.id)';

PRINT '';
PRINT '========================================';
PRINT '✓✓✓ MIGRATION COMPLETED SUCCESSFULLY ✓✓✓';
PRINT 'Timestamp: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '========================================';
GO
