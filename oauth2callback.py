from flask import Blueprint, request, session, redirect, url_for,current_app
import requests

bp_oauth2callback = Blueprint('oauth2callback', __name__, url_prefix='/oauth2callback')


@bp_oauth2callback.route('/')
def oauth2callback():
    """
    Handles the OAuth2 callback from the authorization server.

    This function is triggered after the user authorizes the application. It receives an
    authorization code from the request arguments, which it then exchanges for an access token
    and an ID token from the token endpoint.

    The obtained tokens and user information (fetched from the userinfo endpoint) are stored
    in the session. Finally, it redirects the user to the `check_user` blueprint to
    complete the login or registration process.
    """
    code = request.args.get('code')
    
    # Use the same dynamic redirect URI for the exchange
    redirect_uri = url_for('oauth2callback.oauth2callback', _external=True)

    # Exchange code for tokens
    data = {
        'code': code,
        'client_id': current_app.config["CLIENT_ID"],
        'client_secret': current_app.config["CLIENT_SECRET"],
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    response = requests.post(current_app.config["TOKEN_URL"], data=data)
    tokens = response.json()

    # Save tokens in session or your database
    session['access_token'] = tokens.get('access_token')
    session['id_token'] = tokens.get('id_token')
    
    userinfo_response = requests.post(
        'https://www.googleapis.com/oauth2/v3/userinfo',
        headers={'Authorization': f'Bearer {session["access_token"]}'}
    )
    session['userinfo'] = userinfo_response.json()
    userinfo = userinfo_response.json()
    return redirect(url_for('check_user.check_user'))
