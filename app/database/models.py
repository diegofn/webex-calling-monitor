from sqlalchemy import Column, Integer, String, Float, BigInteger
from app.database.db import Base


class AdminToken(Base):
    """
    This class represents the AdminToken table in the database.
    It stores the access token, refresh token, and other related information for the admin user.
    """
    __tablename__ = 'admin_tokens'
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String, nullable=False)
    expires_in = Column(Integer)
    refresh_token = Column(String)
    refresh_token_expires_in = Column(Integer)
    token_type = Column(String)
    scope = Column(String)
    expires_at = Column(Float)
    session_token = Column(String, nullable=False)


class UserList(Base):
    """
    This class represents the UserList table in the database.
    It stores the user_id and session_token for each user.
    """
    __tablename__ = 'user_list'
    user_id = Column(String, primary_key=True, index=True)
    session_token = Column(String, nullable=False)


class WebexUser(Base):
    """
    Stores Webex Calling users discovered during monitoring initialization.
    """
    __tablename__ = 'webex_users'
    xsi_user_id = Column(String, primary_key=True, index=True)
    webex_user_id = Column(String, nullable=False)
    name = Column(String)
    phone_number = Column(String)
    extension = Column(String)
    updated_at = Column(Float, nullable=False)


class AgentEvent(Base):
    """
    Stores agent state events received from the XSI event channel.
    """
    __tablename__ = 'agent_events'
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False, index=True)
    sequence_number = Column(Integer)
    user_id = Column(String, nullable=False, index=True)
    target_id = Column(String, index=True)
    event_type = Column(String)
    state = Column(String)
    state_timestamp = Column(BigInteger, index=True)
    sign_in_timestamp = Column(BigInteger)
    total_available_time = Column(Integer)
    average_wrap_up_time = Column(Integer)
    created_at = Column(Float, nullable=False)


class QueueEvent(Base):
    """
    Stores ACD queue call events received from the XSI event channel.
    """
    __tablename__ = 'queue_events'
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, nullable=False, index=True)
    sequence_number = Column(Integer)
    user_id = Column(String, index=True)
    target_id = Column(String, index=True)
    event_type = Column(String)
    call_id = Column(String, index=True)
    ext_tracking_id = Column(String)
    caller_name = Column(String)
    caller_address = Column(String)
    caller_type = Column(String)
    add_time = Column(BigInteger, index=True)
    acd_name = Column(String)
    acd_number = Column(String)
    acd_priority = Column(String)
    created_at = Column(Float, nullable=False)
