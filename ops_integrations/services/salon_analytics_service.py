"""
Salon Analytics Service
Real-time analytics service for hairstyling business operations.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Simple replacements for deleted hairstyling_crm
class ServiceType:
    HAIRCUT = "Haircut"
    COLOR = "Hair Color"
    HIGHLIGHTS = "Highlights"

class AppointmentStatus:
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    NO_SHOW = "No Show"
    CANCELLED = "Cancelled"

# Import the comprehensive CRM from salon phone service
try:
    from ops_integrations.services.salon_phone_service import HairstylingCRM
except ImportError:
    # Fallback if import fails
    class HairstylingCRM:
        def __init__(self):
            self.current_week_metrics = {
                'total_calls': 0,
                'answered_calls': 0,
                'missed_calls': 0,
                'total_appointments': 0,
                'completed_appointments': 0,
                'total_revenue': 0.0
            }
        
        def get_dashboard_data(self):
            return {
                'current_week': self.current_week_metrics,
                'active_calls': 0,
                'recent_calls': [],
                'growth_insights': {
                    'revenue_growth_4_week': 0,
                    'insights': [],
                    'recommendations': []
                },
                'timestamp': datetime.now().isoformat()
            }

class SalonAnalyticsService:
    """Real-time salon analytics service with WebSocket support."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.crm = HairstylingCRM()
        self.active_connections: Set[WebSocket] = set()
        self.background_tasks = set()
        
    async def connect_websocket(self, websocket: WebSocket):
        """Add a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
        
        # Send initial dashboard data
        try:
            dashboard_data = self.crm.get_dashboard_data()
            await websocket.send_text(json.dumps({
                'type': 'dashboard_update',
                'data': dashboard_data
            }))
        except Exception as e:
            self.logger.error(f"Failed to send initial data: {e}")
    
    async def disconnect_websocket(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        self.logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast_update(self, message_type: str, data: Dict[str, Any]):
        """Broadcast update to all connected WebSocket clients."""
        if not self.active_connections:
            return
            
        message = json.dumps({
            'type': message_type,
            'data': data
        })
        
        # Send to all connections, remove failed ones
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        self.active_connections -= disconnected
    
    async def handle_call_event(self, call_data: Dict[str, Any]):
        """Handle incoming call events."""
        try:
            call_sid = call_data.get('call_sid')
            phone_number = call_data.get('phone_number')
            direction = call_data.get('direction', 'inbound')
            customer_name = call_data.get('customer_name')
            
            if call_data.get('event') == 'call_started':
                # Track new call
                result = self.crm.track_call(
                    call_sid=call_sid,
                    phone_number=phone_number,
                    direction=direction,
                    customer_name=customer_name
                )
                
                # Broadcast call update
                await self.broadcast_update('call_update', {
                    'call_sid': call_sid,
                    'phone_number': phone_number,
                    'direction': direction,
                    'start_time': datetime.now().isoformat(),
                    'answered': True,
                    'after_hours': result.get('after_hours', False)
                })
                
            elif call_data.get('event') == 'call_ended':
                # End call tracking
                self.crm.end_call(call_sid)
                
            elif call_data.get('event') == 'call_missed':
                # Track missed call
                self.crm.track_missed_call(phone_number)
                
                # Broadcast missed call
                await self.broadcast_update('call_update', {
                    'phone_number': phone_number,
                    'direction': 'inbound',
                    'start_time': datetime.now().isoformat(),
                    'answered': False,
                    'after_hours': not self.crm._is_business_hours(datetime.now())
                })
            
            # Send updated dashboard data
            dashboard_data = self.crm.get_dashboard_data()
            await self.broadcast_update('dashboard_update', dashboard_data)
            
        except Exception as e:
            self.logger.error(f"Failed to handle call event: {e}")
    
    async def handle_appointment_event(self, appointment_data: Dict[str, Any]):
        """Handle appointment events."""
        try:
            event_type = appointment_data.get('event')
            
            if event_type == 'appointment_scheduled':
                # Schedule new appointment
                customer_id = appointment_data.get('customer_id')
                appointment_date = datetime.fromisoformat(appointment_data.get('appointment_date'))
                service_type = appointment_data.get('service_type', 'Haircut')
                price = float(appointment_data.get('price', 0))
                call_sid = appointment_data.get('call_sid')
                notes = appointment_data.get('notes', '')
                
                result = self.crm.schedule_appointment(
                    customer_id=customer_id,
                    appointment_date=appointment_date,
                    service_type=service_type,
                    price=price,
                    call_sid=call_sid,
                    notes=notes
                )
                
                # Broadcast appointment update
                await self.broadcast_update('appointment_update', {
                    'action': 'scheduled',
                    'appointment_id': result.get('appointment_id'),
                    'customer_id': customer_id,
                    'service_type': service_type,
                    'appointment_date': appointment_date.isoformat(),
                    'price': price
                })
                
            elif event_type == 'appointment_status_update':
                # Update appointment status
                appointment_id = appointment_data.get('appointment_id')
                status = appointment_data.get('status')
                actual_price = appointment_data.get('actual_price')
                
                result = self.crm.update_appointment_status(
                    appointment_id=appointment_id,
                    status=status,
                    actual_price=actual_price
                )
                
                # Broadcast status update
                await self.broadcast_update('appointment_update', {
                    'action': 'status_update',
                    'appointment_id': appointment_id,
                    'status': status,
                    'price': actual_price or result.get('final_price', 0)
                })
            
            # Send updated dashboard data
            dashboard_data = self.crm.get_dashboard_data()
            await self.broadcast_update('dashboard_update', dashboard_data)
            
        except Exception as e:
            self.logger.error(f"Failed to handle appointment event: {e}")
    
    async def generate_weekly_report(self):
        """Generate and save weekly performance report."""
        try:
            # Save current week metrics
            success = self.crm.save_weekly_metrics()
            if success:
                self.logger.info("Weekly metrics saved successfully")
                
                # Generate insights
                insights = self.crm.generate_growth_insights()
                
                # Broadcast weekly report
                await self.broadcast_update('weekly_report', {
                    'week_start': self.crm.current_week_metrics.week_start.isoformat(),
                    'insights': insights,
                    'report_generated': datetime.now().isoformat()
                })
            
        except Exception as e:
            self.logger.error(f"Failed to generate weekly report: {e}")
    
    def start_background_tasks(self):
        """Start background tasks for periodic updates."""
        # Schedule weekly report generation (every Sunday at midnight)
        async def weekly_report_task():
            while True:
                now = datetime.now()
                # Calculate next Sunday at midnight
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0 and now.hour >= 0:
                    days_until_sunday = 7
                
                next_sunday = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
                sleep_seconds = (next_sunday - now).total_seconds()
                
                await asyncio.sleep(sleep_seconds)
                await self.generate_weekly_report()
        
        # Periodic dashboard updates (every 30 seconds)
        async def dashboard_update_task():
            while True:
                await asyncio.sleep(30)
                if self.active_connections:
                    dashboard_data = self.crm.get_dashboard_data()
                    await self.broadcast_update('dashboard_update', dashboard_data)
        
        # Start tasks
        task1 = asyncio.create_task(weekly_report_task())
        task2 = asyncio.create_task(dashboard_update_task())
        
        self.background_tasks.add(task1)
        self.background_tasks.add(task2)
        
        # Clean up finished tasks
        def task_done_callback(task):
            self.background_tasks.discard(task)
        
        task1.add_done_callback(task_done_callback)
        task2.add_done_callback(task_done_callback)

# Global service instance
salon_service = SalonAnalyticsService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    salon_service.start_background_tasks()
    logging.info("Salon Analytics Service started")
    yield
    # Shutdown
    # Cancel background tasks
    for task in salon_service.background_tasks:
        task.cancel()
    logging.info("Salon Analytics Service stopped")

# FastAPI app
app = FastAPI(
    title="Salon Analytics Service",
    description="Real-time analytics service for hairstyling business operations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/salon")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await salon_service.connect_websocket(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get('type') == 'ping':
                await websocket.send_text(json.dumps({'type': 'pong'}))
            
    except WebSocketDisconnect:
        await salon_service.disconnect_websocket(websocket)

@app.get("/salon/dashboard")
async def get_dashboard_data():
    """Get current dashboard data."""
    try:
        data = salon_service.crm.get_dashboard_data()
        return data
    except Exception as e:
        logging.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")

@app.post("/salon/call")
async def handle_call_webhook(call_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle call webhook events."""
    background_tasks.add_task(salon_service.handle_call_event, call_data)
    return {"status": "received"}

