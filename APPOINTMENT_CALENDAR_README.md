# Appointment Calendar Integration

This document describes the implementation of automatic appointment calendar integration that adds confirmed appointments to the frontend calendar in real-time.

## Overview

When operators confirm appointments on the backend, the system now automatically:
1. Sends a WebSocket message to the frontend
2. Adds the appointment as a visual event to the calendar
3. Provides interactive event details on click

## Implementation Details

### Backend Changes

#### New Function: `_send_appointment_confirmation_to_frontend`

**Location:** `ops_integrations/services/phone_service.py` and `ops_integrations/adapters/phone.py`

**Purpose:** Sends appointment confirmation messages to the frontend via WebSocket

**Parameters:**
- `call_sid`: Unique call identifier
- `customer_name`: Customer's name
- `service_type`: Type of plumbing service
- `appointment_time`: Scheduled appointment datetime
- `address`: Service address
- `phone`: Customer's phone number

**WebSocket Message Format:**
```json
{
  "type": "appointment_confirmed",
  "data": {
    "callSid": "call_123",
    "event": {
      "id": "appointment_call_123",
      "title": "Service Type - Customer Name",
      "start": "2025-08-16T20:37:10.938648Z",
      "end": "2025-08-16T22:37:10.938648Z",
      "customer_name": "John Smith",
      "service_type": "Emergency Plumbing Repair",
      "address": "123 Main St, Anytown, USA",
      "phone": "+1234567890",
      "call_sid": "call_123",
      "backgroundColor": "#10b981",
      "borderColor": "#059669",
      "textColor": "#ffffff"
    },
    "ts": "2025-08-16T18:37:10.939723Z"
  }
}
```

#### Integration Points

The appointment confirmation function is called from:
1. **`/ops/action/approve` endpoint** - When operators manually approve appointments
2. **`_finalize_booking_if_ready` function** - When appointments are automatically finalized

### Frontend Changes

#### New Interface: `CalendarEvent`

**Location:** `frontend/pages/dashboard.tsx`

```typescript
interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  customer_name: string;
  service_type: string;
  address: string;
  phone: string;
  call_sid: string;
  backgroundColor: string;
  borderColor: string;
  textColor: string;
}
```

#### Enhanced Calendar Component

**Updates to `FullCalendarComponent`:**
- Added `events` prop to accept calendar events
- Added `handleEventClick` function for interactive event details
- Events display with green background for confirmed appointments

#### WebSocket Message Handler

**New message type:** `appointment_confirmed`

When received, the frontend:
1. Adds the event to the calendar state
2. Removes any existing event with the same ID (prevents duplicates)
3. Shows a system action notification
4. Displays the event visually on the calendar

#### CSS Styling

**Location:** `frontend/styles/globals.css`

Added styles for calendar events:
- Rounded corners and hover effects
- Proper text overflow handling
- Consistent spacing and typography

## Usage Flow

1. **Customer calls** and requests an appointment
2. **AI system** suggests a time slot
3. **Customer confirms** the appointment by saying "YES"
4. **System sends** the message: "You'll be sent an SMS with your booking details once your appointment is confirmed. Thanks for choosing SafeHarbour, have a great rest of your day." and hangs up
5. **Operator reviews** the job ticket in the dashboard
6. **Operator approves** the appointment (or it auto-finalizes)
7. **Backend sends** appointment confirmation via WebSocket
8. **Frontend receives** the message and adds event to calendar
9. **Calendar displays** the appointment with green styling
10. **Users can click** events to view appointment details

## Testing

Run the test script to verify functionality:

```bash
python3 test_appointment_calendar.py
```

This test:
- Creates mock appointment data
- Sends appointment confirmation messages
- Verifies message structure and required fields
- Confirms WebSocket communication works

## Event Details

When users click on calendar events, they see:
- Customer name
- Service type
- Address
- Phone number
- Appointment time

## Visual Design

- **Background Color:** Green (#10b981) for confirmed appointments
- **Border Color:** Darker green (#059669)
- **Text Color:** White (#ffffff)
- **Hover Effects:** Subtle lift and shadow
- **Event Display:** Block format with rounded corners

## Error Handling

- WebSocket failures are logged but don't break the appointment flow
- Missing event data is handled gracefully
- Duplicate events are prevented by ID-based filtering
- Timezone issues are handled with proper ISO formatting

## Call Flow Changes

### Updated User Experience

When a customer confirms an appointment time by saying "YES":

1. **Immediate Response**: The system immediately responds with: "You'll be sent an SMS with your booking details once your appointment is confirmed. Thanks for choosing SafeHarbour, have a great rest of your day."

2. **Call Termination**: The call is automatically hung up after delivering this message

3. **Operator Review**: The appointment request is sent to operators for review and approval

4. **SMS Confirmation**: Once approved, the customer receives an SMS with booking details

This creates a smoother customer experience where they don't need to wait on hold while operators review the request.

## Future Enhancements

Potential improvements:
- Event editing capabilities
- Appointment status updates (rescheduled, cancelled)
- Integration with external calendar systems
- Email/SMS notifications for calendar updates
- Drag-and-drop appointment rescheduling 