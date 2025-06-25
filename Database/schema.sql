-- Create the main database for the feedback system
CREATE DATABASE IF NOT EXISTS feedback_system;
USE feedback_system; -- Switch to the feedback_system database

-- Table to store all users (managers + employees)
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,         -- unique user identifier
  name VARCHAR(100) NOT NULL,               -- full name of the user
  email VARCHAR(255) NOT NULL UNIQUE,       -- login email, must be unique
  password VARCHAR(255) NOT NULL,           -- bcrypt‑hashed password
  role ENUM('manager','employee') NOT NULL, -- user role: manager or employee
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- record creation time
);

-- ADD manager_id column to users table:
ALTER TABLE users 
  ADD COLUMN manager_id INT NULL AFTER role, -- FK to users(id) for the manager, can be NULL if no manager
  ADD FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL; -- FK to users(id) for the manager, can be NULL if no manager

-- Table to store feedback entries
CREATE TABLE IF NOT EXISTS feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,           -- unique feedback identifier
  manager_id INT NOT NULL,                     -- FK to users(id) for the manager
  employee_id INT NOT NULL,                    -- FK to users(id) for the employee
  strengths TEXT NOT NULL,                     -- feedback: strengths
  improvements TEXT NOT NULL,                  -- feedback: areas to improve
  sentiment ENUM('positive','neutral','negative') NOT NULL, -- overall sentiment
  tags VARCHAR(255) DEFAULT NULL,              -- comma‑separated tags, e.g. "leadership,communication"
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,           -- when feedback was created
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, -- last edit
  FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,  -- FK to users(id) for the manager
  FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE CASCADE -- FK to users(id) for the employee
);

-- Table to track acknowledgements by employees
CREATE TABLE IF NOT EXISTS acknowledgements (
  feedback_id INT NOT NULL,                  -- FK to feedback(id)
  employee_id INT NOT NULL,                  -- FK to users(id), must match feedback.employee_id
  acknowledged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- when they acknowledged
  PRIMARY KEY (feedback_id, employee_id),    -- one record per feedback per employee
  FOREIGN KEY (feedback_id) REFERENCES feedback(id) ON DELETE CASCADE, -- FK to feedback(id)
  FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE CASCADE -- FK to users(id)
);

-- Table for comments on feedback (supports markdown)
CREATE TABLE IF NOT EXISTS comments (
  id INT AUTO_INCREMENT PRIMARY KEY,         -- unique comment identifier
  feedback_id INT NOT NULL,                  -- FK to feedback(id)
  user_id INT NOT NULL,                      -- FK to users(id) who wrote the comment
  comment_text TEXT NOT NULL,                -- the comment body (markdown allowed)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- when comment was made
  FOREIGN KEY (feedback_id) REFERENCES feedback(id) ON DELETE CASCADE, -- FK to feedback(id)
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE -- FK to users(id)
);










-- Optional initial data assignment for single manager
-- Open your terminal/CLI or MySQL GUI
-- UPDATE users
--   SET manager_id = 1
-- WHERE role = 'employee';


-- Optional initial data assignment for multiple managers
-- Assign managers to employees based on their email addresses
-- Assuming the following email addresses belong to specific managers
-- Open your terminal/CLI or MySQL GUI 
-- UPDATE users
--   SET manager_id = 1
-- WHERE email = 'ramuchary2001@gmail.com';  -- belongs to Saikiran (id=1)

-- UPDATE users
--   SET manager_id = 5
-- WHERE email = 'fg@hshsh.com';           -- belongs to jdjdjdjdjfjfjf (id=5)

-- UPDATE users
--   SET manager_id = 10
-- WHERE email = 'hunter2001@gmail.com';  -- belongs to Sankathir (id=10)


