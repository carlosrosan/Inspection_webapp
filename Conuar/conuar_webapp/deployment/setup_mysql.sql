-- Create the database
CREATE DATABASE IF NOT EXISTS conuar_webapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Use the database
USE conuar_webapp;

-- Create a dedicated user (optional but recommended for production)
-- CREATE USER 'conuar_user'@'localhost' IDENTIFIED BY 'your_secure_password';
-- GRANT ALL PRIVILEGES ON conuar_webapp.* TO 'conuar_user'@'localhost';
-- FLUSH PRIVILEGES;

-- Show the created database
SHOW DATABASES;
