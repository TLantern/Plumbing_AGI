from typing import List
from ops_integrations.models import Job

class CalendarAdapter:
    def __init__(self, provider: str = "google"):
        self.provider = provider
        # Init OAuth2 clients

    def list_events(self, start: str, end: str) -> List[Job]:
        # TODO: fetch and map calendar events to Job models
        return []

    def create_event(self, job: Job) -> None:
        # TODO: push Job as calendar event
        pass