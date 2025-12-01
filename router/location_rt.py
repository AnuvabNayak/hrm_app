"""
Location Tracking Routes

GDPR Compliant:
- Explicit permission required
- Users can revoke anytime
- Auto-delete after 90 days
- Audit trail of all access

Access Control:
- Employees: Request/manage own location
- Admins/Managers: View all locations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import logging

from db import get_db
from dependencies import get_current_user, allow_admin, allow_manager
from models import (
    User, Employee, LocationPermission, LocationPermissionStatus,
    EmployeeLocation, LocationAccessLog
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["Location Tracking"])


# ============================================================================
# SCHEMAS (Request/Response Models)
# ============================================================================

class LocationPermissionRequest(BaseModel):
    """Employee requests to enable location tracking"""
    track_always: bool = False
    track_work_hours_only: bool = True


class LocationPermissionResponse(BaseModel):
    """Response to permission request"""
    permission_id: int
    status: str
    message: str
    
    class Config:
        from_attributes = True


class LocationUpdateRequest(BaseModel):
    """Location data from mobile app"""
    latitude: float = Field(..., ge=-90, le=90, description="GPS latitude -90 to +90")
    longitude: float = Field(..., ge=-180, le=180, description="GPS longitude -180 to +180")
    accuracy: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")
    address: Optional[str] = Field(None, max_length=500, description="Reverse geocoding")
    location_source: str = Field(default="gps", description="gps, wifi, or cellular")


class EmployeeLocationOut(BaseModel):
    """Location data for admin/manager view"""
    id: int
    employee_id: int
    employee_name: str
    latitude: float
    longitude: float
    accuracy: Optional[float]
    address: Optional[str]
    recorded_at: datetime
    
    class Config:
        from_attributes = True


class LocationHistoryItem(BaseModel):
    """Single location history record"""
    id: int
    latitude: float
    longitude: float
    address: Optional[str]
    recorded_at: datetime
    accuracy: Optional[float]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_employee_from_user(db: Session, user_id: int) -> Employee:
    """Get employee from user_id, raise 404 if not found"""
    employee = db.query(Employee).filter(Employee.user_id == user_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    return employee


def log_location_access(
    db: Session,
    accessing_user_id: int,
    accessing_user_role: str,
    viewed_employee_id: Optional[int],
    action: str,
    ip_address: Optional[str] = None
):
    """Log location access for GDPR compliance"""
    access_log = LocationAccessLog(
        accessing_user_id=accessing_user_id,
        accessing_user_role=accessing_user_role,
        viewed_employee_id=viewed_employee_id,
        action=action,
        ip_address=ip_address
    )
    db.add(access_log)
    db.commit()
    logger.info(f"Location access logged: {action} by user {accessing_user_id}")


def cleanup_old_locations(db: Session, retention_days: int = 90):
    """Delete location records older than retention days (GDPR compliance)"""
    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    
    old_records = db.query(EmployeeLocation).filter(
        EmployeeLocation.recorded_at < cutoff_date
    ).count()
    
    if old_records > 0:
        db.query(EmployeeLocation).filter(
            EmployeeLocation.recorded_at < cutoff_date
        ).delete()
        db.commit()
        logger.info(f"Deleted {old_records} location records older than {retention_days} days")


def is_work_hours() -> bool:
    """Check if current time is within work hours (9 AM - 6 PM IST)"""
    ist = timezone(timedelta(hours=5, minutes=30))
    current_hour = datetime.now(ist).hour
    return 9 <= current_hour < 18


# ============================================================================
# PERMISSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/permission/request", response_model=LocationPermissionResponse, status_code=201)
async def request_location_permission(
    request: LocationPermissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Employee requests to enable location tracking.
    
    GDPR Compliance:
    - Explicit consent: Yes (user must click allow)
    - Purpose: Field employee tracking, safety
    - Data: GPS coordinates only
    - Retention: 90 days (auto-delete)
    - Right to revoke: Yes (anytime)
    
    Mobile flow:
    1. User clicks "Allow Location Access" in app
    2. Native iOS/Android permission dialog appears
    3. If granted, send lat/long to this endpoint
    4. Backend stores permission and starts tracking
    """
    
    try:
        employee = get_employee_from_user(db, current_user.id)
    except HTTPException:
        raise
    
    # Check if permission record exists
    permission = db.query(LocationPermission).filter(
        LocationPermission.employee_id == employee.id
    ).first()
    
    if permission is None:
        # Create new permission record
        permission = LocationPermission(
            employee_id=employee.id,
            status=LocationPermissionStatus.GRANTED,
            granted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            track_always=request.track_always,
            track_work_hours_only=request.track_work_hours_only
        )
        db.add(permission)
        logger.info(f"✓ Location permission CREATED for employee {employee.name} (ID: {employee.id})")
    else:
        # Update existing permission
        permission.status = LocationPermissionStatus.GRANTED
        permission.granted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        permission.track_always = request.track_always
        permission.track_work_hours_only = request.track_work_hours_only
        logger.info(f"✓ Location permission UPDATED for employee {employee.name} (ID: {employee.id})")
    
    db.commit()
    db.refresh(permission)
    
    return LocationPermissionResponse(
        permission_id=permission.id,
        status=permission.status,
        message="Location tracking enabled. You can revoke this anytime from Settings."
    )


