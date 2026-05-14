import json
from typing import Optional
from fastapi import Request, APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from requests_oauthlib import OAuth2Session
from sqlalchemy.exc import SQLAlchemyError

from app.call_monitor import CallMonitor
from app.config.config import c
from app.database.crud import CRUDOperations
from app.database.db import SessionLocal
from sqlalchemy.orm import Session

from app.funcs import (
    is_token_expired,
    is_refresh_token_expired,
    generate_session_token,
)
from app.logger.logrr import lm
from app.schemas import TimeLocationData
from app.webex_api import MyWebex

# Importing constants/load config settings
CLIENT_ID = c.CLIENT_ID
CLIENT_SECRET = c.CLIENT_SECRET
SCOPE = c.SCOPE
PUBLIC_URL = c.PUBLIC_URL
AUTHORIZATION_BASE_URL = c.AUTHORIZATION_BASE_URL
TOKEN_URL = c.TOKEN_URL
USER_REDIRECT_URI = c.USER_REDIRECT_URI
ADMIN_REDIRECT_URI = c.ADMIN_REDIRECT_URI
WEBEX_ADMIN_UID = c.WEBEX_ADMIN_UID

webex_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# Dependency Injections
async def dependency_db():
    """ Using FastAPIs dependency injection system to close the database session after the request is complete. """
    db = SessionLocal()     # Create a new database session
    try:
        yield db    # Yield the database session to the route function
    finally:
        db.close()  # Close the database session after the request is complete


@webex_router.get("/user/login")
async def start_user_oauth():
    """
        Initiates the OAuth flow for user authentication with Webex.
    """
    try:
        lm.lnp_wbx_oauth("1. Initiating OAuth flow for user authentication with Webex.")    # Log the start of the OAuth flow
        auth_client = OAuth2Session(CLIENT_ID, scope=SCOPE, redirect_uri=USER_REDIRECT_URI)  # Create an OAuth2Session instance for the user
        authorization_url, state = auth_client.authorization_url(AUTHORIZATION_BASE_URL)  # Generate the authorization URL
        response = RedirectResponse(url=authorization_url)  # Redirect to the authorization URL
        response.set_cookie(key="oauth_state", value=state)  # Set the state as a cookie in the response
        lm.lnp_wbx_oauth("2. OAuth flow started. Redirecting to Webex authorization URL.")      # Log the redirection
        return response
    except Exception as e:
        lm.lnp(f'Error during OAuth start: {e}', style='error', level='error')
        return RedirectResponse(url="/error")  # Redirect to an error page or handle error differently


@webex_router.get("/user/callback")
async def user_oauth_callback(request: Request, db: Session = Depends(dependency_db)):
    """
        Handles the OAuth callback for the user. Fetches the access token and stores it in the database.
    """
    try:
        lm.lnp_wbx_oauth('3. Received OAuth callback. Attempting to fetch access token...')     # Log the start of the Webex OAuth callback
        state = request.cookies.get("oauth_state")  # Retrieve the OAuth state from the cookie
        auth_client = OAuth2Session(CLIENT_ID, state=state, redirect_uri=USER_REDIRECT_URI)     # Create an OAuth2Session instance for the user
        token = auth_client.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=str(request.url))    # Fetch the Webex access token
        if token:
            lm.lnp_wbx_oauth('Access token successfully obtained')
            session_token = generate_session_token()  # Generate a unique session token for the user
            my_webex = MyWebex(access_token=token['access_token'])  # Create an instance of MyWebex with user's access token

            user_info = my_webex.get_user_info()    # Retrieve user information using MyWebex instance
            user_id = user_info.get('id')   # Get the Webex user ID from the user information

            # Save the user_id and session_token to the UserList table
            try:
                crud = CRUDOperations(db)
                user_list_entry = crud.read_user_list(user_id=user_id)
                if user_list_entry is None:
                    crud.create_user_list_entry(user_id=user_id, session_token=session_token)
                else:
                    crud.update_user_list_entry(user_id=user_id, session_token=session_token)
            except Exception as e:
                db.rollback()  # Rollback the changes in case of an error
                lm.lnp(f"Error occurred while saving user to the database: {e}", style='error', level='error')

            # Create a response and set a cookie with the session token
            response = RedirectResponse(url="/user_oauth_success")
            response.set_cookie(key="session_token", value=session_token, httponly=True)  # Use httponly for security
            return response
        else:
            lm.p_panel('[bright_white]Failed to obtain access token in OAuth callback.', style='error', expand=False)
            return RedirectResponse(url="/error")
    except Exception as e:
        lm.lnp(f'Error in user OAuth callback: {e}', style='error', level='error')
        return RedirectResponse(url="/error")


