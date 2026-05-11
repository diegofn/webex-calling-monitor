import queue
import threading
import time
import traceback

import wxcadm

from app.database.crud import CRUDOperations
from app.database.db import SessionLocal
from app.funcs import (
    is_token_expired,
    is_refresh_token_expired
)
from app.logger.logrr import lm

from fastapi.responses import JSONResponse


class AgentMonitor:
    """
    The AgentMonitor class handles the monitoring of agents for the Webex Calling Customer Assist. It initializes and maintains
    a mapping between Webex agents and their tracking from states like available, busy, away, etc.
    
    """

    def __init__(self, access_token):
        """
        Initialize AgentMonitor with given access token.
        Args:
            access_token (str): Webex API access token.
        """
        self.access_token = access_token
        self.webex = wxcadm.Webex(access_token) 
        self.webex.org.get_xsi_endpoints()
       
        
        lm.lnp(f"\nAgent Monitoring Initiated")

    @staticmethod
    def extract_event_details(event):
        """
        Extract the event details from the event data.
        Args:
            event (dict): The event data.
        """
        try:
            event_data = event.get('xsi:Event', {}).get('xsi:eventData', {})
            event_type = event_data.get('@xsi1:type', {})
            call_info = event_data.get('xsi:call', {})
            xsitargetId = event.get('xsi:Event', {}).get('xsi:targetId', {})
            call_id = call_info.get('xsi:callId', '')
            remote_party_info = call_info.get('xsi:remoteParty', {})
            userId = remote_party_info.get('xsi:userId', {})
            remote_party_name = remote_party_info.get('xsi:name', '').lower()
            userDN = remote_party_info.get('xsi:userDN', {}).get('#text', '') or remote_party_info.get('xsi:address', {}).get('#text', '')

            event_details = {
                "event_type": event_type,
                "call_id": call_id,
                "user_id": userId,
                "target_id": xsitargetId,
            }

            # lm.lnp(f"Event details: {event_details}", style="webex")
            return event_details
        except Exception as e:
            lm.lnp(f"Error extracting event details: {e}", style="error", level="error")
            return {}

    def register_agent_state(self, call_id, user_id):
        """
        Associate a given call_id with a user_id.
        Args:
            call_id (str): The unique ID of the call.
            user_id (str): The ID of the user.
        """
        lm.lnp(f"Associating Call ID {call_id} with User ID {user_id}")
        self.call_to_user_map[call_id] = user_id

    def handle_event(self, event):
        """
        Handle an event.
        """
        event_details = self.extract_event_details(event)

        if not event_details:
            lm.lnp("Event details could not be extracted.")
            return

        event_type = event_details.get('event_type')

        try:
            if event_type == "xsi:AgentStateEvent":
                self._save_agent_state_event(event, event_details)

            elif event_type in ["xsi:ACDCallAddedEvent"]:
                call_id = event_details.get('call_id')
                xsi_user_id = event_details.get('user_id')
                xsi_target_id = event_details.get('target_id')
                lm.lnp(f"Handling call event. Type: {event_type}, Call ID: {call_id}, Caller: {xsi_user_id}, Call Receiver: {xsi_target_id}")
                internal_xsi_user_id = xsi_target_id if xsi_target_id else xsi_user_id  # noqa: F841

            else:
                lm.lnp(f"Unhandled event type {event_type}")

        except Exception as e:
            lm.lnp(f"Error handling call event {e}", style='error')
            traceback.print_exc()

    def _save_agent_state_event(self, event, event_details):
        """Parse an xsi:AgentStateEvent and persist it to the database."""
        xsi_event = event.get('xsi:Event', {})
        event_data = xsi_event.get('xsi:eventData', {})
        state_info = event_data.get('xsi:agentStateInfo', {})

        event_id = xsi_event.get('xsi:eventID', '')
        sequence_number = int(xsi_event.get('xsi:sequenceNumber', 0) or 0)
        user_id = xsi_event.get('xsi:userId', '') or event_details.get('user_id', '')
        target_id = event_details.get('target_id', '')
        state = state_info.get('xsi:state', '')

        state_ts_raw = state_info.get('xsi:stateTimestamp', {})
        state_timestamp = int(state_ts_raw.get('xsi:value', 0) or 0) if isinstance(state_ts_raw, dict) else int(state_ts_raw or 0)

        sign_in_timestamp = int(state_info.get('xsi:signInTimestamp', 0) or 0)
        total_available_time = int(state_info.get('xsi:totalAvailableTime', 0) or 0)

        wrap_up_raw = state_info.get('xsi:averageWrapUpTime', {})
        average_wrap_up_time = int(wrap_up_raw.get('xsi:value', 0) or 0) if isinstance(wrap_up_raw, dict) else int(wrap_up_raw or 0)

        lm.lnp(f"AgentStateEvent — user: {user_id}, state: {state}, ts: {state_timestamp}")

        db = SessionLocal()
        try:
            crud = CRUDOperations(db)
            crud.create_agent_event(
                event_id=event_id,
                sequence_number=sequence_number,
                user_id=user_id,
                target_id=target_id,
                event_type=event_details.get('event_type', ''),
                state=state,
                state_timestamp=state_timestamp,
                sign_in_timestamp=sign_in_timestamp,
                total_available_time=total_available_time,
                average_wrap_up_time=average_wrap_up_time,
                created_at=time.time(),
            )
        finally:
            db.close()

    def monitor_agents(self, events_queue):
        """
        Monitor all agents for the Webex organization in Webex Customer Assist
        Args:
            events_queue (queue.Queue): The queue storing the events.
        """
        lm.lnp('monitor_agents called')

        while True:  # Start an infinite loop to get the messages as they are placed in Queue
            try:
                event = events_queue.get()  # Get the event from the queue
                if event:
                    self.handle_event(event)  # Handle the event
                    time.sleep(0.5)
            except Exception as e:
                lm.lnp(traceback.format_exc(), style='debug')
                lm.lnp(f"Error in the monitoring loop: {e}", style="error", level="error")

    def setup_xsi_events(self):
        """Initialize XSI events and set up a thread to monitor agent states continuously."""
        try:
            lm.lnp("Initializing Agent Monitor with provided access token.")

            events = wxcadm.XSIEvents(self.webex.org)
            events_queue = queue.Queue()
            channel = events.open_channel(events_queue)
            subscription_response = channel.subscribe("Call Center Agent")

            if subscription_response:
                lm.lnp(f"Subscribed to 'Call Center Agent' event package {subscription_response}", level="info")
            else:
                lm.lnp("Failed to subscribe to 'Call Center Agent' event package.", level="error")
                return False

            lm.lnp("Starting thread to monitor agents...", style="info", level="info")
            monitor_thread = threading.Thread(target=self.monitor_agents, args=(events_queue,), daemon=True)
            monitor_thread.start()

            if monitor_thread.is_alive():
                lm.lnp("Event monitoring thread is running.", style="success", level="info")
                lm.lnp("\n")
                lm.p_panel(
                    "[bright_red]Agent Monitoring has been started for the organization...[/bright_red]",
                    title="[white]Webex setup complete. Ready for agents state changes.[/white]",
                    style="webex",
                    expand=False
                )
                return True
            else:
                lm.lnp("Event monitoring thread failed to start.", level="error")
                return False
        except Exception as e:
            lm.logger.exception("Failed to setup webex calling agent monitoring: ", exc_info=e)
            return False

