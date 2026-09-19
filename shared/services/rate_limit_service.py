"""Rate limiting service for login attempts."""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from database.db_manager import get_db
from utils.config import Config


class LoginRateLimiter:
    """Track and limit failed login attempts using the shared database.

    The limiter works across multiple Gunicorn workers because state lives in
    the application database rather than in process memory.
    """

    @staticmethod
    def _now() -> datetime:
        """Return the current UTC time."""
        return datetime.utcnow()

    @staticmethod
    def _now_str() -> str:
        """Return the current UTC time as a database-friendly string."""
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _parse_timestamp(value) -> Optional[datetime]:
        """Normalize a timestamp value from the database to datetime."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # SQLite default format: YYYY-MM-DD HH:MM:SS
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return None

    @classmethod
    def is_allowed(cls, ip_address: str, username: Optional[str] = None) -> Tuple[bool, Optional[int]]:
        """Check whether a login attempt is allowed for the given IP/user.

        Returns:
            A tuple (allowed, retry_after_seconds). retry_after_seconds is
            None when the attempt is allowed, otherwise the number of seconds
            the client must wait before trying again.
        """
        if not Config.LOGIN_RATE_LIMIT_ENABLED or not ip_address:
            return True, None

        db = get_db()
        now = cls._now()
        window_start = (now - timedelta(seconds=Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")

        if username:
            row = db.execute(
                """
                SELECT COUNT(*) AS attempt_count, MAX(attempted_at) AS last_attempt
                FROM login_attempts
                WHERE ip_address = ?
                  AND username = ?
                  AND success = FALSE
                  AND attempted_at > ?
                """,
                (ip_address, username, window_start),
                fetchone=True,
            )
        else:
            row = db.execute(
                """
                SELECT COUNT(*) AS attempt_count, MAX(attempted_at) AS last_attempt
                FROM login_attempts
                WHERE ip_address = ?
                  AND username IS NULL
                  AND success = FALSE
                  AND attempted_at > ?
                """,
                (ip_address, window_start),
                fetchone=True,
            )

        if not row:
            return True, None

        attempt_count = row["attempt_count"] if isinstance(row, dict) else row[0]
        last_attempt = cls._parse_timestamp(
            row["last_attempt"] if isinstance(row, dict) else row[1]
        )

        if attempt_count >= Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS and last_attempt:
            lockout_end = last_attempt + timedelta(seconds=Config.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS)
            retry_after = max(0, int((lockout_end - now).total_seconds()))
            if retry_after > 0:
                return False, retry_after

        return True, None

    @classmethod
    def record_attempt(cls, ip_address: str, username: Optional[str] = None, success: bool = False) -> None:
        """Record a login attempt in the database."""
        if not Config.LOGIN_RATE_LIMIT_ENABLED or not ip_address:
            return

        db = get_db()
        db.execute(
            """
            INSERT INTO login_attempts (ip_address, username, attempted_at, success)
            VALUES (?, ?, ?, ?)
            """,
            (ip_address, username, cls._now_str(), success),
        )

        if success:
            # Clear previous failures after a successful login.
            cls.clear_attempts(ip_address, username)

    @classmethod
    def clear_attempts(cls, ip_address: str, username: Optional[str] = None) -> None:
        """Remove recorded attempts for an IP address (optionally filtered by user)."""
        if not ip_address:
            return

        db = get_db()
        if username:
            db.execute(
                """
                DELETE FROM login_attempts
                WHERE ip_address = ? AND username = ?
                """,
                (ip_address, username),
            )
        else:
            db.execute(
                """
                DELETE FROM login_attempts
                WHERE ip_address = ? AND username IS NULL
                """,
                (ip_address,),
            )

    @classmethod
    def cleanup(cls) -> None:
        """Delete old login attempt records.

        Kept public so it can be invoked from a scheduled task if desired.
        """
        if not Config.LOGIN_RATE_LIMIT_ENABLED:
            return

        max_seconds = max(
            Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            Config.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS,
        )
        cutoff = (cls._now() - timedelta(seconds=max_seconds * 2)).strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        db.execute(
            """
            DELETE FROM login_attempts
            WHERE attempted_at < ?
            """,
            (cutoff,),
        )
