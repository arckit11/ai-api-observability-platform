-- V5: seed a demo admin user for local dev / smoke tests.
-- Password: "admin1234!" (BCrypt hash, cost=10). Rotate before any real deploy.
INSERT INTO users (id, username, email, password_hash, role, is_active)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin',
    'admin@example.com',
    '$2a$10$hsK1kmJLcKXWbObd3WYJQOXkZmZfEl5NQPssGHCYMVEuYg.tbyJci',
    'ADMIN',
    TRUE
)
ON CONFLICT (id) DO NOTHING;
