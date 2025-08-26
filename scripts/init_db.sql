-- Initialize PostgreSQL database for Schwab API client

-- Create schema
CREATE SCHEMA IF NOT EXISTS api;

-- Set search path
SET search_path TO api, public;

-- Auth tokens table will be created by Alembic migrations
-- This file is for any custom database initialization

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA api TO api_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA api TO api_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA api TO api_user;