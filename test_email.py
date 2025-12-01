"""
Test script for email service
Run this to verify email configuration is working
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import email service
from services.email_service import email_service

print("=" * 70)
print("EMAIL SERVICE TEST SCRIPT")
print("=" * 70)

# Check configuration
print("\n📋 Configuration Check:")
print(f"SMTP Server: {os.getenv('SMTP_SERVER')}")
print(f"SMTP Port: {os.getenv('SMTP_PORT')}")
print(f"SMTP Username: {os.getenv('SMTP_USERNAME')}")
print(f"SMTP Password: {'*' * 16} (hidden)")

# Get test email address
print("\n" + "=" * 70)
test_email = input("Enter your email address for testing: ")

# Test OTP email
print("\n" + "=" * 70)
print("📧 TEST 1: Sending OTP Email...")
print("=" * 70)

success = email_service.send_otp_email(
    to_email=test_email,
    otp_code="123456",
    employee_name="Test User"
)

if success:
    print("✅ OTP Email sent successfully!")
    print(f"📬 Check your inbox: {test_email}")
else:
    print("❌ Failed to send OTP email")
    print("Check the error messages above")

# Test notification email
print("\n" + "=" * 70)
print("📧 TEST 2: Sending Password Changed Notification...")
print("=" * 70)

success = email_service.send_password_changed_notification(
    to_email=test_email,
    employee_name="Test User",
    ip_address="127.0.0.1"
)

if success:
    print("✅ Notification Email sent successfully!")
    print(f"📬 Check your inbox: {test_email}")
else:
    print("❌ Failed to send notification email")
    print("Check the error messages above")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
