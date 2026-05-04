from flask import (
    Blueprint,
    render_template,
    session,
    current_app,
    request,
    redirect,
    url_for,
)
from markupsafe import Markup
from pprint import pprint
from simplewebapp.Funhelpers import get_lisbon_greeting


# bp_signup314 = Blueprint("signup314", __name__)
bp_signup = Blueprint("signup", __name__)


@bp_signup.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Manages the user signup form, pre-filling data from different sources.

    This function handles both GET and POST requests to display the final signup form.
    - On a GET request, it's typically used for users who have authenticated via an
      external provider (like Google). It retrieves their details (email, name) from
      the session and uses them to pre-fill the form.
    - On a POST request, it's used for users who have completed an email confirmation
      step. It retrieves the email from the submitted form data.

    If no email is found in either case, the user is redirected back to the sign-in page.

    The function renders the 'content/signup.html' template with the pre-filled data,
    which is then embedded into the main 'index.html' layout for the user to complete
    their registration.
    """
    # pprint('Rendering signup page...')
    if not session.get("metadata"):
        session["metadata"] = {}
    session["metadata"]["greeting"] = get_lisbon_greeting()

    email = ""
    given_name = ""
    family_name = ""
    is_google = False

    if request.method == "POST":
        email = request.form.get("email", "")
    elif request.method == "GET":
        # print("session", session)
        user = session.get("user") or session.get("userinfo")
        email = user["email"]
        given_name = user["given_name"]
        family_name = user["family_name"]
        is_google = True

    if len(email) == 0:
        return redirect(url_for("signin.signin"))

    # print(email)
    # error_message = session.get("metadata").get("error_message",'')
    # print(session.get("metadata"))

    # First render the content template with profile variables
    main_content_html = render_template(
        "content/signup.html",
        email_input=email,
        # error_message=error_message,
        is_google=is_google,
        given_name=given_name,
        family_name=family_name,
        **session.get("metadata", {})
    )

    # Then render the main template with the rendered content
    return render_template(
        "index.html",
        user=None,
        # metadata=session.get("metadata"),
        admin_email=current_app.config["ADMIN_EMAIL"],
        content_template='content/signup.html',
        email_input=email,
        is_google=is_google,
        given_name=given_name,
        family_name=family_name,
        **session.get("metadata", {}),
        page_title="Mostly Jovial Crafters",
        title="Mostly Jovial Crafters",
    )


# @bp_signup.route("/")
# def signup():
#     """
#     Renders a work-in-progress page.

#     This function is a placeholder and is not yet fully implemented.
#     It is intended to be used for future development of an alternative
#     signup process.
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
