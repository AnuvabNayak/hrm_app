"""
Email Service for Password Reset
Handles sending OTP and notification emails via SMTP
Created: 2025-11-17
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service for sending password reset emails via Gmail SMTP.
    
    Features:
    - Send OTP codes for password reset
    - Send confirmation emails after password change
    - Professional HTML-formatted emails
    - Automatic fallback to plain text
    """
    
    def __init__(self):
        """Initialize email service with configuration from environment variables."""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)
        self.from_name = os.getenv("SMTP_FROM_NAME", "HRM System")
        
        # Validate configuration
        if not self.smtp_username or not self.smtp_password:
            logger.warning("⚠️  SMTP credentials not configured in .env file!")
            logger.warning("Email sending will fail until SMTP_USERNAME and SMTP_PASSWORD are set")
    
    def send_otp_email(
        self,
        to_email: str,
        otp_code: str,
        employee_name: str = "User"
    ) -> bool:
        """
        Send OTP code via email for password reset.
        
        Args:
            to_email: Recipient email address
            otp_code: 6-digit OTP code (e.g., "482916")
            employee_name: Name of the employee (for personalization)
            
        Returns:
            True if sent successfully, False otherwise
            
        Example:
            success = email_service.send_otp_email(
                to_email="john@company.com",
                otp_code="482916",
                employee_name="John Doe"
            )
        """
        subject = "Password Reset OTP - HRM System"
        
        # HTML email body - Professional design
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    margin: 0;
                    padding: 0;
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; 
                    padding: 30px 20px; 
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .content {{ 
                    background: white; 
                    padding: 40px 30px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .otp-code {{ 
                    font-size: 36px; 
                    font-weight: bold; 
                    color: #667eea; 
                    letter-spacing: 8px; 
                    text-align: center; 
                    padding: 25px; 
                    background: #f0f4ff; 
                    border: 3px dashed #667eea;
                    border-radius: 10px;
                    margin: 25px 0;
                }}
                .info-box {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .footer {{ 
                    text-align: center; 
                    color: #777; 
                    font-size: 12px; 
                    padding: 20px;
                    margin-top: 20px;
                }}
                .warning {{ 
                    color: #dc3545; 
                    font-weight: bold;
                    text-align: center;
                    margin-top: 20px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset Request</h1>
                </div>
                <div class="content">
                    <p style="font-size: 16px;">Hello <strong>{employee_name}</strong>,</p>
                    
                    <p>We received a request to reset your password for your HRM System account.</p>
                    
                    <p style="font-size: 18px; font-weight: bold; margin-top: 25px;">
                        Your One-Time Password (OTP):
                    </p>
                    
                    <div class="otp-code">{otp_code}</div>
                    
                    <div class="info-box">
                        <p style="margin: 0;"><strong>⏰ Important:</strong></p>
                        <ul style="margin: 10px 0;">
                            <li>This code will expire in <strong>15 minutes</strong></li>
                            <li>This code can only be used <strong>once</strong></li>
                            <li>Enter this code on the password reset page</li>
                        </ul>
                    </div>
                    
                    <p>If you didn't request this password reset, please ignore this email or contact your administrator immediately.</p>
                    
                    <div class="warning">
                        ⚠️ Never share this code with anyone!
                    </div>
                </div>
                <div class="footer">
                    <p>This is an automated email from HRM System</p>
                    <p>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}</p>
                    <p>If you have any questions, please contact your system administrator</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback (for email clients that don't support HTML)
        text_body = f"""
        Password Reset Request - HRM System
        
        Hello {employee_name},
        
        We received a request to reset your password.
        
        Your OTP Code: {otp_code}
        
        ⏰ This code will expire in 15 minutes.
        ⏰ This code can only be used once.
        
        If you didn't request this password reset, please ignore this email.
        
        ⚠️  Never share this code with anyone!
        
        ---
        Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}
        HRM System - Automated Email
        """
        
        return self._send_email(to_email, subject, html_body, text_body)
    
    def send_password_changed_notification(
        self,
        to_email: str,
        employee_name: str = "User",
        ip_address: str = "Unknown"
    ) -> bool:
        """
        Send notification email after successful password change.
        
        Args:
            to_email: Recipient email address
            employee_name: Name of the employee
            ip_address: IP address of the request (for security tracking)
            
        Returns:
            True if sent successfully, False otherwise
            
        Example:
            success = email_service.send_password_changed_notification(
                to_email="john@company.com",
                employee_name="John Doe",
                ip_address="192.168.1.100"
            )
        """
        subject = "Password Changed Successfully - HRM System"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .header {{ 
                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    color: white; 
                    padding: 30px 20px; 
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .content {{ 
                    background: white; 
                    padding: 40px 30px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .success {{ 
                    color: #28a745; 
                    font-size: 20px; 
                    font-weight: bold;
                    text-align: center;
                    margin: 20px 0;
                }}
                .details {{ 
                    background: #f8f9fa; 
                    padding: 20px; 
                    margin: 20px 0;
                    border-radius: 8px;
                    border-left: 4px solid #28a745;
                }}
                .footer {{ 
                    text-align: center; 
                    color: #777; 
                    font-size: 12px; 
                    padding: 20px;
                }}
                .alert {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Password Changed</h1>
                </div>
                <div class="content">
                    <p style="font-size: 16px;">Hello <strong>{employee_name}</strong>,</p>
                    
                    <div class="success">
                        ✓ Your password has been changed successfully!
                    </div>
                    
                    <p>This email confirms that your password was recently changed for your HRM System account.</p>
                    
                    <div class="details">
                        <p style="margin: 0; font-weight: bold;">Change Details:</p>
                        <ul style="margin: 10px 0;">
                            <li><strong>Date & Time:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}</li>
                            <li><strong>IP Address:</strong> {ip_address}</li>
                            <li><strong>Status:</strong> Successful</li>
                        </ul>
                    </div>
                    
                    <div class="alert">
                        <p style="margin: 0;"><strong>⚠️ Didn't make this change?</strong></p>
                        <p style="margin: 10px 0;">If you did not change your password, please contact your system administrator immediately. Your account may be compromised.</p>
                    </div>
                    
                    <p>You can now use your new password to log in to the HRM System.</p>
                </div>
                <div class="footer">
                    <p>This is an automated security notification from HRM System</p>
                    <p>Please do not reply to this email</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        Password Changed Successfully - HRM System
        
        Hello {employee_name},
        
        ✓ Your password has been changed successfully!
        
        Change Details:
        - Date & Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}
        - IP Address: {ip_address}
        - Status: Successful
        
        ⚠️  Didn't make this change?
        If you did not change your password, please contact your system 
        administrator immediately. Your account may be compromised.
        
        ---
        HRM System - Automated Security Notification
        """
        
        return self._send_email(to_email, subject, html_body, text_body)
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """
        Internal method to send email via SMTP.
        
        This method handles the actual email sending using Gmail SMTP.
        It creates a multipart message with both HTML and plain text versions.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_body: HTML content (primary)
            text_body: Plain text content (fallback)
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Check if credentials are configured
        if not self.smtp_username or not self.smtp_password:
            logger.error("❌ SMTP credentials not configured in .env file")
            logger.error("Cannot send email without SMTP_USERNAME and SMTP_PASSWORD")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Attach both plain text and HTML versions
            # Email clients will use HTML if available, otherwise plain text
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Connect to SMTP server and send
            logger.info(f"📧 Connecting to SMTP server: {self.smtp_server}:{self.smtp_port}")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Enable security
                server.starttls()
                logger.info("🔒 TLS enabled")
                
                # Login
                server.login(self.smtp_username, self.smtp_password)
                logger.info(f"✅ Logged in as: {self.smtp_username}")
                
                # Send message
                server.send_message(msg)
                logger.info(f"✅ Email sent successfully to: {to_email}")
            
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP Authentication Failed: {e}")
            logger.error("Check your SMTP_USERNAME and SMTP_PASSWORD in .env")
            logger.error("Make sure you're using App Password, not regular Gmail password")
            return False
            
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP Error: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Unexpected error sending email: {e}")
            return False


# Create global instance for use across the application
email_service = EmailService()


# Example usage (for testing):
if __name__ == "__main__":
    """
    This section runs only when you execute this file directly.
    Use it for testing the email service.
    
    Usage:
        python services/email_service.py
    """
    print("=" * 60)
    print("EMAIL SERVICE TEST")
    print("=" * 60)
    
    # Test sending OTP email
    print("\n📧 Testing OTP email...")
    success = email_service.send_otp_email(
        to_email="test@example.com",  # Replace with your email
        otp_code="123456",
        employee_name="Test User"
    )
    
    if success:
        print("✅ OTP email test successful!")
    else:
        print("❌ OTP email test failed!")
    
    print("\n" + "=" * 60)
