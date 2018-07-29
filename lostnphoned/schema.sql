DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS passwords;

CREATE TABLE users (
  phone_number TEXT PRIMARY KEY,
  token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  token_uri TEXT NOT NULL,
  client_id TEXT NOT NULL,
  client_secret TEXT NOT NULL,
  salt BLOB NOT NULL
);

CREATE TABLE passwords (
  id INTEGER PRIMARY KEY,
  phone_number TEXT NOT NULL REFERENCES users(phone_number) ON UPDATE CASCADE ON DELETE CASCADE,
  password BLOB NOT NULL
);

CREATE TABLE bannable_clients (
  phone_number TEXT PRIMARY KEY,
  last_attempt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  attempts INTEGER NOT NULL DEFAULT 1
);