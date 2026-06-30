from datetime import datetime, timezone

from storage.db import get_connection


class DigestLogRepository:
    def save(self, user_id: str, status: str, item_count: int, message: str | None = None) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO digest_logs (user_id, status, item_count, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    status,
                    item_count,
                    message,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
