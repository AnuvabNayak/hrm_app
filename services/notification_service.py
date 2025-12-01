"""
Notification Service
====================
Handles: In-app notifications, email triggers
"""

from datetime import datetime, timezone, date
from sqlalchemy.orm import Session
from services.email_service import email_service
from models import Notification, User, Employee, LeaveRequest, Post
import logging

logger = logging.getLogger(__name__)

def create_notification(
    db: Session,
    user_id: int,
    ntype: str,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None
) -> Notification:
    """
    Create in-app notification for user.
    
    Args:
        db: Database session
        user_id: Target user ID
        ntype: Notification type (leave_request, leave_approved, etc.)
        title: Notification title
        message: Notification message
        related_entity_type: Entity type (e.g., "leave_request")
        related_entity_id: Entity ID
    
    Returns:
        Notification: Created notification
    """
    notification = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        is_read=False,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def notify_leave_requested(db: Session, leave_request, requester_user_id: int):
    """Notify requester that leave request was submitted."""
    create_notification(
        db,
        user_id=requester_user_id,
        ntype="leave_request",
        title="Leave request submitted",
        message=f"Your leave request for {float(leave_request.total_days)} days has been submitted and is pending approval.",
        related_entity_type="leave_request",
        related_entity_id=leave_request.id
    )


def notify_approval_pending(db: Session, leave_request, approver_user_id: int):
    """Notify approver that leave request needs their approval."""
    from models import Employee
    emp = db.query(Employee).filter(Employee.id == leave_request.employee_id).first()
    emp_name = emp.name if emp else "Employee"
    
    create_notification(
        db,
        user_id=approver_user_id,
        ntype="approval_pending",
        title="Leave approval required",
        message=f"{emp_name} has requested {float(leave_request.total_days)} days of leave. Your approval is required.",
        related_entity_type="leave_request",
        related_entity_id=leave_request.id
    )


def notify_leave_approved(db: Session, leave_request, requester_user_id: int):
    """Notify requester that leave was approved."""
    create_notification(
        db,
        user_id=requester_user_id,
        ntype="leave_approved",
        title="Leave request approved",
        message=f"Your leave request for {float(leave_request.total_days)} days has been approved.",
        related_entity_type="leave_request",
        related_entity_id=leave_request.id
    )


def notify_leave_denied(db: Session, leave_request, requester_user_id: int, reason: str | None = None):
    """Notify requester that leave was denied."""
    msg = f"Your leave request for {float(leave_request.total_days)} days has been denied."
    if reason:
        msg += f" Reason: {reason}"
    
    create_notification(
        db,
        user_id=requester_user_id,
        ntype="leave_denied",
        title="Leave request denied",
        message=msg,
        related_entity_type="leave_request",
        related_entity_id=leave_request.id
    )


def mark_as_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark notification as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()
    
    if not notification:
        return False
    
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return True


def mark_all_as_read(db: Session, user_id: int) -> int:
    """Mark all notifications as read for user."""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).update({
        "is_read": True,
        "read_at": datetime.now(timezone.utc).replace(tzinfo=None)
    })
    db.commit()
    return count


