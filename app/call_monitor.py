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


class CallMonitor:
    """
    The CallMonitor class handles the monitoring of calls for the Webex organization. It initializes and maintains
    a mapping between Webex users and their corresponding call sessions and tracks active and ended calls.

    """

    def __init__(self, access_token):
        """
        Initialize CallMonitor with given access token.
        Args:
            access_token (str): Webex API access token.
        """
        self.access_token = access_token
        self.webex = wxcadm.Webex(access_token)  # Initialize XSI API
        self.webex.org.get_xsi_endpoints()  # Fetch the XSI endpoints for the organization
        self.all_people = self.webex.org.people.webex_calling()  # Fetch all people in the organization
        self.xsi_user_map = {}  # Mapping of person ID to their display name and ID
        self.call_to_user_map = {}  # Track / map call to user

        try:
            # Initialize the xsi_user_map with users and their respective details.
            for person in self.all_people:
                person.start_xsi()  # Start the XSI for each person
                person_id = person.id  # Fetch the person ID
                xsi_instance = wxcadm.xsi.XSI(parent=person)  # Create the XSI instance for each person

                phone_numbers_info = person.wxc_numbers.get('phoneNumbers', []) if isinstance(person.wxc_numbers, dict) else []  # Fetch the phone numbers for the person
                primary_phone_number = next((pn for pn in phone_numbers_info if pn.get('primary', False)),
                                            phone_numbers_info[0] if phone_numbers_info else None)  # Fetch the primary phone number
                direct_number = primary_phone_number.get('directNumber') if primary_phone_number else "No number available"  # Fetch the direct number
                extension = primary_phone_number.get('extension') if primary_phone_number and 'extension' in primary_phone_number else ""  # Fetch the extension

                profile_info = xsi_instance.profile  # Fetch the profile information for the XSI user instance
                if profile_info is not None:
                    xsi_user_id = profile_info.get('user_id')  # Fetch the xsi user ID

                    # Store the user details in the xsi_user_map for easy access
                    self.xsi_user_map[xsi_user_id] = {
                        "remote_party_name": person.name,
                        "xsi_user_id": xsi_user_id,  # Store the XSI user ID
                        "webex_user_id": person_id,  # Store the Webex user ID
                        "phone_number": direct_number,  # Store the concatenated phone number and extension
                        "extension": extension,  # Store the extension
                        "xsi_instance": xsi_instance,  # Store the XSI instance
                        # "profile_info": profile_info  # Store all the profile information
                    }

            lm.print_xsi_user_map(self.xsi_user_map)  # Print the XSI user map
            lm.lnp(f"\nCall Monitoring Initiated for {len(self.xsi_user_map)} users.")

            db = SessionLocal()
            try:
                crud = CRUDOperations(db)
                synced = 0
                for xsi_user_id, user_data in self.xsi_user_map.items():
                    crud.upsert_webex_user(
                        xsi_user_id=xsi_user_id,
                        webex_user_id=user_data['webex_user_id'],
                        name=user_data['remote_party_name'],
                        phone_number=user_data['phone_number'],
                        extension=user_data['extension'],
                        updated_at=time.time(),
                    )
                    synced += 1
                lm.lnp(f"Synced {synced} users to the database.")
            finally:
                db.close()

        except Exception as e:
            lm.lnp(f"Failed to get XSI Users: {e}", level="error")

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

    def reject_call(self, user_id, call_id):
        """
        Reject the call for the given user_id and call_id
        Args:
            call_id (str): The unique ID of the call.
            :param call_id:
            :type call_id:
            :param user_id:
            :type user_id:
        """
        # Retrieve the XSI instance associated with the user ID from the xsi_user_map
        user_entry = self.xsi_user_map.get(user_id)
        if not user_entry:
            lm.logger.error(f"No XSI instance found for User ID: {user_id}")
            return

        xsi_instance = user_entry.get('xsi_instance')
        if xsi_instance:
            try:
                # Use the XSI instance to end the call
                active_calls = xsi_instance.calls
                for call in active_calls:
                    try:
                        call.hangup()
                        lm.lnp(f"Ended call with Call ID: {call.id}")
                    except Exception as e:
                        lm.lnp(f"Failed to end the call with Call ID: {call_id}. Error: {e}")
            except Exception as e:
                lm.lnp(f"Failed to end the call with Call ID: {call_id}. Error: {e}")
        else:
            lm.lnp(f"No active call found for Call ID: {call_id}.")

    def register_call(self, call_id, user_id):
        """
        Associate a given call_id with a user_id.
        Args:
            call_id (str): The unique ID of the call.
            user_id (str): The ID of the user.
        """
        lm.lnp(f"Associating Call ID {call_id} with User ID {user_id}")
        self.call_to_user_map[call_id] = user_id

    def handle_internal_call(self, xsi_user_id, xsi_target_id, call_id):
        """
        Handle a call where both parties are internal.
        """
        caller_entry = self.xsi_user_map.get(xsi_user_id) if xsi_user_id else None
        receiver_entry = self.xsi_user_map.get(xsi_target_id) if xsi_target_id else None
        if caller_entry and receiver_entry:
            lm.lnp(f"Both parties are internal, allowing call {call_id}")

    def handle_external_call(self, internal_xsi_user_id, call_id, event_type):
        """
        Handle a call where one party is external.
        """
        entry = self.xsi_user_map.get(internal_xsi_user_id)
        internal_webex_user_id = entry.get('webex_user_id') if entry else None

        if event_type == "xsi:CallReceivedEvent" and internal_webex_user_id:
            lm.lnp(f"External to internal call (inbound) and internal user {internal_webex_user_id} is in country, allowing call {call_id}")
        elif event_type == "xsi:CallOriginatedEvent" and internal_webex_user_id:
            lm.lnp(f"Internal to External call (outbound) and internal user {internal_webex_user_id} is in country; allowing call {call_id}")
        
    def handle_event(self, event):
        """
        Handle an event.
        """
        #lm.lnp(f"Event Received: \n: {event}")  # Print the event data
        event_details = self.extract_event_details(event)  # Extract the event details
        event_type = event_details.get('event_type')  # Fetch the event type

        if not event_details:  # Check if event_details is empty
            lm.lnp("Event details could not be extracted.")
            return  # Early return if event_details is empty
        try:
            if event_type in ["xsi:CallReceivedEvent", "xsi:CallOriginatedEvent"]:  # Check if the event type is a call event
                lm.lnp(f"Processing {event_type}. Details: {event_details}")
                call_id = event_details.get('call_id')  # Fetch the call ID
                xsi_user_id = event_details.get('user_id')  # Fetch the user ID
                xsi_target_id = event_details.get('target_id')  # Fetch the target ID

                lm.lnp(f"Handling call event. Type: {event_type}, Call ID: {call_id}, Caller: {xsi_user_id}, Call Receiver: {xsi_target_id}")
                internal_xsi_user_id = xsi_target_id if xsi_target_id else xsi_user_id  # Fetch the internal user ID

                if xsi_user_id and xsi_target_id:  # Both Internal check
                    # lm.lnp("Both calls internal... handling")
                    self.handle_internal_call(xsi_user_id, xsi_target_id, call_id)
                elif internal_xsi_user_id:  # Caller external check
                    self.handle_external_call(xsi_target_id, call_id, event_type)
                else:
                    lm.lnp(f"Unhandled event type {event_type}")
        except Exception as e:
            lm.lnp(f"Error handling call event {e}", style='error')
            traceback.print_exc()

    def monitor_calls(self, events_queue):
        """
        Monitor all calls for the Webex organization.
        Args:
            events_queue (queue.Queue): The queue storing the events.
        """
        lm.lnp('monitor_calls called')

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
        """Initialize XSI events and set up a thread to monitor calls continuously."""
        try:
            lm.lnp("Initializing CallMonitor with provided access token.")

            events = wxcadm.XSIEvents(self.webex.org)
            events_queue = queue.Queue()
            channel = events.open_channel(events_queue)
            subscription_response = channel.subscribe("Advanced Call")  # Subscribe to the Advanced Call event package

            if subscription_response:
                lm.lnp(f"Subscribed to 'Advanced Call' event package {subscription_response}", level="info")
            else:
                lm.lnp("Failed to subscribe to 'Advanced Call' event package.", level="error")
                return False

            lm.lnp("Starting thread to monitor calls...", style="info", level="info")
            monitor_thread = threading.Thread(target=self.monitor_calls, args=(events_queue,), daemon=True)
            monitor_thread.start()

            if monitor_thread.is_alive():
                lm.lnp("Event monitoring thread is running.", style="success", level="info")
                lm.lnp("\n")
                lm.p_panel(
                    "[bright_red]Call Monitoring has been started for the organization...[/bright_red]",
                    title="[white]Webex setup complete. Ready for calls.[/white]",
                    style="webex",
                    expand=False
                )
                return True
            else:
                lm.lnp("Event monitoring thread failed to start.", level="error")
                return False
        except Exception as e:
            lm.logger.exception("Failed to setup webex call monitoring: ", exc_info=e)
            return False

