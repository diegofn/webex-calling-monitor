import typer
from app.env_manager.em import em
from app.config.settings import REQUIRED_SETTINGS, REQUIRED_ENV_VARS
from rich.console import Console

console = Console()  # Create a rich console
app = typer.Typer()  # Create a Typer app


def print_start():
    console.print(f"[blue]\nWelcome to the app setup for Webex Calling Monitor![/blue]")
    console.print(f"To start, env variables must be setup. You will be prompted to enter all necessary env variables. Reference the README for additional information.\n"
                  f"1. First, login (admin) to Webex for Developers portal here: https://developer.webex.com/docs/getting-started & copy/save the Personal "
                  f"Access token. This will be used to retrieve/save the Webex Admin User ID to .env for FastAPI route dependency (security).")
    console.print(f"2. Next, navigate to https://developer.webex.com/my-apps/new (admin) and select 'Create an Integration'\n"
                  f"3. Name the integration, select an icon, add App Hub Description, "
                  f"add Redirect URI(s): 'PUBLIC_URL/admin/callback' & 'PUBLIC_URL/user/callback', "
                  f"select scopes: spark:all, spark-admin:xsi,spark:xsi, spark-admin:locations_read, spark-admin:people_read, spark-admin:licenses_read"
                  f"4. Create Integration'")
    console.print(f"5. Copy/save the Client ID & Client Secret!\n")
    console.print(f"Starting the setup process...", style="bold bright_green")


@app.command()
def main_callback():
    """
    This callback is run before any command.
    """
    print_start()


@app.command()
def run():
    """
        Run the setup process for the app.
    """
    em.create_and_load_env_if_missing()  # Create and load the .env file in app/config/.env if missing
    em.ensure_vars_set(REQUIRED_ENV_VARS)
    print("\n")
    em.ensure_settings_set(REQUIRED_SETTINGS)
    # lm.print_config_table(config_instance=c)


if __name__ == "__main__":
    app()
