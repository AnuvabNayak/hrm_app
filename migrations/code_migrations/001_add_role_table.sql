-- ================================================
-- Migration: Add Role Table and Update User Table
-- Version: 1.0
-- Date: 2025-11-03
-- Environment: LOCAL DEVELOPMENT ONLY
-- Description: Separate roles into dedicated table with FK relationship
-- ================================================

USE hrm_db;
GO

PRINT '========================================';
PRINT 'STARTING ROLE TABLE MIGRATION';
PRINT 'Timestamp: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '========================================';
PRINT '';

-- ================================================
-- STEP 1: Create roles table
-- ================================================
PRINT '→ Step 1: Creating roles table...';

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'roles')
BEGIN
    CREATE TABLE roles (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(50) NOT NULL UNIQUE,
        display_name NVARCHAR(100) NOT NULL,
        description NVARCHAR(255),
        level INT NOT NULL DEFAULT 0,
        is_active BIT DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE()
    );
    
    -- Create index on name for fast role lookups
    CREATE INDEX idx_roles_name ON roles(name);
    
    PRINT '  ✓ Roles table created successfully';
END
ELSE
BEGIN
    PRINT '  ! Roles table already exists, skipping creation';
END
GO

-- ================================================
-- STEP 2: Insert predefined system roles
-- ================================================
PRINT '';
PRINT '→ Step 2: Inserting system roles...';

IF NOT EXISTS (SELECT * FROM roles WHERE name = 'employee')
BEGIN
    SET IDENTITY_INSERT roles ON;
    
    INSERT INTO roles (id, name, display_name, description, level, is_active) VALUES
    (1, 'employee', 'Employee', 'Regular employee with basic access to attendance, leave, and posts', 0, 1),
    (2, 'admin', 'Administrator', 'Department admin with management and approval privileges', 50, 1),
    (3, 'super_admin', 'Super Administrator', 'System administrator with full access to all features', 100, 1);
    
    SET IDENTITY_INSERT roles OFF;
    
    PRINT '  ✓ Inserted 3 system roles (employee, admin, super_admin)';
END
ELSE
BEGIN
    PRINT '  ! System roles already exist, skipping insert';
END
GO

-- ================================================
-- STEP 3: Add role_id column to users table
-- ================================================
PRINT '';
PRINT '→ Step 3: Adding role_id column to users table...';

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('users') AND name = 'role_id')
BEGIN
    ALTER TABLE users ADD role_id INT NULL;
    PRINT '  ✓ role_id column added (nullable for migration)';
END
ELSE
BEGIN
    PRINT '  ! role_id column already exists';
END
GO

-- ================================================
-- STEP 4: Migrate existing user roles to role_id
-- ================================================
PRINT '';
PRINT '→ Step 4: Migrating existing role data...';

DECLARE @employeeCount INT = 0;
DECLARE @adminCount INT = 0;
DECLARE @superAdminCount INT = 0;
DECLARE @unmappedCount INT = 0;

-- Count before migration
SELECT @employeeCount = COUNT(*) FROM users WHERE role = 'employee' AND role_id IS NULL;
SELECT @adminCount = COUNT(*) FROM users WHERE role = 'admin' AND role_id IS NULL;
SELECT @superAdminCount = COUNT(*) FROM users WHERE role = 'super_admin' AND role_id IS NULL;
SELECT @unmappedCount = COUNT(*) FROM users WHERE role_id IS NULL AND role NOT IN ('employee', 'admin', 'super_admin');

-- Map string roles to role_id
UPDATE users SET role_id = 1 WHERE (role = 'employee' OR role IS NULL) AND role_id IS NULL;
UPDATE users SET role_id = 2 WHERE role = 'admin' AND role_id IS NULL;
UPDATE users SET role_id = 3 WHERE role = 'super_admin' AND role_id IS NULL;

