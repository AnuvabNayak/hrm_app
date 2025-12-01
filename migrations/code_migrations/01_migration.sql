-- ========================================================================
-- ATTENDANCE SYSTEM V2.0 - DATABASE MIGRATION SCRIPT
-- ========================================================================
-- Purpose: Add daily attendance aggregation and archival tables
-- Date: November 12, 2025
-- Database: SQL Server
-- 
-- What this script does:
-- 1. Creates `daily_attendance` table (hot storage, last 30 days)
-- 2. Creates `archived_attendance` table (cold storage, 1 year)
-- 3. Adds `daily_attendance_id` column to existing `work_sessions` table
-- 4. Creates all necessary indexes and foreign keys
-- 5. Verifies successful creation
-- 
-- Safe to run: YES - Does NOT modify existing data
-- Idempotent: YES - Can be run multiple times safely
-- ========================================================================

-- Start transaction for safety
BEGIN TRANSACTION;

PRINT '========================================================================';
PRINT 'ATTENDANCE SYSTEM V2.0 - DATABASE MIGRATION';
PRINT 'Started at: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '========================================================================';
PRINT '';

-- ========================================================================
-- STEP 1: CREATE daily_attendance TABLE
-- ========================================================================
-- Purpose: Store aggregated daily attendance for last 30 days
-- Hot storage: Frequently accessed, fast queries
-- ========================================================================

PRINT '📊 STEP 1: Creating daily_attendance table...';

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'daily_attendance')
BEGIN
    CREATE TABLE daily_attendance (
        -- Primary Key
        id INT PRIMARY KEY IDENTITY(1,1),
        
        -- Foreign Keys
        employee_id INT NOT NULL,
        
        -- Date (unique per employee per day)
        attendance_date DATE NOT NULL,
        
        -- Aggregated Metrics
        total_work_seconds INT NOT NULL DEFAULT 0,
        total_break_seconds INT NOT NULL DEFAULT 0,
        session_count INT NOT NULL DEFAULT 0,
        
        -- First and Last Times
        first_clock_in DATETIME NULL,
        last_clock_out DATETIME NULL,
        
        -- Status: complete, partial, incomplete, absent, leave
        status VARCHAR(20) NOT NULL DEFAULT 'incomplete',
        
        -- Metadata
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        updated_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        
        -- Foreign Key Constraint
        CONSTRAINT fk_daily_attendance_employee 
            FOREIGN KEY (employee_id) 
            REFERENCES employees(id) 
            ON DELETE CASCADE,
        
        -- Unique Constraint: One record per employee per day
        CONSTRAINT unique_employee_date 
            UNIQUE (employee_id, attendance_date)
    );
    
    PRINT '✅ Table created: daily_attendance';
    
    -- Create Indexes for Performance
    CREATE INDEX idx_daily_attendance_date 
        ON daily_attendance(attendance_date DESC);
    PRINT '✅ Index created: idx_daily_attendance_date';
    
    CREATE INDEX idx_daily_attendance_employee_date 
        ON daily_attendance(employee_id, attendance_date DESC);
    PRINT '✅ Index created: idx_daily_attendance_employee_date';
    
    CREATE INDEX idx_daily_attendance_status 
        ON daily_attendance(status, attendance_date);
    PRINT '✅ Index created: idx_daily_attendance_status';
    
    PRINT '✅ STEP 1 COMPLETE: daily_attendance table created with 3 indexes';
END
ELSE
BEGIN
    PRINT '⚠️  Table already exists: daily_attendance (skipping)';
END

PRINT '';

-- ========================================================================
-- STEP 2: CREATE archived_attendance TABLE
-- ========================================================================
-- Purpose: Store attendance data older than 30 days for compliance
-- Cold storage: Less frequently accessed, optimized for storage
-- Retention: 1 year (records older than 1 year are deleted)
-- ========================================================================

PRINT '📦 STEP 2: Creating archived_attendance table...';

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'archived_attendance')
BEGIN
    CREATE TABLE archived_attendance (
        -- Primary Key
        id INT PRIMARY KEY IDENTITY(1,1),
        
        -- Foreign Keys
        employee_id INT NOT NULL,
        
        -- Date
        attendance_date DATE NOT NULL,
        
        -- Same Aggregated Data as daily_attendance
        total_work_seconds INT NOT NULL,
        total_break_seconds INT NOT NULL,
        session_count INT NOT NULL,
        first_clock_in DATETIME NULL,
        last_clock_out DATETIME NULL,
        status VARCHAR(20) NOT NULL,
        
        -- Archive Metadata
        archived_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        original_daily_id INT NULL,  -- Reference to original daily_attendance record
        
        -- Foreign Key Constraint
        CONSTRAINT fk_archived_attendance_employee 
            FOREIGN KEY (employee_id) 
            REFERENCES employees(id) 
            ON DELETE CASCADE
    );
    
    PRINT '✅ Table created: archived_attendance';
    
    -- Create Indexes (fewer than daily_attendance)
    CREATE INDEX idx_archived_attendance_employee_date 
        ON archived_attendance(employee_id, attendance_date DESC);
    PRINT '✅ Index created: idx_archived_attendance_employee_date';
    
    CREATE INDEX idx_archived_attendance_date 
        ON archived_attendance(attendance_date DESC);
    PRINT '✅ Index created: idx_archived_attendance_date';
    
    PRINT '✅ STEP 2 COMPLETE: archived_attendance table created with 2 indexes';