@router.get("/permission/status")
async def get_permission_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if employee has granted location permission"""
    
    try:
        employee = get_employee_from_user(db, current_user.id)
    except HTTPException:
        raise
    
    permission = db.query(LocationPermission).filter(
        LocationPermission.employee_id == employee.id
    ).first()
    
    if permission is None:
        return {
            "has_permission": False,
            "status": LocationPermissionStatus.NEVER_ASKED,
            "message": "Please grant location access",
            "granted_at": None
        }
    
    return {
        "has_permission": permission.status == LocationPermissionStatus.GRANTED,
        "status": permission.status,
        "track_always": permission.track_always,
        "track_work_hours_only": permission.track_work_hours_only,
        "granted_at": permission.granted_at,
        "message": f"Status: {permission.status.value}"
    }


@router.post("/permission/revoke")
async def revoke_location_permission(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Employee revokes location tracking.
    
    GDPR Right: User can withdraw consent anytime.
    After revocation: No new locations tracked.
    Existing data: Kept for 90 days, then deleted.
    """
    
    try:
        employee = get_employee_from_user(db, current_user.id)
    except HTTPException:
        raise
    
    permission = db.query(LocationPermission).filter(
        LocationPermission.employee_id == employee.id
    ).first()
    
    if permission is None or permission.status != LocationPermissionStatus.GRANTED:
        raise HTTPException(
            status_code=400,
            detail="No active location permission to revoke"
        )
    
    # Mark as revoked
    permission.status = LocationPermissionStatus.REVOKED
    permission.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    
    logger.warning(f"⚠️  Location permission REVOKED for employee {employee.name} (ID: {employee.id})")
    
    deletion_date = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)).date()
    
    return {
        "status": "revoked",
        "message": "Location tracking disabled. Your historical data will be deleted after 90 days.",
        "data_deletion_date": str(deletion_date)
    }


# ============================================================================
# LOCATION UPDATE ENDPOINT (Called by Mobile App)
# ============================================================================

@router.post("/update", status_code=201)
async def update_employee_location(
    request: LocationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    req: Request = None
):
    """
    Mobile app sends current location.
    
    Called: Every 30 seconds (configurable interval)
    Only if: Permission status is GRANTED
    Data: Lat/long, accuracy, timestamp
    
    This endpoint:
    1. Validates permission
    2. Checks if tracking is allowed (during work hours?)
    3. Stores location in database
    4. Deletes old data (>90 days)
    
    Rate limit: 5 updates per minute per user
    """
    
    try:
        employee = get_employee_from_user(db, current_user.id)
    except HTTPException:
        raise
    
    # Check permission
    permission = db.query(LocationPermission).filter(
        LocationPermission.employee_id == employee.id
    ).first()
    
    if permission is None or permission.status != LocationPermissionStatus.GRANTED:
        raise HTTPException(
            status_code=403,
            detail="Location tracking not permitted. Please enable in Settings."
        )
    
    # Check if tracking is allowed during current time
    if permission.track_work_hours_only:
        if not is_work_hours():
            return {
                "status": "not_recorded",
                "reason": "Outside work hours",
                "message": "Location not tracked outside 9 AM - 6 PM IST"
            }
    
    # Create location record
    location = EmployeeLocation(
        employee_id=employee.id,
        permission_id=permission.id,
        latitude=request.latitude,
        longitude=request.longitude,
        accuracy=request.accuracy,
        address=request.address,
        location_source=request.location_source,
        recorded_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    
    db.add(location)
    db.commit()
    db.refresh(location)
    
    # Cleanup old records periodically (every 100 locations)
    record_count = db.query(EmployeeLocation).count()
    if record_count % 100 == 0:
        cleanup_old_locations(db)
    
    await broadcast_location_to_managers(employee.id, employee.name, location)
    
    logger.debug(
        f"✓ Location recorded for {employee.name}: "
        f"({request.latitude:.4f}, {request.longitude:.4f}), "
        f"Accuracy: {request.accuracy}m"
    )
    
    return {
        "status": "recorded",
        "location_id": location.id,
        "recorded_at": location.recorded_at.isoformat()
    }


# ============================================================================
# ADMIN/MANAGER VIEW ENDPOINTS
# ============================================================================

@router.get(
    "/admin/employees-locations",
    response_model=List[EmployeeLocationOut],
    dependencies=[Depends(allow_admin)]
)
async def get_all_employees_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    req: Request = None
):
    """
    Admin/Manager view: See all employees' current locations.
    
    Access Control: Admin/Manager only
    Audit: Every view is logged
    Data: Only if permission is GRANTED
    """
    
    # Log access for audit trail
    log_location_access(
        db,
        current_user.id,
        current_user.role,
        None,
        "viewed_all_employees_locations",
        req.client.host if req else None
    )
    
    # Get latest location for each employee with permission
    locations = db.query(EmployeeLocation).join(
        LocationPermission,
        EmployeeLocation.permission_id == LocationPermission.id
    ).join(
        Employee,
        EmployeeLocation.employee_id == Employee.id
    ).filter(
        LocationPermission.status == LocationPermissionStatus.GRANTED
    ).order_by(
        desc(EmployeeLocation.recorded_at)
    ).all()
    
    # Group by employee to get latest location only
    latest_locations = {}
    for location in locations:
        if location.employee_id not in latest_locations:
            latest_locations[location.employee_id] = location
    
    results = []
    for location in latest_locations.values():
        employee = db.query(Employee).filter(Employee.id == location.employee_id).first()
        if employee:
            results.append(EmployeeLocationOut(
                id=location.id,
                employee_id=location.employee_id,
                employee_name=employee.name,
                latitude=location.latitude,
                longitude=location.longitude,
                accuracy=location.accuracy,
                address=location.address,
                recorded_at=location.recorded_at
            ))
    
    logger.info(f"Admin {current_user.username} viewed all employee locations ({len(results)} employees)")
    
    return results


