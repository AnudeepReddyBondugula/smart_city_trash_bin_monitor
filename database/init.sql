-- Init script for PostgreSQL database
-- Loads schema and seeds initial data

-- 2. Seed initial users (password: 'admin' for admin, 'viewer' for viewer)
INSERT INTO api_users (username, password_hash, role, is_active)
VALUES
  ('admin', '$2b$12$Zo26K4rwepjeP4x.p.aTeusjacVJqdEuEOw4vuf4sTYEqkeSbcEBq', 'admin', TRUE),
  ('viewer', '$2b$12$nDocjJJwQ9ps4W6q4MZ8MO1.X41C9VbMt/GG6ml.PIuPvw77Du3WS', 'viewer', TRUE)
ON CONFLICT (username) DO NOTHING;