@webex_router.get("/user_oauth_success", response_class=HTMLResponse)
async def user_oauth_success(request: Request):
    """
        Handles the successful OAuth authentication for the user.
        Checks for the session token in the cookies.
        If the token is found, the user is authenticated.
    """
    session_token = request.cookies.get("session_token")    # Retrieve the session token from the cookies
    if session_token is None:   # If the session token is not found, return an error
        raise HTTPException(status_code=400, detail="User unauthorized, session token not found in cookies")
    lm.lnp(f"User successfully authenticated. Session token: {session_token}. Client: {request.client.host}")   # Else, log the successful authentication
    return templates.TemplateResponse(name='user_oauth_success.html', context={'request': request, 'session_token': session_token})     # Return the success page


@webex_router.get("/admin/home")
async def admin_home(request: Request):
    """
        Displays the home page for the admin.
    """
    return templates.TemplateResponse("admin_home.html", {"request": request})


@webex_router.get("/admin/login")
async def admin_oauth_login():
    """
        Initiates the OAuth flow for admin authentication with Webex.
    """
    try:
        lm.lnp_wbx_oauth("1. Initiating OAuth flow for admin authentication with Webex.")
        # Start the OAuth flow if no valid token is found or if there was an error reading the token from db
        auth_client = OAuth2Session(c.CLIENT_ID, scope=SCOPE, redirect_uri=ADMIN_REDIRECT_URI)
        authorization_url, state = auth_client.authorization_url(c.AUTHORIZATION_BASE_URL)
        response = RedirectResponse(url=authorization_url)
        response.set_cookie(key="oauth_state", value=state, httponly=True, samesite='lax')
        return response
    except Exception as e:
        lm.lnp(f'Error during OAuth start: {e}', style='error', level='error')
        return RedirectResponse(url="/error")  # Redirect to an error page or handle error differently


@webex_router.get("/admin/callback")
async def admin_callback(request: Request, db: Session = Depends(dependency_db)):
    """
        Handles the OAuth callback for the admin. Fetches the access token and stores it in the database.
    """

    try:
        state = request.cookies.get("oauth_state")  # Retrieve the state from the cookie
        auth_client = OAuth2Session(CLIENT_ID, state=state, redirect_uri=ADMIN_REDIRECT_URI)  # Create an OAuth2Session instance for the admin
        token = auth_client.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=str(request.url))  # Fetch the access token
        admin_session_token = generate_session_token(token_len=32)  # Generate a unique session token for the admin
        lm.lnp(f"Generated 'admin' session token: {admin_session_token} for client: {request.client.host}")
        access_token = token.get("access_token")
        if access_token:
            my_webex = MyWebex(access_token=access_token)  # Create an instance of MyWebex with admin's access token
            # Retrieve user information using MyWebex instance
            user_info = my_webex.get_user_info()
            user_id = user_info.get('id')
            user_name = user_info.get("displayName")
            # lm.lnp(f"admin/login attempt by user_id: {user_id}, user_name: {user_name}", style='webex', level='info')

            if user_id != c.WEBEX_ADMIN_UID:
                raise HTTPException(status_code=403, detail="Unauthorized: Admin ID does not match.")
            elif user_id == c.WEBEX_ADMIN_UID:
                lm.lnp(f"Admin successfully authenticated.")
                # lm.lnp(f"Admin {user_id}, user_name: {user_name} successfully authenticated.", style="success", level='info')
                crud = CRUDOperations(db)
                crud.update_admin_token(**token, session_token=admin_session_token)  # Process and store the admin token securely
                response = RedirectResponse(url="/admin_success")  # Redirect to the login page
                response.set_cookie(key="session_token", value=admin_session_token, httponly=True)  # Set the session token as a cookie in the response
                response.set_cookie(key="is_admin_authenticated", value="true", httponly=True)  # Set a flag in the cookie
                return response
    except HTTPException as e:
        return JSONResponse(content={"message": f"Error during admin OAuth callback {e}"}, status_code=e.status_code)
    except Exception as e:
        lm.lnp(f"Error during admin callback: {e}", level='error', style='error')
        return JSONResponse(content={"message": f"Error during admin OAuth callback {e}"}, status_code=500)


