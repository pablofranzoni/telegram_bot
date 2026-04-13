"""DTOs for outbound email operations."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class EmailAttachmentDTO:
    """Represents a file attachment sent by email."""

    filename: str
    content_bytes: bytes
    mime_type: str = "application/octet-stream"


@dataclass(slots=True)
class EmailSendResult:
    """Represents the outcome of sending an email."""

    success: bool
    recipients: list[str] = field(default_factory=list)
    subject: str | None = None
    attachment_count: int = 0
    error_message: str | None = None