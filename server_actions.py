import subprocess
from datetime import datetime
import pytz
from flask import Blueprint, request, session, redirect, url_for, flash, current_app, render_template
from mailinteraction.registration_token import generate_token, confirm_token
from mailinteraction.send_email import send_email
from markupsafe import Markup

bp_server_actions = Blueprint("server_actions", __name__, url_prefix="/server")

from mailinteraction.registration_token import generate_token, confirm_token, generate_short_token, confirm_short_token
import threading

# Global state to track server start progress for sessions
# In a production app, this would be in Redis or DB
server_progress = {}

@bp_server_actions.route("/resume", methods=["POST"])
def request_resume():
    """
    Handles the request to resume the Minecraft server.
    Sends a confirmation email with a 10-char short token.
    """
    if not session.get("metadata"):
        flash("Please sign in to perform this action.")
        return redirect(url_for("signin.signin"))

    user_email = session["metadata"]["email"]
    
    # Generate a 10-char short token
    token = generate_short_token(user_email)

    subject = "Confirm Minecraft Server Restart"
    html_message = f"""
    <p>Hello,</p>
    <p>We received a request to start the Minecraft server <strong>mc.mjcrafts.pt</strong>.</p>
    <p>Your confirmation code is:</p>
    <h2 style="background: #f4f4f4; padding: 10px; text-align: center; letter-spacing: 5px;">{token}</h2>
    <p>Please enter this code in the portal to confirm the action.</p>
    <p>This code is valid for only <strong>5 minutes</strong>.</p>
    <p>If you did not request this action, please ignore this email.</p>
    """

    send_email(subject, user_email, html_message)
    
    # Store that we are waiting for a code in the session
    session["waiting_for_resume_code"] = True
    session["resume_email"] = user_email
    
    flash("A confirmation code has been sent to your email.")
    return redirect(url_for("home.view_func_home"))

@bp_server_actions.route("/verify_code", methods=["POST"])
def verify_code():
    """
    Verifies the 10-char code and triggers the background resume process.
    """
    code = request.form.get("code", "").strip()
    email = confirm_short_token(code)
    
    if not email:
        flash("Invalid or expired confirmation code.")
        return redirect(url_for("home.view_func_home"))

    # Check for daily restart time (3:00 - 3:05 AM GMT)
    now_gmt = datetime.now(pytz.timezone('GMT'))
    if now_gmt.hour == 3 and 0 <= now_gmt.minute <= 5:
        flash("Daily server restart ongoing. Please wait.")
        return redirect(url_for("home.view_func_home"))

    # Start the resume process in a background thread
    session_id = session.get("session_id") or email # Use email as fallback
    server_progress[session_id] = {"step": "starting_machine", "progress": 10, "message": "Starting machine..."}
    
    # We need app context for the thread
    app = current_app._get_current_object()
    thread = threading.Thread(target=async_resume_sequence, args=(app, session_id))
    thread.start()
    
    session["resume_in_progress"] = True
    session.pop("waiting_for_resume_code", None)
    
    return redirect(url_for("home.view_func_home"))

@bp_server_actions.route("/status")
def get_status():
    """
    Returns the current progress of the server resume sequence.
    """
    session_id = session.get("session_id") or session.get("resume_email")
    if not session_id or session_id not in server_progress:
        return {"status": "none"}
    
    return server_progress[session_id]

def async_resume_sequence(app, session_id):
    """
    Background task to handle the VM resume and service start.
    """
    import time
    with app.app_context():
        try:
            instance_name = app.config.get("GCP_INSTANCE_NAME", "mcserver-mem8")
            zone = app.config.get("GCP_ZONE", "europe-west1-b")
            remote_host = "sargedas@mc.mjcrafts.pt" # Using sargedas as verified by agent
            
            def update_progress(step, progress, message):
                server_progress[session_id] = {"step": step, "progress": progress, "message": message}
                print(f"PROGRESS [{session_id}]: {message}")

            def run_cmd(cmd, shell=False):
                try:
                    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=30)
                    return result
                except Exception:
                    return None

            # Step 1: Check and Resume VM
            update_progress("starting_machine", 20, "Checking VM status...")
            status_cmd = ["gcloud", "compute", "instances", "describe", instance_name, "--zone", zone, "--format=value(status)"]
            res = run_cmd(status_cmd)
            status = res.stdout.strip() if res else "UNKNOWN"

            if status == "SUSPENDED":
                update_progress("starting_machine", 30, "Resuming VM instance...")
                resume_cmd = ["gcloud", "compute", "instances", "resume", instance_name, "--zone", zone]
                run_cmd(resume_cmd)
            
            # Polling for RUNNING
            start_time = time.time()
            while time.time() - start_time < 60:
                res = run_cmd(status_cmd)
                if res and res.stdout.strip() == "RUNNING":
                    break
                time.sleep(5)
            
            # Step 2: Start Minecraft
            update_progress("starting_minecraft", 50, "Waiting for Minecraft service...")
            ssh_base = f"gcloud compute ssh {instance_name} --zone {zone} --quiet --"
            ssh_check_cmd = f"{ssh_base} sudo systemctl is-active mcpserver.service"
            
            start_time = time.time()
            while time.time() - start_time < 90:
                res = run_cmd(ssh_check_cmd, shell=True)
                if res and res.returncode in [0, 3]:
                    if res.stdout.strip() != "active":
                        update_progress("starting_minecraft", 70, "Starting Minecraft service...")
                        run_cmd(f"{ssh_base} sudo systemctl start mcpserver.service", shell=True)
                    break
                time.sleep(5)
            
            # Step 3: Server is ready
            update_progress("ready", 90, "Server is ready! Loading plugins (60s wait)...")
            time.sleep(60)
            update_progress("completed", 100, "Done!")
            
            # Cleanup after some time
            time.sleep(20)
            if session_id in server_progress:
                del server_progress[session_id]

        except Exception as e:
            update_progress("failed", 0, f"Error: {str(e)}")
            time.sleep(30)
            if session_id in server_progress:
                del server_progress[session_id]

@bp_server_actions.route("/confirm/<token>")
def confirm_resume(token):
    # This route is now deprecated in favor of verify_code but kept for compatibility if needed
    return redirect(url_for("home.view_func_home"))
