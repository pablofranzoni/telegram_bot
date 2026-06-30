"""Unit tests for shared.services.email_service."""

from shared.dtos import EmailAttachmentDTO, EmailSendResult
from shared.services import email_service


class TestSendEmailMock:
    """Tests for send_email mock implementation."""
    
    def test_send_email_basic(self):
        """Test basic email sending."""
        # Clear previous emails
        email_service.EmailService.clear_sent_emails()
        
        result = email_service.EmailService.send_email(
            subject="Test Subject",
            body_text="Test Body",
            to=["test@example.com"]
        )
        
        assert result.success is True
        assert result.subject == "Test Subject"
        assert result.recipients == ["test@example.com"]
        assert result.attachment_count == 0
        assert result.error_message is None
    
    def test_send_email_with_cc_and_bcc(self):
        """Test email with CC and BCC."""
        email_service.EmailService.clear_sent_emails()
        
        result = email_service.EmailService.send_email(
            subject="Test",
            body_text="Body",
            to=["dest@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"]
        )
        
        assert result.success is True
        assert result.recipients == ["dest@example.com", "cc@example.com", "bcc@example.com"]
    
    def test_send_email_with_attachments(self):
        """Test email with attachments."""
        email_service.EmailService.clear_sent_emails()
        
        attachment = EmailAttachmentDTO(
            filename="test.pdf",
            content_bytes=b"PDF content",
            mime_type="application/pdf"
        )
        
        result = email_service.EmailService.send_email(
            subject="With Attachment",
            body_text="See attachment",
            to=["test@example.com"],
            attachments=[attachment]
        )
        
        assert result.success is True
        assert result.attachment_count == 1
    
    def test_send_email_with_multiple_attachments(self):
        """Test email with multiple attachments."""
        email_service.EmailService.clear_sent_emails()
        
        attachments = [
            EmailAttachmentDTO(
                filename=f"file{i}.pdf",
                content_bytes=b"content",
                mime_type="application/pdf"
            )
            for i in range(3)
        ]
        
        result = email_service.EmailService.send_email(
            subject="Multiple Attachments",
            body_text="See attachments",
            to=["test@example.com"],
            attachments=attachments
        )
        
        assert result.success is True
        assert result.attachment_count == 3
    
    def test_send_email_stores_in_memory(self):
        """Test that sent emails are stored in memory."""
        email_service.EmailService.clear_sent_emails()
        
        email_service.EmailService.send_email(
            subject="Stored",
            body_text="Body",
            to=["stored@example.com"]
        )
        
        sent_emails = email_service.EmailService.get_sent_emails("stored@example.com")
        assert len(sent_emails) > 0
        assert sent_emails[0]["subject"] == "Stored"
    
    def test_send_email_returns_email_send_result(self):
        """Test that send_email returns EmailSendResult."""
        email_service.EmailService.clear_sent_emails()
        
        result = email_service.EmailService.send_email(
            subject="Test",
            body_text="Body",
            to=["test@example.com"]
        )
        
        assert isinstance(result, EmailSendResult)
        assert hasattr(result, "success")
        assert hasattr(result, "recipients")
        assert hasattr(result, "subject")
        assert hasattr(result, "attachment_count")
        assert hasattr(result, "error_message")


class TestSendVerificationEmail:
    """Tests for send_verification_email."""
    
    def test_send_verification_email_returns_true(self):
        """Test that send_verification_email returns True on success."""
        email_service.EmailService.clear_sent_emails()
        
        result = email_service.EmailService.send_verification_email(
            email="test@example.com",
            code="123456",
            user_name="Test User"
        )
        
        assert result is True
    
    def test_send_verification_email_contains_code(self):
        """Test that verification email contains the code."""
        email_service.EmailService.clear_sent_emails()
        
        code = "654321"
        email_service.EmailService.send_verification_email(
            email="test@example.com",
            code=code,
            user_name="Test User"
        )
        
        sent_emails = email_service.EmailService.get_sent_emails("test@example.com")
        assert len(sent_emails) > 0
        assert code in sent_emails[0]["body"]
    
    def test_send_verification_email_has_correct_subject(self):
        """Test that verification email has correct subject."""
        email_service.EmailService.clear_sent_emails()
        
        email_service.EmailService.send_verification_email(
            email="test@example.com",
            code="123456",
            user_name="Test User"
        )
        
        sent_emails = email_service.EmailService.get_sent_emails("test@example.com")
        assert "Verification" in sent_emails[0]["subject"]


class TestSendPasswordResetEmail:
    """Tests for send_password_reset_email."""
    
    def test_send_password_reset_email_returns_true(self):
        """Test that send_password_reset_email returns True on success."""
        email_service.EmailService.clear_sent_emails()
        
        result = email_service.EmailService.send_password_reset_email(
            email="test@example.com",
            token="reset_token_123",
            user_name="Test User"
        )
        
        assert result is True
    
    def test_send_password_reset_email_contains_token(self):
        """Test that reset email contains the token."""
        email_service.EmailService.clear_sent_emails()
        
        token = "my_reset_token"
        email_service.EmailService.send_password_reset_email(
            email="test@example.com",
            token=token,
            user_name="Test User"
        )
        
        sent_emails = email_service.EmailService.get_sent_emails("test@example.com")
        assert len(sent_emails) > 0
        assert token in sent_emails[0]["body"]
    
    def test_send_password_reset_email_with_url(self):
        """Test that reset email works with reset URL."""
        email_service.EmailService.clear_sent_emails()
        
        reset_url = "https://example.com/reset?token=abc123"
        email_service.EmailService.send_password_reset_email(
            email="test@example.com",
            token="abc123",
            user_name="Test User",
            reset_url=reset_url
        )
        
        sent_emails = email_service.EmailService.get_sent_emails("test@example.com")
        assert reset_url in sent_emails[0]["body"]
    
    def test_send_password_reset_email_has_correct_subject(self):
        """Test that reset email has correct subject."""
        email_service.EmailService.clear_sent_emails()
        
        email_service.EmailService.send_password_reset_email(
            email="test@example.com",
            token="token123",
            user_name="Test User"
        )
        
        sent_emails = email_service.EmailService.get_sent_emails("test@example.com")
        assert "Password Reset" in sent_emails[0]["subject"]