async def check_token(db):
    try:
        crud = CRUDOperations(db)
        admin_token_info = crud.read_admin_token()

        # Return both validation result and token
        if admin_token_info and not is_token_expired(admin_token_info) and not is_refresh_token_expired(admin_token_info):
            admin_access_token = admin_token_info["access_token"]
            return True, admin_access_token  
    except Exception as e:
        lm.logger.error(f"Error accessing admin token: {e}")
        
    # Return False and None if token is invalid or an error occurred
    return False, None  


async def start_agent_monitoring():
    """
    Start the agent monitoring process by initializing the AgentMonitor class and setting up XSI events on server start if the admin token is valid in the database.
    """
    db = SessionLocal()
    try:
        # Check if the admin token is valid
        token_valid, admin_access_token = await check_token(db)  
        if not token_valid:
            lm.logger.error("Invalid or expired admin token.")
            return JSONResponse(content={"message": "Invalid or expired admin token"}, status_code=403)

        lm.logger.info("Admin token in DB is valid, starting agent monitoring")
        
        # Setup monitoring of XSI events
        agent_monitor = AgentMonitor(admin_access_token)
        agent_monitor.setup_xsi_events()  
        return JSONResponse(content={"message": "Agent monitoring started successfully"}, status_code=200)
    except Exception as e:
        lm.logger.error(f"Failed to initiate agent monitoring: {e}")
        return JSONResponse(status_code=500, content={"message": f"Failed to initiate agent monitoring: {str(e)}"})
    finally:
        db.close()
