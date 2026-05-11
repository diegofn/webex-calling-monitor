from pydantic import BaseModel, Field


class TimeLocationData(BaseModel):
    """
    Pydantic model for the TimeLocation data.
    """
    sessionToken: str = Field(..., alias='sessionToken')    # Webex session token
    time: str   # Time in HH:MM format
    latitude: float    # Latitude
    longitude: float    # Longitude
