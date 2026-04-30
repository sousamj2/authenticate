# Authenticate Module

This module isolates all user authentication, authorization, and session management logic.

## Responsibilities

- **Authentication Providers:** Supports both standard email/password authentication (`signin`, `signup`) and Google OAuth2 (`oauth2callback`).
- **Session Management:** Manages Flask session cookies, securely storing metadata, user info, and JWT tokens.
- **Database Synchronization (`updateDB.py`):** Acts as the bridge between successful signups/logins and the database, ensuring that new users, connection logs, and IP history are correctly recorded in the database.
- **Access Control:** Provides middleware/decorators to protect routes and verify active sessions.

## Architecture Notes
- Uses UUIDs (`CHAR(36)`) for user identification to ensure high security and referential integrity.
- Handles duplicate signup attempts gracefully without exposing sensitive database errors.
