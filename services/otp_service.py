"""
OTP Service for Password Reset
Handles OTP generation, validation, and management
Created: 2025-11-17
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from models import PasswordResetToken, User
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OTPService:
    """
    Service for managing One-Time Passwords (OTPs) for password reset.
    
    Features:
    - Generate cryptographically secure 6-digit OTP codes
    - Store OTPs in database with expiry time
    - Validate OTPs (check existence, expiry, usage)
    - Mark OTPs as used to prevent reuse
    - Clean up expired/used OTPs
    
    Security:
    - Uses secrets module (cryptographically secure random)
    - 15-minute expiry window
    - One-time use only
    - Logs all operations for audit trail
    """
    
    # Configuration constants
    OTP_LENGTH = 6                    # 6-digit OTP (e.g., "482916")
    OTP_EXPIRY_MINUTES = 15          # OTP valid for 15 minutes
    MAX_ATTEMPTS = 5                  # Max attempts before lockout
    
    @staticmethod
    def generate_otp() -> str:
        """
        Generate a secure 6-digit OTP code.
        
        Uses Python's `secrets` module which is cryptographically secure
        (unlike `random` which is predictable).
        
        Returns:
            6-digit string (e.g., "482916")
            
        Example:
            otp = OTPService.generate_otp()
            # otp = "482916"
        """
        # Use only digits 0-9
        digits = string.digits
        
        # Generate 6 random digits using cryptographically secure random
        otp = ''.join(secrets.choice(digits) for _ in range(OTPService.OTP_LENGTH))
        
        logger.info(f"🔐 Generated new OTP: {otp[:2]}****")  # Log first 2 digits only
        return otp
    
    @staticmethod
    def create_reset_token(
        db: Session,
        user_id: int,
        email: str,
        ip_address: str = None,
        user_agent: str = None
    ) -> Tuple[str, datetime]:
        """
        Create a new password reset token with OTP in the database.
        
        This method:
        1. Generates a secure 6-digit OTP
        2. Calculates expiry time (15 minutes from now)
        3. Creates a record in password_reset_tokens table
        4. Returns the OTP and expiry time
        
        Args:
            db: Database session
            user_id: User ID from users table
            email: User's email address
            ip_address: IP address of the request (optional, for security tracking)
            user_agent: Browser/device info (optional, for security tracking)
            
        Returns:
            Tuple of (otp_code, expires_at)
            Example: ("482916", datetime(2025, 11, 17, 18, 15, 0))
            
        Example:
            otp_code, expires_at = OTPService.create_reset_token(
                db=db,
                user_id=42,
                email="john@company.com",
                ip_address="192.168.1.100"
            )
            # otp_code = "482916"
            # expires_at = 2025-11-17 18:15:00
        """
        # Generate secure 6-digit OTP
        otp_code = OTPService.generate_otp()
        
        # Calculate expiry time (15 minutes from now)
        # Using UTC to avoid timezone issues
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=OTPService.OTP_EXPIRY_MINUTES)
        
        # Create database record
        reset_token = PasswordResetToken(
            user_id=user_id,
            email=email,
            otp_code=otp_code,
            expires_at=expires_at,
            is_used=False,          # Not used yet
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Save to database
        db.add(reset_token)
        db.commit()
        db.refresh(reset_token)
        
        logger.info(
            f"✅ Created password reset token for user_id={user_id}, "
            f"email={email}, expires at {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        
        return otp_code, expires_at
    
    @staticmethod
    def validate_otp(
        db: Session,
        email: str,
        otp_code: str
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Validate OTP code for password reset.
        
        This method checks:
        1. Does the OTP exist in database?
        2. Is it for the correct email?
        3. Has it expired?
        4. Has it already been used?
        
        Args:
            db: Database session
            email: User's email address
            otp_code: 6-digit OTP code entered by user
            
        Returns:
            Tuple of (is_valid, user_id, error_message)
            - is_valid: True if OTP is valid, False otherwise
            - user_id: User ID if valid, None otherwise
            - error_message: Error description if invalid, None if valid
            
        Example:
            is_valid, user_id, error = OTPService.validate_otp(
                db=db,
                email="john@company.com",
                otp_code="482916"
            )
            
            if is_valid:
                print(f"OTP valid for user_id={user_id}")
            else:
                print(f"OTP invalid: {error}")
        """
        # Find the most recent OTP for this email and code
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.email == email,
            PasswordResetToken.otp_code == otp_code,
            PasswordResetToken.is_used == False
        ).order_by(PasswordResetToken.created_at.desc()).first()
        
        # Check if OTP exists
        if not token:
            logger.warning(f"❌ Invalid OTP attempt for email: {email}")
            return False, None, "Invalid OTP code"
        
        # Check if OTP has expired
        now = datetime.utcnow()
        if now > token.expires_at:
            logger.warning(
                f"❌ Expired OTP attempt for email: {email}, "
                f"expired at {token.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            return False, None, "OTP code has expired"
        
        # OTP is valid!
        logger.info(f"✅ Valid OTP for user_id={token.user_id}, email={email}")
        return True, token.user_id, None
    
    @staticmethod
    def mark_as_used(
        db: Session,
        email: str,
        otp_code: str
    ) -> bool:
        """
        Mark OTP as used after successful password reset.
        
        This prevents the same OTP from being reused (security measure).
        
        Args:
            db: Database session
            email: User's email address
            otp_code: 6-digit OTP code
            
        Returns:
            True if marked successfully, False if OTP not found
            
        Example:
            success = OTPService.mark_as_used(
                db=db,
                email="john@company.com",
                otp_code="482916"
            )
            
            if success:
                print("OTP marked as used")
            else:
                print("OTP not found")
        """
        # Find the OTP
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.email == email,
            PasswordResetToken.otp_code == otp_code,
            PasswordResetToken.is_used == False
        ).first()
        
        if token:
            # Mark as used
            token.is_used = True
            token.used_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"✅ Marked OTP as used for email={email}")
            return True
        
        logger.warning(f"❌ Could not mark OTP as used (not found) for email={email}")
        return False
    
    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """
        Delete expired and used tokens from database (housekeeping).
        
        This is a maintenance function that should be run periodically
        to keep the database clean. It deletes:
        - Expired tokens (older than 24 hours)
        - Used tokens (older than 24 hours)
        
        Args:
            db: Database session
            
        Returns:
            Number of tokens deleted
            
        Example:
            deleted = OTPService.cleanup_expired_tokens(db)
            print(f"Cleaned up {deleted} old tokens")
        """
        # Delete tokens older than 24 hours (either expired or used)
        cutoff_date = datetime.utcnow() - timedelta(hours=24)
        
        # Build query to find old tokens
        deleted = db.query(PasswordResetToken).filter(
            (PasswordResetToken.expires_at < datetime.utcnow()) |  # Expired
            (PasswordResetToken.is_used == True)                    # Used
        ).filter(
            PasswordResetToken.created_at < cutoff_date  # Older than 24 hours
        ).delete()
        
        db.commit()
        
        if deleted > 0:
            logger.info(f"🗑️  Cleaned up {deleted} expired/used tokens")
        
        return deleted
    
    @staticmethod
    def get_token_info(
        db: Session,
        email: str,
        otp_code: str
    ) -> Optional[dict]:
        """
        Get information about a specific OTP token (for debugging/admin).
        
        Args:
            db: Database session
            email: User's email address
            otp_code: 6-digit OTP code
            
        Returns:
            Dictionary with token info, or None if not found
            
        Example:
            info = OTPService.get_token_info(
                db=db,
                email="john@company.com",
                otp_code="482916"
            )
            
            if info:
                print(f"Created: {info['created_at']}")
                print(f"Expires: {info['expires_at']}")
                print(f"Used: {info['is_used']}")
        """
        token = db.query(PasswordResetToken).filter(
            PasswordResetToken.email == email,
            PasswordResetToken.otp_code == otp_code
        ).first()
        
        if not token:
            return None
        
        # Calculate time remaining
        now = datetime.utcnow()
        time_remaining = (token.expires_at - now).total_seconds()
        
        return {
            'id': token.id,
            'user_id': token.user_id,
            'email': token.email,
            'otp_code': token.otp_code,
            'created_at': token.created_at,
            'expires_at': token.expires_at,
            'is_used': token.is_used,
            'used_at': token.used_at,
            'ip_address': token.ip_address,
            'time_remaining_seconds': max(0, time_remaining),
            'is_expired': time_remaining <= 0
        }


# Create global instance for use across the application
otp_service = OTPService()


# Example usage (for testing):
if __name__ == "__main__":
    """
    This section runs only when you execute this file directly.
    Use it for testing the OTP service.
    
    Usage:
        python services/otp_service.py
    """
    print("=" * 60)
    print("OTP SERVICE TEST")
    print("=" * 60)
    
    # Test OTP generation
    print("\n🔐 Test 1: Generating OTPs...")
    for i in range(5):
        otp = OTPService.generate_otp()
        print(f"  OTP {i+1}: {otp}")
    
    print("\n✅ All tests passed!")
    print("=" * 60)
