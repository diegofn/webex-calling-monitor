# Cisco Webex Calling Monitor

Python middleware for Webex Calling XSI interface to monitor the telephony events in Webex Calling

## Features

- Monitoring and managing call events in real-time using Webex XSI events
- OAuth for secure authentication and user identification
- Secure session management and token refresh for continuous application use
- Database operations using SQLAlchemy for data storage and retrieval
- PostgreSQL database for storing user data, session tokens, calls an agent information information

## User cases

### Block call by geo location.

First version for daemon that register the XSI Interface for the organization and check the Geolocation based on a webpage.

## Installation/Configuration in VPS

1. Clone this repository with `git clone https://github.com/diegofn/webex-calling.monitor`
2. Install the dependencies

```Shell
   sudo apt update
   sudo apt upgrade
   sudo apt install python3-pip
   sudo apt install libpq-dev
   sudo apt install python-is-python3
   sudo apt install postgresql postgresql-contrib
   sudo systemctl start postgresql.service
```

1. Create postgres user

```Shell
   sudo -i -u postgres
   createuser --interactive
   createdb wxc-monitor
   psql
   alter user webex with encrypted password 'webex';
   grant all privileges on database webex to webex;
   exit
   sudo adduser webex
```

1. Install python requirements

```Shell
   python -m venv .
   source bin/activate
   pip install -r requirements.txt
```

1. Install uvicorn process

```Shell
   python setup.py run
```

## Manually create and update the `.env` and update settings.py file:

To configure the application, you need to update the `.env` on the `app/config` folder with the appropriate values. 
This file contains key settings that the application uses to interact with the Webex APIs and to set up its environment.

1. **Webex Admin User ID**:
   - `WEBEX_ADMIN_UID`: The Webex admin user ID. This is used to fetch the Webex organization's details and used to verify the user's role in the organization after authentication.

2. **Client ID and Secret**:
   - `CLIENT_ID`: Your Webex Integration Client ID.
   - `CLIENT_SECRET`: Your Webex Integration Client Secret.

3. **Database Configuration**:
   - `SQLALCHEMY_DATABASE_URL`: The database URL for the application. The default is a PostgreSQL database, but you can replace it with a different database URL if needed.

4. **PUBLIC_URL**: 
   - `PUBLIC_URL`: The URL for the application for private or public environment, we suggest to have it on HTTPS


### `.env` example

   ```script
   WEBEX_ADMIN_UID=YOUR_WEBEX_ADMIN_UID
   CLIENT_ID=YOUR_WEBEX_INTEGRATION_CLIENT_ID
   CLIENT_SECRET=YOUR_WEBEX_INTEGRATION_CLIENT_SECRET
   SQLALCHEMY_DATABASE_URL="postgresql://YOUR_USN:YOUR_PASSWORD@localhost/YOUR_DB_NAME"
   PUBLIC_URL=https://subdomain.ngrok-free.app
   ```

## Usage

### Start the Application

To initiate the App, start the FastAPI application:

```Shell
   uvicorn main:app
   uvicorn main:app --log-level warning
```

## Screenshots/GIFs

### Environment Setup:

![/images/setup.gif](/images/setup.gif)

### Database Setup:

![/images/database_setup.gif](/images/database_setup.gif)

### WxC monitoring setup 

![/images/app_setup.gif](/images/app_setup.gif)

### Starting Call Monitoring:
![/images/call_monitor.gif](/images/call_monitor.gif)

## Webex Calling XSI Documentation

<https://developer.cisco.com/docs/webex-calling/developer-docs/>

## Based on: gve_devnet_webex_xsi_call_block 

<https://github.com/gve-sw/gve_devnet_webex_xsi_call_block>

- Mark Orszycki
- Gerardo Chaves
