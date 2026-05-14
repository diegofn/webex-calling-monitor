import queue
import threading
import time
import traceback
import json
from pprint import pformat

import wxcadm

from app.database.crud import CRUDOperations
from app.database.db import SessionLocal
from app.funcs import (
    is_token_expired,
    is_refresh_token_expired
)
from app.logger.logrr import lm

from fastapi.responses import JSONResponse


class QueueMonitor:
    """
    The QueueMonitor class handles the monitoring of queue events for the Webex Calling Customer Assist. It initializes and maintains
    a mapping between Webex queue events and their tracking.
    
    """

    def __init__(self, access_token):
        """
        Initialize QueueMonitor with given access token.
        Args:
            access_token (str): Webex API access token.
        """
        self.access_token = access_token
        self.webex = wxcadm.Webex(access_token) 
        self.webex.org.get_xsi_endpoints()
       
        
        lm.lnp(f"\nQueue Monitoring Initiated")

    @staticmethod
    def extract_event_details(event):
        """
        Extract the event details from the event data.
        Args:
            event (dict): The event data.
        """
        try:
            xsi_event = event.get('xsi:Event', {})
            event_data = xsi_event.get('xsi:eventData', {})
            event_type = event_data.get('@xsi1:type', '')
            target_id = xsi_event.get('xsi:targetId', '')
            user_id = xsi_event.get('xsi:userId', '')

            event_details = {
                "event_type": event_type,
                "target_id": target_id,
                "user_id": user_id,
            }

            # Agent call events use xsi:call
            call_info = event_data.get('xsi:call', {})
            if call_info:
                remote_party = call_info.get('xsi:remoteParty', {})
                event_details.update({
                    "call_id": call_info.get('xsi:callId', ''),
                    "remote_party_name": remote_party.get('xsi:name', '').lower(),
                    "remote_party_address": (
                        remote_party.get('xsi:userDN', {}).get('#text', '')
                        or remote_party.get('xsi:address', {}).get('#text', '')
                    ),
                })

            # Queue ACD events use xsi:queueEntry
            queue_entry = event_data.get('xsi:queueEntry', {})
            if queue_entry:
                remote_party = queue_entry.get('xsi:remoteParty', {})
                acd_number_raw = queue_entry.get('xsi:acdNumber', {})
                event_details.update({
                    "call_id": queue_entry.get('xsi:callId', ''),
                    "ext_tracking_id": queue_entry.get('xsi:extTrackingId', ''),
                    "caller_name": remote_party.get('xsi:name', '').strip(),
                    "caller_address": remote_party.get('xsi:address', {}).get('#text', ''),
                    "caller_type": remote_party.get('xsi:callType', ''),
                    "add_time": int(queue_entry.get('xsi:addTime', 0) or 0),
                    "acd_name": queue_entry.get('xsi:acdName', ''),
                    "acd_number": acd_number_raw.get('#text', '') if isinstance(acd_number_raw, dict) else str(acd_number_raw),
                    "acd_priority": queue_entry.get('xsi:acdPriority', ''),
                })

            return event_details
        except Exception as e:
            lm.lnp(f"Error extracting event details: {e}", style="error", level="error")
            return {}


    def handle_event(self, event):
        """
        Handle an event.
        """
        event_details = self.extract_event_details(event)
        lm.lnp(f"Handling queue event. Type: {event_details.get('event_type')}")

        if not event_details:
            lm.lnp("Event details could not be extracted.")
            return

        event_type = event_details.get('event_type')

        try:
            if event_type in [
                "xsi:ACDCallAddedEvent",
                "xsi:ACDCallOfferedToAgentEvent",
                "xsi:ACDCallRemovedEvent",
                "xsi:ACDCallAbandonedEvent",
                "xsi:ACDCallAnsweredByAgentEvent"
            ]:
                lm.lnp(f"Saving queue event {event_type}")
                self._save_queue_event(event, event_details)

            else:
                lm.lnp(f"Unhandled event type {event_type}")

        except Exception as e:
            lm.lnp(f"Error handling call event {e}", style='error')
            traceback.print_exc()

    def _save_queue_event(self, event, event_details):
        """Parse an ACD queue call event and persist it to the database."""
        xsi_event = event.get('xsi:Event', {})

        event_id = xsi_event.get('xsi:eventID', '')
        sequence_number = int(xsi_event.get('xsi:sequenceNumber', 0) or 0)
        user_id = event_details.get('user_id', '')
        target_id = event_details.get('target_id', '')

        lm.lnp(
            f"QueueEvent — type: {event_details.get('event_type')}, "
            f"call: {event_details.get('call_id')}, queue: {event_details.get('acd_name')}"
        )

        db = SessionLocal()
        try:
            crud = CRUDOperations(db)
            crud.create_queue_event(
                event_id=event_id,
                sequence_number=sequence_number,
                user_id=user_id,
                target_id=target_id,
                event_type=event_details.get('event_type', ''),
                call_id=event_details.get('call_id', ''),
                ext_tracking_id=event_details.get('ext_tracking_id', ''),
                caller_name=event_details.get('caller_name', ''),
                caller_address=event_details.get('caller_address', ''),
                caller_type=event_details.get('caller_type', ''),
                add_time=event_details.get('add_time', 0),
                acd_name=event_details.get('acd_name', ''),
                acd_number=event_details.get('acd_number', ''),
                acd_priority=event_details.get('acd_priority', ''),
                created_at=time.time(),
            )
        finally:
            db.close()

    def monitor_queues(self, events_queue):
        """
        Monitor all queues for the Webex organization in Webex Customer Assist
        Args:
            events_queue (queue.Queue): The queue storing the events.
        """
        lm.lnp('monitor_queues called')

        while True:  # Start an infinite loop to get the messages as they are placed in Queue
            try:
                event = events_queue.get()  # Get the event from the queue
                if event:
                    try:
                        event_text = json.dumps(event, indent=2, ensure_ascii=False)
                    except (TypeError, ValueError):
                        event_text = pformat(event)
                    lm.lnp(f"Received queue event:\n{event_text}", style="debug")
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
            subscription_response = channel.subscribe("Call Center Queue")
            
            if subscription_response:
                lm.lnp(f"Subscribed to 'Call Center Queue' event package {subscription_response}", level="info")
            else:
                lm.lnp("Failed to subscribe to 'Call Center Queue' event package.", level="error")
                return False

            lm.lnp("Starting thread to monitor queues...", style="info", level="info")
            monitor_thread = threading.Thread(target=self.monitor_queues, args=(events_queue,), daemon=True)
            monitor_thread.start()

            if monitor_thread.is_alive():
                lm.lnp("Event monitoring thread is running.", style="success", level="info")
                lm.lnp("\n")
                lm.p_panel(
                    "[bright_red]Queue Monitoring has been started for the organization...[/bright_red]",
                    title="[white]Webex setup complete. Ready for queue changes.[/white]",
                    style="webex",
                    expand=False
                )
                return True
            else:
                lm.lnp("Event monitoring thread failed to start.", level="error")
                return False
        except Exception as e:
            lm.logger.exception("Failed to setup webex calling queue monitoring: ", exc_info=e)
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


async def start_queue_monitoring():
    """
    Start the queue monitoring process by initializing the QueueMonitor class and setting up XSI events on server start if the admin token is valid in the database.
    """
    db = SessionLocal()
    try:
        # Check if the admin token is valid
        token_valid, admin_access_token = await check_token(db)  
        if not token_valid:
            lm.logger.error("Invalid or expired admin token.")
            return JSONResponse(content={"message": "Invalid or expired admin token"}, status_code=403)

        lm.logger.info("Admin token in DB is valid, starting queue monitoring")
        
        # Setup monitoring of XSI events
        queue_monitor = QueueMonitor(admin_access_token)
        queue_monitor.setup_xsi_events()  
        return JSONResponse(content={"message": "Queue monitoring started successfully"}, status_code=200)
    except Exception as e:
        lm.logger.error(f"Failed to initiate queue monitoring: {e}")
        return JSONResponse(status_code=500, content={"message": f"Failed to initiate queue monitoring: {str(e)}"})
    finally:
        db.close()
