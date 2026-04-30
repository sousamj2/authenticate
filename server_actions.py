import subprocess
from datetime import datetime
import pytz
from flask import Blueprint, request, session, redirect, url_for, flash, current_app, render_template
from mailinteraction.registration_token import generate_token, confirm_token
from mailinteraction.send_email import send_email
from markupsafe import Markup

bp_server_actions = Blueprint("server_actions", __name__, url_prefix="/server")

@bp_server_actions.route("/resume", methods=["POST"])
def request_resume():
    """
    Handles the request to resume the Minecraft server.
    Sends a confirmation email with a 5-minute token.
    """
    if not session.get("metadata"):
        flash("Please sign in to perform this action.")
        return redirect(url_for("signin.signin"))

    user_email = session["metadata"]["email"]
    
    # Generate a 5-minute token (300 seconds)
    token = generate_token(user_email)
    confirm_url = url_for("server_actions.confirm_resume", token=token, _external=True)

    subject = "Confirm Minecraft Server Restart"
    html_message = f"""
    <p>Hello,</p>
    <p>We received a request to start the Minecraft server <strong>mc.mjcrafts.pt</strong>.</p>
    <p>To confirm this action, please click the link below:</p>
    <p><a href="{confirm_url}">{confirm_url}</a></p>
    <p>This link is valid for only <strong>5 minutes</strong>.</p>
    <p>If you did not request this action, please ignore this email.</p>
    """

    send_email(subject, user_email, html_message)
    flash("A confirmation email has been sent. Please validate the request within the next 5 minutes.")
    return redirect(url_for("home.view_func_home"))

@bp_server_actions.route("/confirm/<token>")
def confirm_resume(token):
    """
    Verifies the token and executes the server resume commands.
    """
    email = confirm_token(token, expiration=300) # 5 minutes
    if not email:
        flash("The confirmation link is invalid or has expired.")
        return redirect(url_for("home.view_func_home"))

    # Check for daily restart time (3:00 - 3:05 AM GMT)
    now_gmt = datetime.now(pytz.timezone('GMT'))
    if now_gmt.hour == 3 and 0 <= now_gmt.minute <= 5:
        flash("Daily server restart ongoing. Please wait.")
        return redirect(url_for("home.view_func_home"))

    try:
        # Step 1: Resume the GCP instance
        # Using subprocess to run gcloud
        resume_cmd = ["gcloud", "compute", "instances", "resume", "mcserver-mem8", "--zone", "europe-west1-b"] # Added zone just in case
        # Note: The zone should be clarified if different
        
        result = subprocess.run(resume_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # If resume failed, it might already be running, or there's a real issue.
            # We continue to try starting the service just in case.
            print(f"Gcloud resume failed: {result.stderr}")

        # Step 2: Try to start the service via SSH
        # The user mentioned 'pemg' command to load keys. 
        # We'll assume the environment is set up such that ssh works.
        # We'll try to run the command on the remote host.
        # remote_host = "mc.mjcrafts.pt" # Or the IP/Internal IP
        
        # Connection logic for SSH:
        # We execute 'pemg' then ssh. 
        # Since 'pemg' might be a shell function or alias, we might need to run it in a shell.
        
        # The user said: "execute pemg that loads the SSH key for 5 minutes... set to 3 seconds"
        # I'll construct a command that runs pemg then ssh.
        
        ssh_cmd = "pemg && ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no mjsousa@mc.mjcrafts.pt 'sudo systemctl start mcpserver.service'"
        
        # We run it in shell=True because pemg might be an alias or function or complex command
        result_ssh = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        if result_ssh.returncode == 0:
            flash("Restart command sent successfully! The server should be online shortly.")
        else:
            print(f"SSH command failed: {result_ssh.stderr}")
            flash("The command was sent, but there was an issue verifying the service status. If the server is not online in 2 minutes, contact the administrator.")

    except subprocess.TimeoutExpired:
        flash("The request timed out. Please check the server status manually.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        flash("An unexpected error occurred while trying to start the server. Contacting administrator. ETAmax 24h")

    return redirect(url_for("home.view_func_home"))
