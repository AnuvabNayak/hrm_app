"""
WebSocket Service for Real-Time Location Updates

Managers connect to receive live location updates as employees
send their positions.

Usage:
- Manager opens WebSocket connection
- Receives live location updates
- Connection drops if manager logs out
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import logging

logger = logging.getLogger(__name__)


class LocationWebSocketManager:
    """
    Manages WebSocket connections for real-time location updates.
    
    Broadcast: When employee sends location, all connected managers receive update
    Connection: Manager connects, waits for updates
    Disconnect: Manager closes app, connection drops
    """
    
    def __init__(self):
        # Store active manager connections
        # Key: manager_user_id, Value: WebSocket connection
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, manager_id: int):
        """Manager opens WebSocket connection"""
        await websocket.accept()
        self.active_connections[manager_id] = websocket
        logger.info(
            f"✓ Manager {manager_id} connected to location WebSocket "
            f"({len(self.active_connections)} active connections)"
        )
    
    def disconnect(self, manager_id: int):
        """Manager closes WebSocket connection"""
        if manager_id in self.active_connections:
            del self.active_connections[manager_id]
            logger.info(
                f"✓ Manager {manager_id} disconnected from location WebSocket "
                f"({len(self.active_connections)} active connections)"
            )
    
    async def broadcast_location(self, employee_data: dict):
        """
        Broadcast location update to all connected managers.
        
        Called after employee sends location:
        1. Location received from mobile app
        2. Stored in database
        3. Broadcast to all managers
        
        Args:
            employee_data: {
                "employee_id": 5,
                "employee_name": "Rajesh Kumar",
                "latitude": 20.5937,
                "longitude": 78.9629,
                "recorded_at": "2025-12-01 14:30:00",
                "accuracy": 5.2
            }
        """
        
        message = json.dumps({
            "type": "location_update",
            "data": employee_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Send to all connected managers
        disconnected = []
        
        for manager_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_text(message)
                logger.debug(f"Sent location to manager {manager_id}")
            except Exception as e:
                logger.warning(f"Failed to send to manager {manager_id}: {e}")
                disconnected.append(manager_id)
        
        # Clean up disconnected managers
        for manager_id in disconnected:
            self.disconnect(manager_id)
    
    async def broadcast_permission_change(self, employee_id: int, action: str):
        """
        Notify managers when employee grants/revokes permission.
        
        action: "permission_granted" or "permission_revoked"
        """
        message = json.dumps({
            "type": "permission_change",
            "employee_id": employee_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        for manager_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_text(message)
            except Exception:
                pass


# Global instance
location_manager = LocationWebSocketManager()


# Helper function to use in router
async def broadcast_location_to_managers(employee_id: int, employee_name: str, location):
    """Called after storing location in database"""
    
    employee_data = {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "accuracy": location.accuracy,
        "address": location.address,
        "recorded_at": location.recorded_at.isoformat()
    }
    
    await location_manager.broadcast_location(employee_data)


# Import timezone for broadcast_permission_change
from datetime import datetime, timezone
from sqlalchemy.orm import Session

def cleanup_old_locations(db: Session, retention_days: int = 90):
    """Delete locations older than retention_days (GDPR compliance)"""
    from datetime import datetime, timedelta, timezone
    from models import EmployeeLocation
    
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        deleted_count = db.query(EmployeeLocation).filter(
            EmployeeLocation.recorded_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"✅ Deleted {deleted_count} old location records")
        return deleted_count
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Location cleanup failed: {e}")
        raise