@webex_router.get("/admin_success", response_class=HTMLResponse)
async def admin_success(request: Request):
    """
        Handles the successful OAuth authentication for the admin.
    """
    # Check if the admin has been authenticated through the callback
    is_admin_authenticated = request.cookies.get("is_admin_authenticated") == "true"
    if not is_admin_authenticated:
        return JSONResponse(content={"message": "Unauthorized access. Admin login required."}, status_code=403)
    session_token = request.cookies.get("session_token")
    lm.lnp(f"Admin successfully authenticated. Session token: {session_token}. Client: {request.client.host}")
    return templates.TemplateResponse(name='admin_success.html', context={'request': request, 'session_token': session_token})


@webex_router.get("/admin/refresh_token")
async def refresh_token(db: Session = Depends(dependency_db)):
    """
        Refreshes the admin's access token.
    """
    token = CRUDOperations(db).read_admin_token()

    lm.lnp('Starting token refresh process...', style='webex')
    if token and 'refresh_token' in token:
        try:
            lm.lnp('Refreshing access token...', style='webex')
            auth_client = OAuth2Session(CLIENT_ID, token=token)
            new_token = auth_client.refresh_token(TOKEN_URL, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
            CRUDOperations(db).update_admin_token(**new_token)
            return RedirectResponse(url="/admin_success")
        except Exception as e:
            lm.lnp(f'Error refreshing token: {e}', style='error', level='error')
            return RedirectResponse(url="/admin/login")
    else:
        lm.lnp('No refresh token found.', style='error', level='error')
        return RedirectResponse(url="/admin/login")


@webex_router.post("/start-call-monitoring")
async def start_call_monitoring(request: Request, db: Session = Depends(dependency_db)):
    """
        Start the call monitoring process for Webex Organization.
    """
    lm.lnp_wbx_oauth("Attempting to start call monitoring process for Webex Organization...")
    is_admin_authenticated = request.cookies.get("is_admin_authenticated") == "true"    # Check if the admin has been authenticated through the callback
    if not is_admin_authenticated:  # If the admin is not authenticated, return an error
        lm.lnp("Unauthorized access. Admin login required.", level="error")
        return JSONResponse(content={"message": "Unauthorized access. Admin login required."}, status_code=403)

    crud = CRUDOperations(db)   # Create an instance of CRUDOperations
    admin_access_token = crud.get_admin_access_token()  # Retrieve the admin access token from the database
    if not admin_access_token:  # If the admin access token is not found, return an error
        lm.lnp("Admin token retrieval failed", level="error")
        return JSONResponse(status_code=500, content={"message": "Admin token retrieval failed"})

    try:
        call_monitor = CallMonitor(admin_access_token)
        setup_result = call_monitor.setup_xsi_events()  # Setup monitoring of XSI events
        if setup_result:
            lm.lnp("Call monitoring process started successfully.", level="success")
            return JSONResponse(content={"redirect": "/admin_success"}, status_code=200)
        else:
            lm.lnp("Failed to start call monitoring process.", level="error")
            return JSONResponse(content={"message": "Failed to initiate call monitoring"}, status_code=500)
    except Exception as e:
        lm.lnp(f"Failed to initiate call monitoring: {e}", level="error")
        return JSONResponse(status_code=500, content={"message": f"Failed to initiate call monitoring: {str(e)}"})

@webex_router.get("/admin/agent_monitor", response_class=HTMLResponse)
async def admin_agent_monitor(request: Request):
    return templates.TemplateResponse("admin_agent_monitor.html", {"request": request})


@webex_router.get("/api/agent-events")
async def api_agent_events(
    request: Request,
    db: Session = Depends(dependency_db),
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    user_id: Optional[str] = None,
):
    is_admin_authenticated = request.cookies.get("is_admin_authenticated") == "true"
    if not is_admin_authenticated:
        return JSONResponse(content={"message": "Unauthorized"}, status_code=403)
    try:
        crud = CRUDOperations(db)
        events = crud.get_agent_events(date_from=date_from, date_to=date_to, user_id=user_id)
        result = [
            {
                "id": ev.id,
                "event_id": ev.event_id,
                "sequence_number": ev.sequence_number,
                "user_id": ev.user_id,
                "target_id": ev.target_id,
                "event_type": ev.event_type,
                "state": ev.state,
                "state_timestamp": ev.state_timestamp,
                "sign_in_timestamp": ev.sign_in_timestamp,
                "total_available_time": ev.total_available_time,
                "average_wrap_up_time": ev.average_wrap_up_time,
                "name": wu.name if wu else None,
                "extension": wu.extension if wu else None,
            }
            for ev, wu in events
        ]
        return JSONResponse(content=result)
    except Exception as e:
        lm.lnp(f"Error fetching agent events: {e}", level="error")
        return JSONResponse(status_code=500, content={"message": str(e)})


@webex_router.get("/error")
async def get_error(request: Request):
    return templates.TemplateResponse("error.html", {"request": request})


@webex_router.get("/api/xsi-users", response_class=HTMLResponse)
async def show_xsi_users(request: Request, db: Session = Depends(dependency_db)):
    """
        Displays the XSI users page.
    """
    lm.lnp_wbx_oauth("Attempting to get all XSI Users")
    is_admin_authenticated = request.cookies.get("is_admin_authenticated") == "true"
    if not is_admin_authenticated:
        lm.lnp("Unauthorized access. Admin login required.", level="error")
        return JSONResponse(content={"message": "Unauthorized access. Admin login required."}, status_code=403)

    # Get admin access token from DB
    crud = CRUDOperations(db)   
    admin_access_token = crud.get_admin_access_token()

    if not admin_access_token:
        lm.lnp("Admin token retrieval failed", level="error")
        return JSONResponse(status_code=500, content={"message": "Admin token retrieval failed"})
    
    # Return users as JSON
    try:
        call_monitor = CallMonitor(admin_access_token)
                
        # Build a JSON-serializable copy of the xsi_user_map without the 'xsi_instance' column
        raw_map = call_monitor.xsi_user_map or {}
        sanitized_map = {}
        for xsi_id, info in raw_map.items():
            if not isinstance(info, dict):
                # keep as-is (or coerce to string) if unexpected type
                sanitized_map[xsi_id] = info
                continue

            # copy all keys except 'xsi_instance'
            entry = {k: v for k, v in info.items() if k != "xsi_instance"}

            # ensure values are JSON-serializable; fallback to str() when necessary
            for k, v in list(entry.items()):
                try:
                    json.dumps(v)
                except (TypeError, ValueError):
                    entry[k] = str(v)

                sanitized_map[xsi_id] = entry

        lm.lnp("XSI Users returned", level="success")
        return JSONResponse(content=sanitized_map, status_code=200)
        
    except Exception as e:
        lm.lnp(f"Failed to get XSI Users: {e}", level="error")
        return JSONResponse(status_code=500, content={"message": f"Failed to get XSI Users: {str(e)}"})