async def check_token(db):
    try:
        crud = CRUDOperations(db)
        admin_token_info = crud.read_admin_token()
        if admin_token_info and not is_token_expired(admin_token_info) and not is_refresh_token_expired(admin_token_info):
            admin_access_token = admin_token_info["access_token"]
            return True, admin_access_token  # Return both validation result and token
    except Exception as e:
        lm.logger.error(f"Error accessing admin token: {e}")
    return False, None  # Return False and None if token is invalid or an error occurred


async def start_call_monitoring():
    """
    Start the call monitoring process by initializing the CallMonitor class and setting up XSI events on server start if the admin token is valid in the database.
    """
    db = SessionLocal()
    try:
        token_valid, admin_access_token = await check_token(db)  # Check if the admin token is valid
        if not token_valid:
            lm.logger.error("Invalid or expired admin token.")
            return JSONResponse(content={"message": "Invalid or expired admin token"}, status_code=403)

        lm.logger.info("Admin token in DB is valid, starting call monitoring")
        call_monitor = CallMonitor(admin_access_token)
        call_monitor.setup_xsi_events()  # Setup monitoring of XSI events
        return JSONResponse(content={"message": "Call monitoring started successfully"}, status_code=200)
    except Exception as e:
        lm.logger.error(f"Failed to initiate call monitoring: {e}")
        return JSONResponse(status_code=500, content={"message": f"Failed to initiate call monitoring: {str(e)}"})
    finally:
        db.close()