END
ELSE
BEGIN
    PRINT '⚠️  Table already exists: archived_attendance (skipping)';
END

PRINT '';

-- ========================================================================
-- STEP 3: ADD COLUMN TO work_sessions TABLE
-- ========================================================================
-- Purpose: Link work sessions to their daily attendance record
-- Impact: Adds 1 nullable column to existing table
-- Data: No existing data is modified
-- ========================================================================

PRINT '🔗 STEP 3: Adding daily_attendance_id to work_sessions table...';

-- Check if column already exists
IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('work_sessions') 
    AND name = 'daily_attendance_id'
)
BEGIN
    -- Add the column (nullable, so no impact on existing rows)
    ALTER TABLE work_sessions
        ADD daily_attendance_id INT NULL;
    
    PRINT '✅ Column added: work_sessions.daily_attendance_id';
    
    -- Add foreign key constraint
    ALTER TABLE work_sessions
        ADD CONSTRAINT fk_work_sessions_daily_attendance 
            FOREIGN KEY (daily_attendance_id) 
            REFERENCES daily_attendance(id) 
            ON DELETE SET NULL;
    
    PRINT '✅ Foreign key created: fk_work_sessions_daily_attendance';
    
    -- Create index for faster lookups
    CREATE INDEX idx_work_sessions_daily_attendance 
        ON work_sessions(daily_attendance_id);
    
    PRINT '✅ Index created: idx_work_sessions_daily_attendance';
    
    PRINT '✅ STEP 3 COMPLETE: work_sessions table updated';
END
ELSE
BEGIN
    PRINT '⚠️  Column already exists: work_sessions.daily_attendance_id (skipping)';
END

PRINT '';

-- ========================================================================
-- STEP 4: VERIFICATION
-- ========================================================================
-- Purpose: Verify all tables and indexes were created successfully
-- ========================================================================

PRINT '🔍 STEP 4: Verifying migration...';
PRINT '';

-- Check tables
DECLARE @tableCount INT;
SELECT @tableCount = COUNT(*) 
FROM sys.tables 
WHERE name IN ('daily_attendance', 'archived_attendance');

PRINT 'Tables created: ' + CAST(@tableCount AS VARCHAR) + '/2';

IF @tableCount = 2
BEGIN
    PRINT '✅ All tables exist';
END
ELSE
BEGIN
    PRINT '❌ ERROR: Not all tables were created';
    ROLLBACK TRANSACTION;
    RETURN;
END

-- Check indexes
DECLARE @indexCount INT;
SELECT @indexCount = COUNT(DISTINCT i.name)
FROM sys.indexes i
INNER JOIN sys.tables t ON i.object_id = t.object_id
WHERE t.name IN ('daily_attendance', 'archived_attendance', 'work_sessions')
AND i.name LIKE 'idx_%attendance%';

PRINT 'Indexes created: ' + CAST(@indexCount AS VARCHAR) + ' (expected: 6)';

IF @indexCount >= 6
BEGIN
    PRINT '✅ All indexes exist';
END
ELSE
BEGIN
    PRINT '⚠️  WARNING: Expected 6 indexes, found ' + CAST(@indexCount AS VARCHAR);
END

-- Check column
IF EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID('work_sessions') 
    AND name = 'daily_attendance_id'
)
BEGIN
    PRINT '✅ Column exists: work_sessions.daily_attendance_id';
END
ELSE
BEGIN
    PRINT '❌ ERROR: Column work_sessions.daily_attendance_id not found';
    ROLLBACK TRANSACTION;
    RETURN;
END

PRINT '';

-- ========================================================================
-- STEP 5: DISPLAY SUMMARY
-- ========================================================================

PRINT '========================================================================';
PRINT 'MIGRATION SUMMARY';
PRINT '========================================================================';

-- Table row counts
SELECT 
    'daily_attendance' AS table_name,
    COUNT(*) AS current_rows
FROM daily_attendance
UNION ALL
SELECT 
    'archived_attendance',
    COUNT(*)
FROM archived_attendance
UNION ALL
SELECT 
    'work_sessions',
    COUNT(*)
FROM work_sessions;

PRINT '';
PRINT '📋 Table Structure:';
PRINT '';

-- daily_attendance structure
PRINT '1. daily_attendance:';
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'daily_attendance'
ORDER BY ORDINAL_POSITION;

PRINT '';
PRINT '2. archived_attendance:';
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'archived_attendance'
ORDER BY ORDINAL_POSITION;

PRINT '';
PRINT '========================================================================';
PRINT '✅✅✅ MIGRATION COMPLETED SUCCESSFULLY! ✅✅✅';
PRINT 'Completed at: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '========================================================================';
PRINT '';
PRINT 'NEXT STEPS:';
PRINT '1. Verify tables in SQL Server Management Studio';
PRINT '2. Run backend model updates (models.py)';
PRINT '3. Test aggregation functions';
PRINT '4. Backfill historical data (optional)';
PRINT '';

-- Commit transaction
COMMIT TRANSACTION;

PRINT '✅ Transaction committed successfully';
PRINT '';
