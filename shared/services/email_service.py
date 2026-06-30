# shared/services/email_service.py
"""
Email service for sending verification codes and password reset tokens.

In development, emails are printed to console and stored in memory.
In production, this should be replaced with real SMTP integration.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

from shared.dtos import EmailSendResult, EmailAttachmentDTO

logger = logging.getLogger(__name__)


class EmailService:
    """Email service with mock implementation for development."""
    
    # In-memory storage for development/testing
    _sent_emails: Dict[str, Dict] = {}
    
    @staticmethod
    def send_email(
        subject: str,
        body_text: str,
        to: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[EmailAttachmentDTO]] = None,
        smtp_client_factory=None  # For testing/mocking
    ) -> EmailSendResult:
        """
        Send an email with optional CC, BCC, and attachments.
        
        This is a mock implementation for development. In production,
        this would integrate with real SMTP service.
        
        Args:
            subject: Email subject line
            body_text: Email body (plain text)
            to: List of recipient email addresses
            cc: List of CC recipients (optional)
            bcc: List of BCC recipients (optional)
            attachments: List of EmailAttachmentDTO objects (optional)
            smtp_client_factory: For testing (not used in mock)
        
        Returns:
            EmailSendResult with success status, recipients, and attachment count
        """
        try:
            # Prepare recipients list
            all_recipients = list(to) if to else []
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # Build email content
            email_body = body_text
            
            # Add attachment info to body for visibility
            if attachments:
                email_body += f"\n\n--- Attachments ({len(attachments)}) ---\n"
                for att in attachments:
                    email_body += f"  • {att.filename} ({att.mime_type})\n"
            
            # Log the email (mock implementation)
            EmailService._log_email(
                email=", ".join(to) if to else "no-recipients",
                subject=subject,
                body=email_body,
                email_type="general",
                cc=cc,
                bcc=bcc,
                attachment_count=len(attachments or [])
            )
            
            logger.info(f"Email sent to {to} with {len(attachments or [])} attachments")
            
            return EmailSendResult(
                success=True,
                recipients=all_recipients,
                subject=subject,
                attachment_count=len(attachments or []),
                error_message=None
            )
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return EmailSendResult(
                success=False,
                recipients=[],
                subject=subject,
                attachment_count=0,
                error_message=str(e)
            )
    
    @staticmethod
    def send_verification_email(email: str, code: str, user_name: str) -> bool:
        """
        Send verification email with 6-digit code.
        
        Args:
            email: Recipient email address
            code: 6-digit verification code
            user_name: User's name for personalization
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            subject = "Email Verification Code"
            body = f"""
Hello {user_name},

Your email verification code is:

    {code}

This code will expire in 15 minutes.

Do not share this code with anyone.

Best regards,
Bot Administration Team
"""
            
            result = EmailService.send_email(
                subject=subject,
                body_text=body,
                to=[email]
            )
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def send_password_reset_email(
        email: str,
        token: str,
        user_name: str,
        reset_url: Optional[str] = None
    ) -> bool:
        """
        Send password reset email with reset token/link.
        
        Args:
            email: Recipient email address
            token: Password reset token
            user_name: User's name for personalization
            reset_url: Optional full URL to reset password (e.g., https://app.com/reset?token=...)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            subject = "Password Reset Request"
            
            if reset_url:
                reset_link = reset_url
            else:
                reset_link = f"Use token: {token}"
            
            body = f"""
Hello {user_name},

You requested a password reset. Use the following link or token to reset your password:

    {reset_link}

This link/token will expire in 1 hour.

If you did not request this, please ignore this email.

Best regards,
Bot Administration Team
"""
            
            result = EmailService.send_email(
                subject=subject,
                body_text=body,
                to=[email]
            )
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def _log_email(
        email: str,
        subject: str,
        body: str,
        email_type: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachment_count: int = 0
    ) -> None:
        """
        Log email for development/debugging.
        
        In production, this would integrate with real email service (SendGrid, AWS SES, etc).
        """
        email_record = {
            "to": email,
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body": body,
            "type": email_type,
            "attachments": attachment_count,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store in memory for testing
        if email not in EmailService._sent_emails:
            EmailService._sent_emails[email] = []
        
        EmailService._sent_emails[email].append(email_record)
        
        # Log to console for development
        logger.debug(f"\n{'='*60}")
        logger.debug(f"EMAIL TO: {email}")
        if cc:
            logger.debug(f"CC: {', '.join(cc)}")
        if bcc:
            logger.debug(f"BCC: {', '.join(bcc)} (hidden in real email)")
        logger.debug(f"SUBJECT: {subject}")
        if attachment_count > 0:
            logger.debug(f"ATTACHMENTS: {attachment_count}")
        logger.debug(f"{'='*60}")
        logger.debug(body)
        logger.debug(f"{'='*60}\n")
    
    @staticmethod
    def get_sent_emails(email: Optional[str] = None) -> Dict:
        """
        Get sent emails (for testing).
        
        Args:
            email: If provided, get emails for specific recipient. Otherwise get all.
        
        Returns:
            Dictionary of sent emails
        """
        if email:
            return EmailService._sent_emails.get(email, [])
        return EmailService._sent_emails
    
    @staticmethod
    def clear_sent_emails() -> None:
        """Clear sent emails history (for testing)."""
        EmailService._sent_emails.clear()


# Module-level wrapper functions for backwards compatibility with imports
def send_email(
    subject: str,
    body_text: str,
    to: List[str],
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    attachments: Optional[List[EmailAttachmentDTO]] = None,
    smtp_client_factory=None
) -> EmailSendResult:
    """Wrapper for EmailService.send_email()."""
    return EmailService.send_email(
        subject=subject,
        body_text=body_text,
        to=to,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
        smtp_client_factory=smtp_client_factory
    )


def send_verification_email(email: str, code: str, user_name: str) -> bool:
    """Wrapper for EmailService.send_verification_email()."""
    return EmailService.send_verification_email(
        email=email,
        code=code,
        user_name=user_name
    )


def send_password_reset_email(
    email: str,
    token: str,
    user_name: str,
    reset_url: Optional[str] = None
) -> bool:
    """Wrapper for EmailService.send_password_reset_email()."""
    return EmailService.send_password_reset_email(
        email=email,
        token=token,
        user_name=user_name,
        reset_url=reset_url
    )
