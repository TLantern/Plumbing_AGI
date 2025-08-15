import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class CalendarAdapter:
    def __init__(self):
        self.service = None
        self.calendar_id = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        self.token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
        self.enabled = False
        self._authenticate_safe()
    
    def _authenticate_safe(self):
        """Authenticate with Google Calendar API if credentials are present; otherwise disable gracefully."""
        try:
            if not os.path.exists(self.token_path) and not os.path.exists(self.credentials_path):
                logging.warning(f"Google Calendar disabled: missing credentials at {self.credentials_path} and token at {self.token_path}")
                self.service = None
                self.enabled = False
                return

            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        logging.warning(f"Google Calendar disabled: credentials file not found at {self.credentials_path}")
                        self.service = None
                        self.enabled = False
                        return
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                    creds = flow.run_local_server(port=0)
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self.service = build('calendar', 'v3', credentials=creds)
            self.enabled = True
            logging.info("Google Calendar service initialized")
        except Exception as e:
            logging.error(f"Google Calendar auth failed: {e}")
            self.service = None
            self.enabled = False
    
    def _ensure_available(self) -> bool:
        if self.service is None:
            # Try once more in case creds appeared later
            self._authenticate_safe()
        return self.service is not None
    
    def create_event(self, summary: str, start_time: datetime, end_time: datetime, 
                    description: str = "", location: str = "", attendees: List[str] = None) -> Dict[str, Any]:
        """Create a new calendar event. Returns {} when disabled/unavailable."""
        if not self._ensure_available():
            logging.info("Calendar create_event skipped: service unavailable")
            return {}
        event = {
            'summary': summary,
            'description': description,
            'location': location,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
        }
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        try:
            event = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
            logging.info(f"Event created: {event.get('htmlLink')}")
            return event
        except HttpError as error:
            logging.error(f"Error creating event: {error}")
            return {}
    
    def get_events(self, start_date: datetime = None, end_date: datetime = None, 
                  max_results: int = 100) -> List[Dict[str, Any]]:
        """Get events from calendar within a date range. Returns [] when disabled/unavailable."""
        if not self._ensure_available():
            logging.info("Calendar get_events skipped: service unavailable")
            return []
        if not start_date:
            start_date = datetime.utcnow()
        if not end_date:
            end_date = start_date + timedelta(days=30)
        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except HttpError as error:
            logging.error(f"Error fetching events: {error}")
            return []
    
    def update_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """Update an existing calendar event. Returns {} when disabled/unavailable."""
        if not self._ensure_available():
            logging.info("Calendar update_event skipped: service unavailable")
            return {}
        try:
            event = self.service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
            for key, value in kwargs.items():
                if key in ['summary', 'description', 'location']:
                    event[key] = value
                elif key == 'start_time' and isinstance(value, datetime):
                    event['start']['dateTime'] = value.isoformat()
                elif key == 'end_time' and isinstance(value, datetime):
                    event['end']['dateTime'] = value.isoformat()
            updated_event = self.service.events().update(
                calendarId=self.calendar_id, eventId=event_id, body=event
            ).execute()
            logging.info(f"Event updated: {updated_event.get('htmlLink')}")
            return updated_event
        except HttpError as error:
            logging.error(f"Error updating event: {error}")
            return {}
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event. Returns False when disabled/unavailable."""
        if not self._ensure_available():
            logging.info("Calendar delete_event skipped: service unavailable")
            return False
        try:
            self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            logging.info(f"Event deleted: {event_id}")
            return True
        except HttpError as error:
            logging.error(f"Error deleting event: {error}")
            return False
    
    def sync_events(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Sync external events with Google Calendar. Returns zeroed stats when disabled/unavailable."""
        if not self._ensure_available():
            logging.info("Calendar sync_events skipped: service unavailable")
            return {'created': 0, 'updated': 0, 'errors': 0}
        stats = {'created': 0, 'updated': 0, 'errors': 0}
        for event_data in events:
            try:
                existing_events = self.get_events(
                    start_date=event_data.get('start_time'),
                    end_date=event_data.get('end_time')
                )
                existing_event = None
                for event in existing_events:
                    if (event.get('summary') == event_data.get('summary') and
                        event.get('start', {}).get('dateTime') == event_data.get('start_time').isoformat()):
                        existing_event = event
                        break
                if existing_event:
                    self.update_event(existing_event['id'], **event_data)
                    stats['updated'] += 1
                else:
                    self.create_event(**event_data)
                    stats['created'] += 1
            except Exception as e:
                logging.error(f"Error syncing event {event_data.get('summary')}: {e}")
                stats['errors'] += 1
        logging.info(f"Sync completed: {stats}")
        return stats
