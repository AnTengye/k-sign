# new-api Auto Checkin Design

## Goal
Add a k-sign style script that logs into a new-api instance with a single username/password from environment variables and performs daily check-in at 08:00, while skipping login if Turnstile or 2FA is enabled.

## Scope
- New script only; do not change new-api.
- Single account via environment variables, matching k-sign conventions.
- Daily cron header.

## Configuration
- `SIGN_URL_NEWAPI`: base URL of the new-api instance (e.g. `https://example.com`).
- `SIGN_UP_NEWAPI`: `username|password`.

## Behavior
1. `GET /api/status`:
   - If `turnstile_check` is true, log and stop (cannot pass Turnstile).
   - If `checkin_enabled` is false, log and stop.
2. `POST /api/user/login` with JSON `{ "username": ..., "password": ... }`.
   - If response indicates `require_2fa` or login fails, log and stop.
3. `GET /api/user/checkin` to read `checked_in_today`.
   - If already checked in, log and exit.
4. `POST /api/user/checkin` to perform check-in.

## Logging/Notification
Use existing `BaseSign.pwl()` and `notify.send()` from k-sign. The script should follow the same output style as other k-sign scripts.

## Error Handling
- Network or JSON errors are logged and treated as failures.
- No retries beyond BaseSign default.

## Testing Strategy
Unit tests for:
- Status parsing (Turnstile enabled -> skip).
- Login response handling (require_2fa -> skip).
- Check-in status handling (checked_in_today -> skip).

## Files
- Add: `newapi.py`
- Add: `docs/plans/2026-03-11-newapi-auto-checkin-design.md`
