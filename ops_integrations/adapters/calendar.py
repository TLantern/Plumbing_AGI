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
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('calendar', 'v3', credentials=creds)
    
    def create_event(self, summary: str, start_time: datetime, end_time: datetime, 
                    description: str = "", location: str = "", attendees: List[str] = None) -> Dict[str, Any]:
        """Create a new calendar event."""
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
            raise
    
    def get_events(self, start_date: datetime = None, end_date: datetime = None, 
                  max_results: int = 100) -> List[Dict[str, Any]]:
        """Get events from calendar within a date range."""
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
            raise
    
    def update_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """Update an existing calendar event."""
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
            raise
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        try:
            self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            logging.info(f"Event deleted: {event_id}")
            return True
        except HttpError as error:
            logging.error(f"Error deleting event: {error}")
            raise
    
    def sync_events(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Sync external events with Google Calendar."""
        stats = {'created': 0, 'updated': 0, 'errors': 0}
        
        for event_data in events:
            try:
                # Check if event already exists (by external ID or title/date)
                existing_events = self.get_events(
                    start_date=event_data.get('start_time'),
                    end_date=event_data.get('end_time')
                )
                
                # Simple matching logic - can be enhanced
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