@app.post("/salon/appointment")
async def handle_appointment_webhook(appointment_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle appointment webhook events."""
    background_tasks.add_task(salon_service.handle_appointment_event, appointment_data)
    return {"status": "received"}

@app.get("/salon/metrics/weekly")
async def get_weekly_metrics(weeks_back: int = 12):
    """Get historical weekly metrics."""
    try:
        metrics = salon_service.crm.get_weekly_metrics_history(weeks_back)
        return {
            'metrics': [
                {
                    'week_start': m.week_start.isoformat(),
                    'call_metrics': m.call_metrics.__dict__,
                    'appointment_metrics': m.appointment_metrics.__dict__,
                    'growth_rate': m.growth_rate,
                    'new_customers': m.new_customers,
                    'returning_customers': m.returning_customers
                }
                for m in metrics
            ]
        }
    except Exception as e:
        logging.error(f"Failed to get weekly metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve weekly metrics")

@app.get("/salon/insights")
async def get_growth_insights():
    """Get growth insights and recommendations."""
    try:
        insights = salon_service.crm.generate_growth_insights()
        return insights
    except Exception as e:
        logging.error(f"Failed to get growth insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve growth insights")

@app.post("/salon/report/weekly")
async def generate_weekly_report(background_tasks: BackgroundTasks):
    """Manually trigger weekly report generation."""
    background_tasks.add_task(salon_service.generate_weekly_report)
    return {"status": "report generation started"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "salon_analytics",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(salon_service.active_connections)
    }

# Quick test endpoints for development
@app.post("/salon/test/call")
async def test_call_event():
    """Test endpoint to simulate a call event."""
    test_call = {
        'event': 'call_started',
        'call_sid': f'test_call_{int(datetime.now().timestamp())}',
        'phone_number': '+1234567890',
        'direction': 'inbound',
        'customer_name': 'Test Customer'
    }
    await salon_service.handle_call_event(test_call)
    return {"status": "test call event processed"}

@app.post("/salon/test/appointment")
async def test_appointment_event():
    """Test endpoint to simulate an appointment event."""
    # First create a customer
    customer_id = salon_service.crm._find_or_create_customer('+1234567890', 'Test Customer')
    
    test_appointment = {
        'event': 'appointment_scheduled',
        'customer_id': customer_id,
        'appointment_date': (datetime.now() + timedelta(days=1)).isoformat(),
        'service_type': 'Haircut',
        'price': 50.0,
        'notes': 'Test appointment'
    }
    await salon_service.handle_appointment_event(test_appointment)
    return {"status": "test appointment event processed"}

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    uvicorn.run(
        "salon_analytics_service:app",
        host="0.0.0.0",
        port=5002,
        reload=True,
        log_level="info"
    )
