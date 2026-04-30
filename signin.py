from flask import Blueprint, render_template, session, url_for, current_app, request
from markupsafe import Markup

bp_signin = Blueprint("signin", __name__, url_prefix="/signin")
# bp_signin314 = Blueprint("signin314", __name__, url_prefix="/signin314")


@bp_signin.route("/")
def signin():
    """
    Renders the main sign-in page for the application.

    This function displays the sign-in page by rendering the 'content/signin.html'
    template. This template contains the user interface for authentication, including
    the sign-in form and a "Sign in with Google" button. The resulting HTML is then
    embedded into the main 'index.html' site layout.
    """
    # If a quiz UUID is passed, store it in the session to be claimed after login
    pending_quiz_uuid = request.args.get('next_uuid')
    if pending_quiz_uuid:
        session['pending_quiz_uuid'] = pending_quiz_uuid

    user = session.get('user') or session.get('userinfo')
    # Render the content template first
    main_content_html = render_template(
        'content/signin.html',
        logo_url=url_for('static', filename='images/google_logo.svg')
    )
    user = None

    # Then render the main template with the content
    return render_template(
        "index.html",
        admin_email=current_app.config["ADMIN_EMAIL"],
        user=user,
        page_title="Explicações em Lisboa",
        title="Explicações em Lisboa",
        main_content=Markup(main_content_html),
    )


# @bp_signin.route("/")
# def signin():
#     """
#     Renders a work-in-progress page.

#     This function is a placeholder and is not yet fully implemented.
#     It is intended to be used for future development of an alternative
#     sign-in process.
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