-- Handle any unmapped roles (set to employee as safe default)
UPDATE users SET role_id = 1 WHERE role_id IS NULL;

PRINT '  ✓ Migrated roles:';
PRINT '    - Employees: ' + CAST(@employeeCount AS VARCHAR);
PRINT '    - Admins: ' + CAST(@adminCount AS VARCHAR);
PRINT '    - Super Admins: ' + CAST(@superAdminCount AS VARCHAR);
IF @unmappedCount > 0
    PRINT '    - Unmapped (defaulted to employee): ' + CAST(@unmappedCount AS VARCHAR);
GO

-- ================================================
-- STEP 5: Add foreign key constraint
-- ================================================
PRINT '';
PRINT '→ Step 5: Adding foreign key constraint...';

IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_users_role_id')
BEGIN
    ALTER TABLE users 
    ADD CONSTRAINT FK_users_role_id 
    FOREIGN KEY (role_id) REFERENCES roles(id);
    
    PRINT '  ✓ Foreign key constraint FK_users_role_id created';
END
ELSE
BEGIN
    PRINT '  ! Foreign key already exists';
END
GO

-- ================================================
-- STEP 6: Create trigger to sync role and role_id
-- ================================================
PRINT '';
PRINT '→ Step 6: Creating synchronization trigger...';

-- Drop existing trigger if present
IF EXISTS (SELECT * FROM sys.triggers WHERE name = 'trg_users_sync_role')
BEGIN
    DROP TRIGGER trg_users_sync_role;
    PRINT '  ! Dropped existing trigger';
END
GO

CREATE TRIGGER trg_users_sync_role
ON users
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Sync role_id -> role (for backward compatibility with old code)
    UPDATE u
    SET u.role = r.name
    FROM users u
    INNER JOIN inserted i ON u.id = i.id
    INNER JOIN roles r ON u.role_id = r.id
    WHERE u.role_id IS NOT NULL;
END;
GO

PRINT '  ✓ Trigger trg_users_sync_role created';
GO

-- ================================================
-- STEP 7: Verification queries
-- ================================================
PRINT '';
PRINT '========================================';
PRINT 'MIGRATION VERIFICATION';
PRINT '========================================';
PRINT '';

PRINT '→ Roles in database:';
SELECT 
    id,
    name,
    display_name,
    level,
    is_active,
    (SELECT COUNT(*) FROM users WHERE role_id = roles.id) as user_count
FROM roles
ORDER BY level;

PRINT '';
PRINT '→ Sample user role mappings (first 10 users):';
SELECT TOP 10
    u.id, 
    u.username, 
    u.role as old_role_column, 
    u.role_id, 
    r.name as role_from_table,
    r.level
FROM users u
LEFT JOIN roles r ON u.role_id = r.id
ORDER BY u.id;

PRINT '';
PRINT '→ Summary:';
DECLARE @totalUsers INT = (SELECT COUNT(*) FROM users);
DECLARE @usersWithRoleId INT = (SELECT COUNT(*) FROM users WHERE role_id IS NOT NULL);
DECLARE @mismatchCount INT = (SELECT COUNT(*) FROM users u 
                               INNER JOIN roles r ON u.role_id = r.id 
                               WHERE u.role != r.name);

PRINT '  Total users: ' + CAST(@totalUsers AS VARCHAR);
PRINT '  Users with role_id: ' + CAST(@usersWithRoleId AS VARCHAR);
PRINT '  Role/role_id mismatches: ' + CAST(@mismatchCount AS VARCHAR);

IF @totalUsers = @usersWithRoleId AND @mismatchCount = 0
    PRINT '  ✓ All users successfully migrated with matching data';
ELSE
    PRINT '  ⚠ Some users may need manual verification';

PRINT '';
PRINT '========================================';
PRINT '✓✓✓ MIGRATION COMPLETED SUCCESSFULLY ✓✓✓';
PRINT 'Timestamp: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '========================================';
GO
