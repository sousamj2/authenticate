from flask import (
    Blueprint,
    request,
    session,
    redirect,
    url_for,
    current_app,
    render_template,
    flash,
)
import bleach
import subprocess
from simplewebapp.Funhelpers import mask_email
from mysql.DBhelpers import *
from mysql.DBhelpers import getUserIdFromEmail
from werkzeug.security import generate_password_hash
import re
from markupsafe import Markup

bp_updateDB = Blueprint("updateDB", __name__)


def check_player_exists(ign):
    """
    SSH into the GCP MC server and check if a player with this IGN has stats.
    Returns True if the player exists, False otherwise (including if server is offline).
    """
    mc_user = current_app.config.get("MC_SERVER_USER", "goals_locust8006_eagereverest_co")
    mc_host = current_app.config.get("MC_SERVER_HOST", "2600:1900:4010:58a::")
    script_path = "/home/sargedas/mcserver/ingame_scripts/travel_time_report.py"
    stats_dir = "/home/minecraft/world/players/stats"
    
    cmd = [
        "ssh", "-6", "-o", "StrictHostKeyChecking=no", f"{mc_user}@{mc_host}",
        f"python3 {script_path} {stats_dir} --server-root /home/minecraft --user {ign}"
    ]
    try:
        print(f"DEBUG: Checking if player exists: {' '.join(cmd)}", flush=True)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        print(f"DEBUG: Exit code = {res.returncode}", flush=True)
        return res.returncode == 0
    except Exception as e:
        print(f"DEBUG: Error checking player existence: {e}", flush=True)
        return False


def cleanup_stale_accounts():
    """
    Delete accounts where account_validated is FALSE and created_at is older than 20 minutes.
    """
    try:
        result = submit_query(
            "DELETE FROM users WHERE account_validated = FALSE AND created_at < NOW() - INTERVAL 20 MINUTE;"
        )
        if isinstance(result, dict) and result.get("rowcount", 0) > 0:
            print(f"DEBUG: Cleaned up {result['rowcount']} stale unvalidated account(s)", flush=True)
    except Exception as e:
        print(f"DEBUG: Error cleaning up stale accounts: {e}", flush=True)


@bp_updateDB.route("/updateDB", methods=["GET", "POST"])
def updateDB():
    """
    Handles the final step of Tier 1 user registration, creating the user in the database.
    
    The IGN is checked against the GCP server:
    - If found: account_validated=TRUE, rank_validated=TRUE → direct to profile with rank update message
    - If not found (server offline etc.): account_validated=FALSE, rank_validated=TRUE → popup to join within 20 mins
    """

    # Cleanup stale unvalidated accounts on each registration attempt
    cleanup_stale_accounts()

    userinfo = session.get("userinfo", {})

    def get_clean(field: str, default: str = "") -> str:
        return bleach.clean(request.form.get(field) or default)

    first_name = userinfo.get("given_name") or get_clean("given_name")
    last_name = userinfo.get("family_name") or get_clean("family_name")
    email = (userinfo.get("email") or get_clean("email")).lower()
    errorMessage = ""

    username = None
    if userinfo.get("email"):
        username = email
    else:
        username = get_clean("username").lower()
        if username != email and not re.match(r"^[A-Za-z0-9._-]+$", username):
            errorMessage += "The username can contain letters, numbers or the symbols '.' , '-' or '_'\n"
            errorMessage += "Alternatively you can use your email as username."

    h_password = None
    password = get_clean("password") or None
    if password:
        h_password = generate_password_hash(password)

    register_ip = request.headers.get("X-Real-IP")
    if not register_ip:
        register_ip = request.remote_addr

    # Validation: check if email already has an account
    if getUserIdFromEmail(email):
        errorMessage += f"This email ({email}) already has an account.\n"

    # Reset token if trying to register admin email
    admin_email = current_app.config.get("ADMIN_EMAIL", "mj.sargedas@gmail.com").lower()
    is_google = bool(userinfo.get("email"))
    if email == admin_email:
        if not is_google:
            submit_query("DELETE FROM registration_tokens WHERE email = %s;", (email,))
            print(f"DEBUG: Reset registration token for admin email: {email}", flush=True)
        errorMessage += "Registration not allowed for this email.\n"

    # Validation: check if IGN is already taken by a validated account (ignoring placeholders)
    ign = get_clean("ign")
    if ign:
        existing = submit_query(
            "SELECT email FROM users WHERE ign = %s AND account_validated = TRUE AND g_token != -1 LIMIT 1;",
            (ign,)
        )
        if existing and not isinstance(existing, str):
            errorMessage += (
                "This in-game name is already registered. "
                "If you think this is a mistake, use the command "
                "'/msg mjcrafts [MESSAGE]' if admin is online or "
                "'/mail send mjcrafts [MESSAGE]' otherwise "
                "and the ADMIN will correct the problem.\n"
            )

    if len(errorMessage) > 0:
        if not session.get("metadata"):
            session["metadata"] = {}
        session["metadata"]["error_message"] = errorMessage
        print(errorMessage)
        return redirect(url_for("signup.signup", email=email))

    # Check if the IGN exists — first in local DB (fast), then via GCP SSH (slow)
    account_validated = False
    if ign:
        # Step 1: Check local database (data synced from GCP by suspend_if_empty)
        db_email = getEmailFromIgn(ign)
        if db_email:
            account_validated = True
            print(f"DEBUG: IGN '{ign}' found in local DB (email={db_email})", flush=True)
        else:
            # Step 2: Fall back to SSH check on GCP server
            account_validated = check_player_exists(ign)
            print(f"DEBUG: IGN '{ign}' GCP SSH check result: {account_validated}", flush=True)

    # TIER 1: Insert user with rank_validated=True (registered via webapp)
    # Check if a placeholder account exists for this IGN
    placeholder = None
    if ign:
        placeholder = submit_query("SELECT email FROM users WHERE ign = %s AND g_token = -1 LIMIT 1;", (ign,))
        
    if placeholder and not isinstance(placeholder, str):
        # Convert placeholder to real user
        g_token_val = 1 if username is None else 0
        username_val = username if username is not None else email
        
        submit_query(
            "UPDATE users SET first_name=%s, last_name=%s, email=%s, h_password=%s, username=%s, g_token=%s, rank_validated=TRUE, account_validated=TRUE WHERE ign=%s AND g_token=-1;",
            (first_name, last_name, email, h_password, username_val, g_token_val, ign)
        )
        successUser = "Success"
        account_validated = True
        print(f"DEBUG: Converted placeholder to real account for IGN {ign}")
    else:
        successUser = insertNewUser(
            first_name, last_name, email, h_password, username, ign,
            rank_validated=True, account_validated=account_validated
        )

    successIP = insertNewIP(email, register_ip)
    successConn = insertNewConnectionData(email, register_ip)

    is_error = any("Error" in str(s) for s in [successUser, successIP, successConn])

    if not is_error:
        # Store in session and redirect to profile
        session["metadata"] = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "ign": ign,
            "tier": 1,
            "account_validated": account_validated,
            "show_validation_popup": not account_validated,  # Show popup if not validated yet
        }
        session.modified = True
        return redirect(url_for("profile.profile"))
    else:
        print(f"Registration failed: User={successUser}, IP={successIP}, Conn={successConn}")
        return f"Error registering user: {successUser} / {successIP} / {successConn}", 500
