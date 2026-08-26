-- =====================================================
-- BUG TRACKING SYSTEM - DATABASE SCHEMA
-- =====================================================
-- This script creates the complete database structure
-- for the bug tracking system with users, bug records,
-- and notifications tables.

-- SQLite creates the local database file automatically.

-- =====================================================
-- TABLE: users
-- =====================================================
-- Stores user information for developers, testers, and project managers
-- Role: Developer, Tester, Project Manager
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'Developer' CHECK (role IN ('Developer', 'Tester', 'Project Manager')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: bug_records
-- =====================================================
-- Core table storing all bug reports
-- Fields: ID, title, description, priority, status, assignee, reporter, environment, URL route, error log
CREATE TABLE bug_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT DEFAULT 'Medium' CHECK (priority IN ('Critical', 'High', 'Medium', 'Low')),
    status TEXT DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
    reporter_id INT NOT NULL,
    assignee_id INT,
    environment TEXT,
    url_route TEXT,
    error_log TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (assignee_id) REFERENCES users(id) ON DELETE SET NULL
);

-- =====================================================
-- TABLE: notifications
-- =====================================================
-- Tracks status updates and notifications for bug resolution
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bug_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (bug_id) REFERENCES bug_records(id) ON DELETE CASCADE
);

-- =====================================================
-- Sample Data for Testing
-- =====================================================

-- Insert sample users
INSERT INTO users (username, email, password_hash, role) VALUES
('alice_dev', 'alice@company.com', 'hashed_pwd_1', 'Developer'),
('bob_tester', 'bob@company.com', 'hashed_pwd_2', 'Tester'),
('charlie_pm', 'charlie@company.com', 'hashed_pwd_3', 'Project Manager'),
('diana_dev', 'diana@company.com', 'hashed_pwd_4', 'Developer');

-- Insert sample bugs
INSERT INTO bug_records (title, description, priority, status, reporter_id, assignee_id, environment, url_route, error_log) VALUES
(
    'Login page crashes on mobile',
    'When accessing login page from iOS Safari, the page crashes. Happens on iPhone 12 and 13. Issue is reproducible every time.',
    'Critical',
    'Open',
    2,
    1,
    'Mobile - iOS',
    '/api/login',
    'JavaScript Error: Cannot read property "location" of undefined at line 234 in auth.js'
),
(
    'Dashboard slow on first load',
    'Dashboard takes 8-10 seconds to load on first visit. Subsequent loads are faster.',
    'High',
    'In Progress',
    2,
    1,
    'Chrome Desktop',
    '/dashboard',
    'Network tab shows multiple API calls taking 3-4 seconds each.'
),
(
    'Forgot password email not received',
    'Users report not receiving password reset emails. Some emails arrive after 10+ minutes delay.',
    'High',
    'Open',
    2,
    4,
    'Production',
    '/api/password-reset',
    NULL
),
(
    'Export to CSV button broken',
    'CSV export button on reports page is not working. Button click does nothing.',
    'Medium',
    'Resolved',
    2,
    1,
    'Chrome Desktop',
    '/reports/export',
    NULL
),
(
    'Typo in user settings label',
    'The label "Notifcation" should be "Notification" in settings page.',
    'Low',
    'Closed',
    3,
    NULL,
    'All',
    '/settings',
    NULL
),
(
    'API rate limiting not working correctly',
    'Users can make more than 100 requests per minute, bypassing rate limits.',
    'Critical',
    'Open',
    3,
    4,
    'Production',
    '/api/v1/*',
    'Rate limiter middleware may be disabled'
),
(
    'Dark mode toggle persists incorrectly',
    'When switching to dark mode, preference is not saved. Resets on page refresh.',
    'Low',
    'In Progress',
    2,
    NULL,
    'Chrome, Firefox',
    '/settings/theme',
    NULL
),
(
    'Database connection timeout at peak hours',
    'System experiences connection timeouts between 3-4 PM EST when user count peaks.',
    'High',
    'Open',
    3,
    1,
    'Production',
    NULL,
    'MySQL connection pool exhausted'
);

-- Insert sample notifications
INSERT INTO notifications (user_id, bug_id, message, is_read) VALUES
(1, 1, 'Bug #1 assigned to you: Login page crashes on mobile (Critical)', FALSE),
(1, 2, 'Bug #2 assigned to you: Dashboard slow on first load (High)', FALSE),
(2, 3, 'Status update: Bug #3 now assigned to diana_dev', TRUE),
(2, 5, 'Status update: Bug #5 marked as Closed', TRUE),
(1, 6, 'New bug reported: API rate limiting not working correctly (Critical)', FALSE),
(4, 6, 'Bug #6 assigned to you: API rate limiting not working correctly', FALSE),
(1, 8, 'Status update: Bug #8 priority changed to High', TRUE);

-- =====================================================
-- Verification Query (Optional: Run to verify setup)
-- =====================================================
-- SELECT 
--     (SELECT COUNT(*) FROM users) as total_users,
--     (SELECT COUNT(*) FROM bug_records) as total_bugs,
--     (SELECT COUNT(*) FROM notifications) as total_notifications;
