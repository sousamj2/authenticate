from flask import Blueprint, redirect,current_app

bp_signin_redirect = Blueprint('signin_redirect', __name__, url_prefix='/signin_redirect')
# bp_signin_redirect314 = Blueprint('signin_redirect314', __name__, url_prefix='/signin_redirect314')

@bp_signin_redirect.route('/')
def signin_redirect():
    """
    Constructs and redirects to the Google OAuth 2.0 authorization URL.

    This function initiates the Google authentication process by building the
    authorization URL with parameters defined in the application's configuration.
    Key parameters include the client ID, redirect URI, and scope.

    It specifically requests 'offline' access, which prompts the user for consent
    to allow the application to receive a refresh token. The user is then immediately
    redirected to this URL to begin authentication with Google.
    """
    # Create the Google OAuth authorization URL
    auth_url = (
        f'{current_app.config["AUTHORIZATION_URL"]}?response_type=code'
        f'&client_id={current_app.config["CLIENT_ID"]}'
        f'&redirect_uri={current_app.config["REDIRECT_URI"]}'
        f'&scope={current_app.config["SCOPE"]}'
        f'&access_type=offline'
        f'&prompt=consent'
        f'&state=secure_random_state'
    )
    # print(auth_url)
    return redirect(auth_url)


# @bp_signin_redirect.route("/")
# def signin_redirect():
#     """
#     Constructs and redirects to a Google OAuth 2.0 authorization URL with a 'bogus' access type.

#     Similar to `signin_redirect314`, this function initiates the Google authentication
#     process by building and redirecting to the authorization URL.

#     However, this version is configured with `access_type=bogus`. This is a non-standard
#     value and suggests a specific use case, potentially for testing or a flow that does
#     not require an access or refresh token. The user is immediately redirected to this
#     URL.
#     """
#     # Create the Google OAuth authorization URL
#     auth_url = (
#         f'{current_app.config["AUTHORIZATION_URL"]}?response_type=code'
#         f'&client_id={current_app.config["CLIENT_ID"]}'
#         f'&redirect_uri={current_app.config["REDIRECT_URI"]}'
#         f'&scope={current_app.config["SCOPE"]}'
#         f"&access_type=bogus"
#         f"&prompt=consent"
#         f"&state=secure_random_state"
#     )
#     # print(auth_url)
#     return redirect(auth_url)