def notify_leave_requested_email(db: Session, leave_request: LeaveRequest, requester_id: int):
    """
    Send email to all managers when employee requests leave.
    
    Args:
        db: Database session
        leave_request: Leave request object
        requester_id: User ID who created the request
    """
    try:
        # Get requester details
        requester = db.query(User).filter(User.id == requester_id).first()
        if not requester:
            logger.warning(f"Requester user {requester_id} not found")
            return False
        
        # Get employee details
        employee = db.query(Employee).filter(
            Employee.id == leave_request.employee_id
        ).first()
        if not employee or not employee.user:
            logger.warning(f"Employee {leave_request.employee_id} not found")
            return False
        
        # Get all managers in approval chain
        approvers = []
        if leave_request.current_approver_id:
            approver_emp = db.query(Employee).filter(
                Employee.id == leave_request.current_approver_id
            ).first()
            if approver_emp and approver_emp.user:
                approvers.append(approver_emp.user)
        
        # Send emails to all approvers
        for approver in approvers:
            if not approver.email:
                logger.warning(f"Approver {approver.id} has no email address")
                continue
            
            subject = f"New Leave Request - {employee.user.username}"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                               color: white; padding: 30px 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .detail-box {{ background: #f8f9fa; padding: 15px; margin: 15px 0; border-left: 4px solid #667eea; border-radius: 5px; }}
                    .btn {{ display: inline-block; padding: 12px 30px; background: #667eea; 
                            color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                    .footer {{ text-align: center; color: #777; font-size: 12px; padding: 20px; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>New Leave Request</h1>
                    </div>
                    <div class="content">
                        <p>Hello <strong>{approver.username}</strong>,</p>
                        
                        <p>A new leave request requires your approval:</p>
                        
                        <div class="detail-box">
                            <p><strong>Employee:</strong> {employee.user.username}</p>
                            <p><strong>Employee Code:</strong> {employee.empcode or 'N/A'}</p>
                            <p><strong>Leave Type:</strong> {leave_request.leave_type}</p>
                            <p><strong>Start Date:</strong> {leave_request.start_date.strftime('%Y-%m-%d')}</p>
                            <p><strong>End Date:</strong> {leave_request.end_date.strftime('%Y-%m-%d')}</p>
                            <p><strong>Total Days:</strong> {leave_request.total_days}</p>
                            <p><strong>Reason:</strong> {leave_request.reason or 'Not specified'}</p>
                        </div>
                        
                        <p>Please review and approve/deny this request at your earliest convenience.</p>
                        
                        <div class="footer">
                            <p>This is an automated email from HRM System</p>
                            <p>Please do not reply to this email</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_body = f"""
            New Leave Request - HRM System
            
            Employee: {employee.user.username}
            Employee Code: {employee.empcode or 'N/A'}
            Leave Type: {leave_request.leave_type}
            Start Date: {leave_request.start_date.strftime('%Y-%m-%d')}
            End Date: {leave_request.end_date.strftime('%Y-%m-%d')}
            Total Days: {leave_request.total_days}
            Reason: {leave_request.reason or 'Not specified'}
            
            Please review and approve/deny this request.
            
            This is an automated email from HRM System
            """
            
            success = email_service.send_email(
                to_email=approver.email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )
            
            if success:
                logger.info(f"Leave request email sent to {approver.email}")
            else:
                logger.error(f"Failed to send leave request email to {approver.email}")
        
        return True
    except Exception as e:
        logger.error(f"Error in notify_leave_requested_email: {str(e)}")
        return False


def notify_leave_approved_email(db: Session, leave_request: LeaveRequest, employee_user_id: int):
    """
    Send email to employee when leave is approved.
    
    Args:
        db: Database session
        leave_request: Leave request object
        employee_user_id: User ID of employee
    """
    try:
        # Get employee user
        user = db.query(User).filter(User.id == employee_user_id).first()
        if not user or not user.email:
            logger.warning(f"Employee user {employee_user_id} not found or has no email")
            return False
        
        subject = "Leave Request Approved"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                           color: white; padding: 30px 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                .success {{ color: #28a745; font-size: 20px; font-weight: bold; text-align: center; margin: 20px 0; }}
                .detail-box {{ background: #f8f9fa; padding: 15px; margin: 15px 0; border-left: 4px solid #28a745; border-radius: 5px; }}
                .footer {{ text-align: center; color: #777; font-size: 12px; padding: 20px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Leave Request Approved</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{user.username}</strong>,</p>
                    
                    <div class="success">✓ Your leave request has been approved</div>
                    
                    <div class="detail-box">
                        <p><strong>Leave Type:</strong> {leave_request.leave_type}</p>
                        <p><strong>Start Date:</strong> {leave_request.start_date.strftime('%Y-%m-%d')}</p>
                        <p><strong>End Date:</strong> {leave_request.end_date.strftime('%Y-%m-%d')}</p>
                        <p><strong>Total Days:</strong> {leave_request.total_days}</p>
                        <p><strong>Paid Days:</strong> {leave_request.paid_days}</p>
                        <p><strong>Unpaid Days:</strong> {leave_request.unpaid_days}</p>
                    </div>
                    
                    <p>Your leave has been approved and you are all set for your time off. 
                    Please ensure that all your pending work is covered before your leave starts.</p>
                    
                    <div class="footer">
                        <p>This is an automated email from HRM System</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        Leave Request Approved - HRM System
        
        Hello {user.username},
        
        Your leave request has been approved!
        
        Leave Details:
        - Leave Type: {leave_request.leave_type}
        - Start Date: {leave_request.start_date.strftime('%Y-%m-%d')}
        - End Date: {leave_request.end_date.strftime('%Y-%m-%d')}
        - Total Days: {leave_request.total_days}
        - Paid Days: {leave_request.paid_days}
        - Unpaid Days: {leave_request.unpaid_days}
        
        Please ensure that all your pending work is covered before your leave starts.
        
        This is an automated email from HRM System
        """
        
        success = email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )
        
        if success:
            logger.info(f"Leave approved email sent to {user.email}")
        else:
            logger.error(f"Failed to send leave approved email to {user.email}")
        
        return success
    except Exception as e:
        logger.error(f"Error in notify_leave_approved_email: {str(e)}")
        return False

def notify_leave_denied_email(db: Session, leave_request: LeaveRequest, employee_user_id: int, admin_notes: str = None):
    """
    Send email to employee when leave is denied.
    
    Args:
        db: Database session
        leave_request: Leave request object
        employee_user_id: User ID of employee
        admin_notes: Reason for denial
    """
    try:
        # Get employee user
        user = db.query(User).filter(User.id == employee_user_id).first()
        if not user or not user.email:
            logger.warning(f"Employee user {employee_user_id} not found or has no email")
            return False
        
        subject = "Leave Request Denied"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); 
                           color: white; padding: 30px 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                .notice {{ color: #dc3545; font-size: 18px; font-weight: bold; text-align: center; margin: 20px 0; }}
                .detail-box {{ background: #fff3cd; padding: 15px; margin: 15px 0; border-left: 4px solid #ffc107; border-radius: 5px; }}
                .footer {{ text-align: center; color: #777; font-size: 12px; padding: 20px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Leave Request Decision</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{user.username}</strong>,</p>
                    
                    <div class="notice">✗ Your leave request has been denied</div>
                    
                    <div class="detail-box">
                        <p><strong>Leave Type:</strong> {leave_request.leave_type}</p>
                        <p><strong>Requested Dates:</strong> {leave_request.start_date.strftime('%Y-%m-%d')} to {leave_request.end_date.strftime('%Y-%m-%d')}</p>
                        <p><strong>Total Days:</strong> {leave_request.total_days}</p>
                        {"<p><strong>Reason:</strong> " + admin_notes + "</p>" if admin_notes else ""}
                    </div>
                    
                    <p>You can reapply for leave if the circumstances change or if you have additional information to support your request.</p>
                    
                    <div class="footer">
                        <p>This is an automated email from HRM System</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        Leave Request Denied - HRM System
        
        Hello {user.username},
        
        We regret to inform you that your leave request has been denied.
        
        Leave Details:
        - Leave Type: {leave_request.leave_type}
        - Requested Dates: {leave_request.start_date.strftime('%Y-%m-%d')} to {leave_request.end_date.strftime('%Y-%m-%d')}
        - Total Days: {leave_request.total_days}
        {f"- Reason: {admin_notes}" if admin_notes else ""}
        
        You can reapply for leave if you have additional information to support your request.
        
        This is an automated email from HRM System
        """
        
        success = email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )
        
        if success:
            logger.info(f"Leave denied email sent to {user.email}")
        else:
            logger.error(f"Failed to send leave denied email to {user.email}")
        
        return success
    except Exception as e:
        logger.error(f"Error in notify_leave_denied_email: {str(e)}")
        return False

def notify_post_created_email(db: Session, post: Post):
    """
    Send email to all employees when a new post is published.
    
    Args:
        db: Database session
        post: Post object
    """
    try:
        # Get post author
        author = db.query(User).filter(User.id == post.author_id).first()
        if not author:
            logger.warning(f"Post author {post.author_id} not found")
            return False
        
        # Get all employees
        employees = db.query(Employee).all()
        if not employees:
            logger.warning("No employees found to send post email")
            return False
        
        # Create post summary (first 200 characters)
        summary = post.content[:200] + "..." if len(post.content) > 200 else post.content
        
        subject = f"New Update: {post.title}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 30px 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                .post-box {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-left: 4px solid #667eea; border-radius: 5px; }}
                .btn {{ display: inline-block; padding: 12px 30px; background: #667eea; 
                        color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }}
                .footer {{ text-align: center; color: #777; font-size: 12px; padding: 20px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Update</h1>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    
                    <p>A new update has been posted on the HRM System:</p>
                    
                    <div class="post-box">
                        <h2 style="margin-top: 0; color: #667eea;">{post.title}</h2>
                        <p><strong>Posted by:</strong> {author.username}</p>
                        <p><strong>Date:</strong> {post.created_at.strftime('%Y-%m-%d %H:%M')}</p>
                        <hr>
                        <p>{summary}</p>
                    </div>
                    
                    <p>Log in to the HRM System to read the full post and share your thoughts.</p>
                    
                    <div class="footer">
                        <p>This is an automated email from HRM System</p>
                        <p>Please do not reply to this email</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        New Update - HRM System
        
        Title: {post.title}
        Posted by: {author.username}
        Date: {post.created_at.strftime('%Y-%m-%d %H:%M')}
        
        {summary}
        
        Log in to the HRM System to read the full post.
        
        This is an automated email from HRM System
        """
        
        # Send to all employees
        success_count = 0
        for employee in employees:
            if not employee.user or not employee.user.email:
                logger.warning(f"Employee {employee.id} has no user or email")
                continue
            
            success = email_service.send_email(
                to_email=employee.user.email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )
            
            if success:
                success_count += 1
            else:
                logger.error(f"Failed to send post email to {employee.user.email}")
        
        logger.info(f"Post email sent to {success_count}/{len(employees)} employees")
        return success_count > 0
    except Exception as e:
        logger.error(f"Error in notify_post_created_email: {str(e)}")
        return False
