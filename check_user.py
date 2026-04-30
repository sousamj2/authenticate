from flask import (
    Blueprint,
    request,
    session,
    redirect,
    url_for,
    flash,
    current_app,
    render_template,
)
from werkzeug.security import (
    check_password_hash,
)  # pip install werkzeug for password hash comparison

from pprint import pprint
from mysql.DBhelpers import (
    get_user_profile_tier1,
    refresh_last_login_and_ip,
    getHashFromEmail,
    getEmailFromUsername,
)

from markupsafe import Markup

bp_check_user = Blueprint("check_user", __name__, url_prefix="/check_user")
# bp_check_user314 = Blueprint("check_user314", __name__, url_prefix="/check_user314")


@bp_check_user.route("/", methods=["GET", "POST"])
def check_user():
#     """
#     Renders a work-in-progress page.

#     This function is a placeholder and is not yet fully implemented.
#     It is intended to be used for future development.
#     """
#     user = session.get("user") or session.get("userinfo")
#     # Render the content template first
#     main_content_html = render_template(
#         "content/wip.html",
#     )
#     user = None

#     # Then render the main template with the content
#     return render_template(
#         "index.html",
#         admin_email=current_app.config["ADMIN_EMAIL"],
#         user=user,
#         page_title="Explicações em Lisboa",
#         title="Explicações em Lisboa",
#         main_content=Markup(main_content_html),
#     )


# @bp_check_user314.route("/", methods=["GET", "POST"])
# def check_user314():
    """
    Handles user authentication.

    For POST requests, it authenticates using email and password.
    If the user provides a username instead of an email, it retrieves the email from the database.
    It then verifies the password against the stored hash.
    If authentication is successful, it updates the last login time and IP address, stores user metadata in the session, and redirects to the user's profile.

    For GET requests, it handles users authenticated via an external provider (e.g., Google).
    It checks if the user's email exists in the database.
    If the user exists, it updates their last login time and IP, stores their metadata in the session, and redirects to their profile.
    If the user does not exist, it redirects to the signup page.
    """
    # pprint('Checking user in the database...')

    if request.method == "POST":
        email = request.form.get(
            "username", ""
        ).lower()  # use 'username' if that's your form field name
        password = request.form.get("password", "")

        if not email or not password:
            flash("Falta o username/email ou a palavra-passe.")
            return redirect(url_for("signin.signin"))

        if "@" not in email:  # case for user name
            email = getEmailFromUsername(email)

        # Fetch the stored hash for this email
        hashval = getHashFromEmail(email)
        if hashval is None:
            flash("O username/email não existe ou a palavra-passe está incorreta.")
            return redirect(url_for("signin.signin"))

        # Verify password against hash
        if check_password_hash(hashval, password):
            user = get_user_profile_tier1(email)
            if user:
                refresh_last_login_and_ip(email, request.headers.get("X-Real-IP"))
                session["metadata"] = user
                # return redirect(url_for('profile.profile', source_method ='POST'))
                return redirect(url_for('profile.profile'))
            else:
                flash("O username/email não existe ou a palavra-passe está incorreta.")
                return redirect(url_for("signup.signup"))
        else:
            flash("O username/email não existe ou a palavra-passe está incorreta.")
            return redirect(url_for("signin.signin"))

    else:
        userinfo = session.get("userinfo")
        # pprint(userinfo)
        # pprint(session)["metadata"])
        if not userinfo or "email" not in userinfo:
            return redirect(url_for("signup.signup"))

        email = userinfo["email"]

        user = get_user_profile_tier1(email)

        if user:
            # pprint('User found in the database.')
            refresh_last_login_and_ip(email, request.headers.get("X-Real-IP"))
            session["metadata"] = get_user_profile_tier1(email)
            # pprint(session['metadata'])
            # return redirect(url_for('profile.profile', source_method ='GET'))
            return redirect(url_for("profile.profile"))
        else:
            flash("O username/email não existe ou a palavra-passe está incorreta.")
            # pprint('User not found, redirecting to signup.')
            return redirect(url_for("signup.signup"))
