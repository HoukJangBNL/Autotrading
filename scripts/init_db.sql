-- Initialize PostgreSQL database for trading system

-- Create TimescaleDB extension for time-series data
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create custom types if needed
DO $$ BEGIN
    CREATE TYPE trading_mode AS ENUM ('discovery', 'selection', 'trading');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create schema
CREATE SCHEMA IF NOT EXISTS trading;

-- Set search path
SET search_path TO trading, public;

-- Create indexes for better performance
-- These will be created by Alembic, but we can add custom ones here

-- Create hypertable for time-series data (after table creation)
-- This should be run after Alembic creates the tables:
-- SELECT create_hypertable('price_data', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- Create continuous aggregates for common queries
-- Example for 5-minute candles:
-- CREATE MATERIALIZED VIEW price_data_5min
-- WITH (timescaledb.continuous) AS
-- SELECT
--     symbol,
--     time_bucket('5 minutes', timestamp) AS bucket,
--     first(open, timestamp) AS open,
--     max(high) AS high,
--     min(low) AS low,
--     last(close, timestamp) AS close,
--     sum(volume) AS volume
-- FROM price_data
-- GROUP BY symbol, bucket
-- WITH NO DATA;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA trading TO trading;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trading TO trading;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trading TO trading;