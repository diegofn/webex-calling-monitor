from datetime import datetime, timezone, timedelta
from threading import local

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.logger.logrr import lm
from app.database.models import AdminToken, UserList, AgentEvent, WebexUser


def extract_access_token(token_object):
    """ Extract Webex access token from token object """
    if token_object and "access_token" in token_object:
        return token_object["access_token"]
    else:
        raise ValueError("Access token not found in the provided token object.")


class CRUDOperations:
    """
    Class for performing CRUD operations on the database.

    Attributes:
        _instance (CRUDOperations): The instance of the CRUDOperations class.
        _local (local): The threading.local object.
    """
    _instance = None
    _local = local()

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(CRUDOperations, cls).__new__(cls)
        return cls._instance

    def __init__(self, db: Session):
        self._local.db = db

    @property
    def db(self):
        return self._local.db

    def commit_db(self, db_item, operation_name):
        """
        Common command call. Commits the db_item to the database and handles any SQLAlchemyError.

        Args:
            db_item: The database item to commit.
            operation_name (str): The name of the operation being performed.
        """
        self.db.add(db_item)
        try:
            self.db.commit()
        except SQLAlchemyError as e:
            lm.lnp(f"Error occurred while committing {operation_name} to the database: {e}")
        return db_item

    def create_admin_token(self, access_token: str, expires_in: int, refresh_token: str, refresh_token_expires_in: int, token_type: str,
                           scope: list, expires_at: float, session_token: str):
        """
        Creates a new AdminToken entry in the database.

        Args:
            access_token (str): The access token.
            expires_in (int): The duration in seconds that the access token is valid.
            refresh_token (str): The refresh token.
            refresh_token_expires_in (int): The duration in seconds that the refresh token is valid.
            token_type (str): The type of the token.
            scope (str): The scope of the token.
            expires_at (float): The timestamp when the token expires.
        """
        # Convert the scope list to a string
        scope_str = ' '.join(scope)

        db_item = AdminToken(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            refresh_token_expires_in=refresh_token_expires_in,
            token_type=token_type,
            scope=scope_str,
            expires_at=expires_at,
            session_token=session_token,
        )
        return self.commit_db(db_item=db_item, operation_name='create_admin_token')

    def read_admin_token(self):
        """
        Retrieves the AdminToken entry from the database.
        """
        admin_token_entry = self.db.query(AdminToken).first()
        if admin_token_entry is not None:
            admin_token_data = {
                "access_token": admin_token_entry.access_token,
                "expires_in": admin_token_entry.expires_in,
                "refresh_token": admin_token_entry.refresh_token,
                "refresh_token_expires_in": admin_token_entry.refresh_token_expires_in,
                "token_type": admin_token_entry.token_type,
                "scope": admin_token_entry.scope,
                "expires_at": admin_token_entry.expires_at,
                "session_token": admin_token_entry.session_token
            }
            # lm.lnp(f"Retrieved admin token from the database: {admin_token_data}")
            return admin_token_data
        else:
            lm.lnp("No admin token entry found.", level="warning", style="warning")
            return None

    def update_admin_token(self, access_token: str, expires_in: int, refresh_token: str, refresh_token_expires_in: int, token_type: str, scope: list, expires_at: float,
                           session_token: str):
        """
        Replaces the admin token in the database. Deletes all existing entries and adds a new one.

        Args:
            access_token (str): The access token.
            expires_in (int): The duration in seconds that the access token is valid.
            refresh_token (str): The refresh token.
            refresh_token_expires_in (int): The duration in seconds that the refresh token is valid.
            token_type (str): The type of the token.
            scope (str): The scope of the token.
            expires_at (float): The timestamp when the token expires.
        """
        self.delete_all_admin_tokens()
        return self.create_admin_token(access_token, expires_in, refresh_token, refresh_token_expires_in, token_type, scope, expires_at, session_token)

    def delete_all_admin_tokens(self):
        """
        Deletes all AdminToken entries from the database.
        """
        self.db.query(AdminToken).delete()
        try:
            self.db.commit()
        except SQLAlchemyError as e:
            lm.lnp(f"Error occurred while deleting all admin tokens from the database: {e}", level="error", style="error")

    def get_admin_access_token(self):
        admin_token_object = self.read_admin_token()
        if not admin_token_object:
            raise ValueError("Admin token object is missing or invalid.")
        return extract_access_token(admin_token_object)

    def create_user_list_entry(self, user_id: str, session_token: str):
        """
        Creates a new UserList entry in the database.

        Args:
            db (Session): The database session.
            user_id (str): The user ID.
            session_token (str): The session token.
        """
        db_item = UserList(
            user_id=user_id,
            session_token=session_token
        )
        return self.commit_db(db_item=db_item, operation_name='create_user_list_entry')

    def read_user_list(self, user_id: str = None, session_token: str = None):
        """
        Retrieves the UserList entry from the database using the user_id or session_token.

        Args:
            user_id (str, optional): The user ID.
            session_token (str, optional): The session token.
        """
        if user_id:
            user_list_entry = self.db.query(UserList).filter(UserList.user_id == user_id).first()
            search_param = user_id
            search_type = 'user ID'
        elif session_token:
            user_list_entry = self.db.query(UserList).filter(UserList.session_token == session_token).first()
            search_param = session_token
            search_type = 'session token'
        else:
            raise ValueError("Either user_id or session_token must be provided.")

        if user_list_entry is not None:
            user_list_data = {
                "user_id": user_list_entry.user_id,
                "session_token": user_list_entry.session_token
            }
            # lm.lnp(f"Retrieved user list from the database: {user_list_data}")
            return user_list_data
        else:
            lm.lnp(f"No user list entry found for the provided {search_type}: {search_param}")
            return None

    def update_user_list_entry(self, user_id: str, session_token: str):
        """
        Updates an existing UserList entry in the database.

        Args:
            db (Session): The database session.
            user_id (str): The user ID.
            session_token (str): The session token.
        """
        db_item = self.db.query(UserList).filter(UserList.user_id == user_id).first()

        if db_item:
            # If a user exists, update the session_token
            db_item.session_token = session_token
            return self.commit_db(db_item=db_item, operation_name='update_user_list_entry')
        else:
            raise ValueError(f"No UserList entry found for user_id: {user_id}")

    def delete_user_list_entry(self, user_id: str):
        """
        Deletes the UserList entry from the database using the user ID.

        Args:
            user_id (str): The user ID.
        """
        db_item = self.db.query(UserList).filter(UserList.user_id == user_id).first()
        if db_item:
            self.db.delete(db_item)
            return self.commit_db(db_item=db_item, operation_name='delete_user_list_entry')

    def create_agent_event(self, event_id: str, sequence_number: int, user_id: str, target_id: str,
                           event_type: str, state: str, state_timestamp: int, sign_in_timestamp: int,
                           total_available_time: int, average_wrap_up_time: int, created_at: float):
        """
        Persists an agent state event received from the XSI channel.
        """
        db_item = AgentEvent(
            event_id=event_id,
            sequence_number=sequence_number,
            user_id=user_id,
            target_id=target_id,
            event_type=event_type,
            state=state,
            state_timestamp=state_timestamp,
            sign_in_timestamp=sign_in_timestamp,
            total_available_time=total_available_time,
            average_wrap_up_time=average_wrap_up_time,
            created_at=created_at,
        )
        return self.commit_db(db_item=db_item, operation_name='create_agent_event')

    def upsert_webex_user(self, xsi_user_id: str, webex_user_id: str, name: str,
                          phone_number: str, extension: str, updated_at: float):
        """
        Creates or updates a WebexUser record.
        Skips the write if all tracked fields are already up to date.
        """
        existing = self.db.query(WebexUser).filter(WebexUser.xsi_user_id == xsi_user_id).first()

        if existing is None:
            db_item = WebexUser(
                xsi_user_id=xsi_user_id,
                webex_user_id=webex_user_id,
                name=name,
                phone_number=phone_number,
                extension=extension,
                updated_at=updated_at,
            )
            return self.commit_db(db_item=db_item, operation_name='create_webex_user')

        if (existing.webex_user_id != webex_user_id or existing.name != name
                or existing.phone_number != phone_number or existing.extension != extension):
            existing.webex_user_id = webex_user_id
            existing.name = name
            existing.phone_number = phone_number
            existing.extension = extension
            existing.updated_at = updated_at
            return self.commit_db(db_item=existing, operation_name='update_webex_user')

        return existing

