DROP TABLE IF EXISTS users;

CREATE TABLE users (
  phone_number TEXT UNIQUE NOT NULL,
  token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  token_uri TEXT NOT NULL,
  client_id TEXT NOT NULL,
  client_secret TEXT NOT NULL,
  scopes TEXT
);