@router.get(
    "/admin/employee/{employee_id}/location-history",
    response_model=List[LocationHistoryItem],
    dependencies=[Depends(allow_admin)]
)
async def get_employee_location_history(
    employee_id: int,
    days: int = Query(7, ge=1, le=90, description="Number of days to fetch (max 90)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    req: Request = None
):
    """
    Get location history for specific employee (last N days).
    
    GDPR Audit: Every view is logged.
    Max 90 days for privacy.
    """
    
    # Verify employee exists
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Log access
    log_location_access(
        db,
        current_user.id,
        current_user.role,
        employee_id,
        f"viewed_employee_history_{days}days",
        req.client.host if req else None
    )
    
    # Get locations from last N days
    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    
    locations = db.query(EmployeeLocation).filter(
        and_(
            EmployeeLocation.employee_id == employee_id,
            EmployeeLocation.recorded_at >= cutoff_date
        )
    ).order_by(
        desc(EmployeeLocation.recorded_at)
    ).all()
    
    logger.info(
        f"Admin {current_user.username} viewed location history for "
        f"employee {employee.name} ({len(locations)} records)"
    )
    
    return [
        LocationHistoryItem(
            id=loc.id,
            latitude=loc.latitude,
            longitude=loc.longitude,
            address=loc.address,
            recorded_at=loc.recorded_at,
            accuracy=loc.accuracy
        )
        for loc in locations
    ]


@router.get(
    "/admin/audit-trail",
    dependencies=[Depends(allow_admin)]
)
async def get_location_audit_trail(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    View audit trail: Who accessed location data?
    
    GDPR Compliance: Track all data access.
    """
    
    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    
    logs = db.query(LocationAccessLog).filter(
        LocationAccessLog.accessed_at >= cutoff_date
    ).order_by(
        desc(LocationAccessLog.accessed_at)
    ).all()
    
    return [
        {
            "id": log.id,
            "accessing_user_id": log.accessing_user_id,
            "accessing_user_role": log.accessing_user_role,
            "viewed_employee_id": log.viewed_employee_id,
            "action": log.action,
            "accessed_at": log.accessed_at,
            "ip_address": log.ip_address
        }
        for log in logs
    ]


# ============================================================================
# SCHEDULED CLEANUP JOB (Run this with APScheduler)
# ============================================================================

def cleanup_old_locations_job(db: Session):
    """
    Scheduled job to delete old location records.
    GDPR: Delete records older than 90 days.
    
    Add to your scheduler in main.py:
    scheduler.add_job(
        cleanup_old_locations_job,
        'cron',
        hour=3,  # 3 AM IST
        minute=0,
        args=[db]
    )
    """
    try:
        cleanup_old_locations(db, retention_days=90)
        logger.info("✓ Location cleanup job completed successfully")
    except Exception as e:
        logger.error(f"✗ Location cleanup job failed: {e}")


# ============================================================================
# WEBSOCKET ENDPOINT (Add to router/location_rt.py)
# ============================================================================

from services.location_websocket_service import location_manager, broadcast_location_to_managers
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/locations")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    WebSocket endpoint for managers to receive live location updates.
    
    Manager calls: GET ws://api.local:8000/location/ws/locations?token=xxx
    Receives: Real-time location updates as JSON
    Closes: When manager logs out
    
    Access: Manager and Admin only
    """
    
    # Verify manager/admin role
    if current_user.role not in ["admin", "manager"]:
        await websocket.close(code=4003, reason="Not authorized")
        logger.warning(f"Unauthorized WebSocket attempt by user {current_user.id}")
        return
    
    # Connect to WebSocket
    await location_manager.connect(websocket, current_user.id)
    
    try:
        while True:
            # Keep connection alive
            # Managers don't send data, only receive
            data = await websocket.receive_text()
            
            # Optional: Handle any incoming messages (e.g., filters, ping)
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        location_manager.disconnect(current_user.id)
        logger.info(f"Manager {current_user.id} disconnected from WebSocket")
    
    except Exception as e:
        logger.error(f"WebSocket error for manager {current_user.id}: {e}")
        location_manager.disconnect(current_user.id)
