"""
Audit Logging Module.

Provides JSONL-based audit logging for moderation actions.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .scorer import ScoreBreakdown


class AuditLogger:
    """
    JSONL audit logger for moderation actions.

    Each log entry is a single JSON line, making it easy to parse
    and process with standard tools.
    """

    def __init__(
        self,
        log_dir: str = "./logs",
        log_level: str = "INFO",
        filename_prefix: str = "moderation_audit",
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.filename_prefix = filename_prefix

        # Get current date for log rotation
        self._current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._logger: Optional[logging.Logger] = None

        self._setup_logger()

    def _setup_logger(self) -> None:
        """Set up the JSONL logger."""
        log_file = self._get_log_file_path()

        # Create logger
        self._logger = logging.getLogger(f"audit.{self.filename_prefix}")
        self._logger.setLevel(self.log_level)
        self._logger.handlers = []  # Clear existing handlers

        # File handler for JSONL output. This opens the file only while
        # writing each record so test temp directories are not locked on Windows.
        file_handler = JSONLFileHandler(log_file)
        file_handler.setLevel(self.log_level)

        # Custom formatter for JSONL
        formatter = JSONLFormatter()
        file_handler.setFormatter(formatter)

        self._logger.addHandler(file_handler)

        # Also add console handler for visibility
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        self._logger.addHandler(console_handler)

    def _get_log_file_path(self) -> Path:
        """Get the current log file path with date-based rotation."""
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if current_date != self._current_date:
            # Date changed, rotate log file
            self._current_date = current_date
            self._setup_logger()

        return self.log_dir / f"{self.filename_prefix}_{self._current_date}.jsonl"

    def log_action(
        self,
        action: str,
        comment_id: int,
        repo: str,
        issue_number: int,
        risk_score: float,
        breakdown: Optional[ScoreBreakdown] = None,
        author: Optional[str] = None,
        decision: Optional[str] = None,
        dry_run: bool = False,
        delivery_id: Optional[str] = None,
        additional_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log a moderation action.

        Args:
            action: Action taken (e.g., "flagged", "deleted", "skipped")
            comment_id: GitHub comment ID
            repo: Repository name (owner/repo)
            issue_number: Issue number
            risk_score: Calculated risk score
            breakdown: Score breakdown details
            author: Comment author username
            decision: Final decision (auto/manual)
            dry_run: Whether this was a dry run
            delivery_id: GitHub delivery ID for idempotency
            additional_data: Any additional context
        """
        if not self._logger:
            self._setup_logger()

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "comment_id": comment_id,
            "repo": repo,
            "issue_number": issue_number,
            "risk_score": round(risk_score, 4),
            "author": author,
            "decision": decision,
            "dry_run": dry_run,
            "delivery_id": delivery_id,
        }

        # Add score breakdown if available
        if breakdown:
            log_entry["score_breakdown"] = {
                "spam_keywords": round(breakdown.spam_keywords_score, 4),
                "link_ratio": round(breakdown.link_ratio_score, 4),
                "length_penalty": round(breakdown.length_penalty_score, 4),
                "repetition": round(breakdown.repetition_score, 4),
                "mention_spam": round(breakdown.mention_spam_score, 4),
                "semantic": round(breakdown.semantic_score, 4),
                "factors": breakdown.factors,
            }

        # Add additional data
        if additional_data:
            log_entry["metadata"] = additional_data

        self._logger.info(json.dumps(log_entry))

    def log_webhook_event(
        self,
        event_type: str,
        delivery_id: str,
        repo: str,
        action: str,
        payload_summary: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log a webhook event receipt.

        Args:
            event_type: GitHub event type (e.g., "issue_comment")
            delivery_id: GitHub delivery ID
            repo: Repository name
            action: Event action (e.g., "created", "deleted")
            payload_summary: Summary of payload data
        """
        if not self._logger:
            self._setup_logger()

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "webhook_received",
            "github_event": event_type,
            "delivery_id": delivery_id,
            "repo": repo,
            "action": action,
        }

        if payload_summary:
            log_entry["payload_summary"] = payload_summary

        self._logger.info(json.dumps(log_entry))

    def log_error(
        self,
        error_type: str,
        message: str,
        comment_id: Optional[int] = None,
        repo: Optional[str] = None,
        delivery_id: Optional[str] = None,
        traceback: Optional[str] = None,
    ) -> None:
        """
        Log an error event.

        Args:
            error_type: Type of error
            message: Error message
            comment_id: Related comment ID if applicable
            repo: Related repository if applicable
            delivery_id: Related delivery ID if applicable
            traceback: Stack trace if available
        """
        if not self._logger:
            self._setup_logger()

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "error",
            "error_type": error_type,
            "message": message,
            "comment_id": comment_id,
            "repo": repo,
            "delivery_id": delivery_id,
        }

        if traceback:
            log_entry["traceback"] = traceback

        self._logger.error(json.dumps(log_entry))

    def get_log_path(self) -> Path:
        """Get the current log file path."""
        return self._get_log_file_path()


class JSONLFormatter(logging.Formatter):
    """Custom formatter that outputs JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # If the message is already JSON, pass it through
        if record.msg.startswith("{") and record.msg.endswith("}"):
            try:
                # Parse and re-serialize to ensure valid JSON
                data = json.loads(record.msg)
                return json.dumps(data, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

        # Otherwise, create a standard log entry
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        return json.dumps(data, ensure_ascii=False)


class JSONLFileHandler(logging.Handler):
    """Write JSONL records without keeping the log file open."""

    terminator = "\n"

    def __init__(self, filename: Path, encoding: str = "utf-8"):
        super().__init__()
        self.filename = Path(filename)
        self.encoding = encoding

    def emit(self, record: logging.LogRecord) -> None:
        """Append a formatted record to the JSONL log file."""
        try:
            message = self.format(record)
            self.filename.parent.mkdir(parents=True, exist_ok=True)
            with self.filename.open("a", encoding=self.encoding) as log_file:
                log_file.write(message)
                log_file.write(self.terminator)
        except Exception:
            self.handleError(record)
