-- Migration: Add first_name and last_name fields to users table
-- Run this on Ubuntu with: sqlite3 bot_database.db < migrations/add_user_name_fields.sql

-- Add first_name column if it doesn't exist
ALTER TABLE users ADD COLUMN first_name VARCHAR(255) NULL;

-- Add last_name column if it doesn't exist
ALTER TABLE users ADD COLUMN last_name VARCHAR(255) NULL;

