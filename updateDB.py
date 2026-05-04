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
from pprint import pprint
import bleach
from simplewebapp.Funhelpers import mask_email
from mysql.DBhelpers import *
from mysql.DBhelpers import getUserIdFromEmail
from werkzeug.security import generate_password_hash
import re
from markupsafe import Markup

bp_updateDB = Blueprint("updateDB", __name__)


@bp_updateDB.route("/updateDB", methods=["GET", "POST"])
def updateDB():
    """
    Handles the final step of Tier 1 user registration, creating the user in the database.
    """

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

    if len(errorMessage) > 0:
        if not session.get("metadata"):
            session["metadata"] = {}
        session["metadata"]["error_message"] = errorMessage
        print(errorMessage)
        return redirect(url_for("signup.signup", email=email))

    # TIER 1: Only these three functions
    ign = get_clean("ign")
    successUser = insertNewUser(first_name, last_name, email, h_password, username, ign)
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
            "tier": 1,  # New user starts at tier 1
        }
        session.modified = True
        return redirect(url_for("profile.profile"))
    else:
        print(f"Registration failed: User={successUser}, IP={successIP}, Conn={successConn}")
        return f"Error registering user: {successUser} / {successIP} / {successConn}", 500
