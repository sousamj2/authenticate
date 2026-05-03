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
    session["new_resume_request"] = True
    session["resume_email"] = user_email
    
    flash("A confirmation code has been sent to your email.")
    return redirect(url_for("profile.profile"))

@bp_server_actions.route("/verify_code", methods=["POST"])
def verify_code():
    """
    Verifies the 10-char code and triggers the background resume process.
    """
    if request.args.get("action") == "cancel":
        session.pop("waiting_for_resume_code", None)
        session.pop("new_resume_request", None)
        session.pop("resume_email", None)
        return redirect(url_for("profile.profile"))

    code = request.form.get("code", "").strip()
    print(f"DEBUG RESUME: Verifying code: {code}", flush=True)
    email = confirm_short_token(code)
    
    if not email:
        print(f"DEBUG RESUME: Code verification FAILED for code: {code}", flush=True)
        flash("Invalid or expired confirmation code.")
        session.pop("waiting_for_resume_code", None)
        session.pop("new_resume_request", None)
        return redirect(url_for("profile.profile"))
    
    print(f"DEBUG RESUME: Code verification SUCCESSFUL for email: {email}", flush=True)

    # Check for daily restart time (3:00 - 3:05 AM GMT)
    now_gmt = datetime.now(pytz.timezone('GMT'))
    if now_gmt.hour == 3 and 0 <= now_gmt.minute <= 5:
        flash("Daily server restart ongoing. Please wait.")
        return redirect(url_for("profile.profile"))

    # Start the resume process in a background thread
    session_id = session.get("session_id") or email
    session["session_id"] = session_id # Ensure it's persisted in session
    print(f"DEBUG RESUME: Using session_id: {session_id} for progress tracking", flush=True)
    
    server_progress[session_id] = {"step": "starting_machine", "progress": 10, "message": "Starting machine..."}
    
    # We need app context for the thread
    app = current_app._get_current_object()
    thread = threading.Thread(target=async_resume_sequence, args=(app, session_id))
    thread.start()
    
    session["resume_in_progress"] = True
    session.pop("waiting_for_resume_code", None)
    
    return redirect(url_for("profile.profile"))

@bp_server_actions.route("/status")
def get_status():
    """
    Returns the current progress of the server resume sequence.
    """
    session_id = session.get("session_id") or session.get("resume_email")
    # print(f"DEBUG RESUME: Polling status for session_id: {session_id}", flush=True)
    if not session_id or session_id not in server_progress:
        return {"status": "none"}
    
    return server_progress[session_id]

def async_resume_sequence(app, session_id):
    """
    Background task to handle the VM resume and service start.
    """
    import time
    with app.app_context():
        print(f"DEBUG RESUME: Starting sequence for session {session_id}", flush=True)
        try:
            instance_name = app.config.get("GCP_INSTANCE_NAME", "mcserver-mem8")
            zone = app.config.get("GCP_ZONE", "europe-west1-b")
            project_id = app.config.get("GCP_PROJECT_ID", "minecraft-server-july-12")
            
            def update_progress(step, progress, message):
                server_progress[session_id] = {"step": step, "progress": progress, "message": message}
                print(f"DEBUG RESUME [{session_id}]: {message}", flush=True)

            def run_cmd(cmd, shell=False):
                cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
                print(f"DEBUG RESUME: Running command: {cmd_str}", flush=True)
                try:
                    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=60)
                    if result.stdout:
                        print(f"DEBUG RESUME: STDOUT: {result.stdout.strip()}", flush=True)
                    if result.stderr:
                        print(f"DEBUG RESUME: STDERR: {result.stderr.strip()}", flush=True)
                    return result
                except Exception as e:
                    print(f"DEBUG RESUME: Exception: {str(e)}", flush=True)
                    return None

            # Step 1: Check and Resume VM
            update_progress("starting_machine", 20, "Checking VM status...")
            status_cmd = ["gcloud", "compute", "instances", "describe", instance_name, "--zone", zone, "--project", project_id, "--format=value(status)"]
            res = run_cmd(status_cmd)
            status = res.stdout.strip() if res else "UNKNOWN"
            print(f"DEBUG RESUME: Current VM Status: {status}", flush=True)

            if status == "SUSPENDED":
                update_progress("starting_machine", 30, "Resuming VM instance...")
                resume_cmd = ["gcloud", "compute", "instances", "resume", instance_name, "--zone", zone, "--project", project_id]
                run_cmd(resume_cmd)
            elif status == "TERMINATED":
                update_progress("starting_machine", 30, "Starting VM instance...")
                start_cmd = ["gcloud", "compute", "instances", "start", instance_name, "--zone", zone, "--project", project_id]
                run_cmd(start_cmd)
            
            # Polling for RUNNING
            update_progress("starting_machine", 40, "Waiting for VM to be RUNNING...")
            start_time = time.time()
            vm_ready = False
            while time.time() - start_time < 120:
                res = run_cmd(status_cmd)
                if res and res.stdout.strip() == "RUNNING":
                    vm_ready = True
                    break
                time.sleep(5)
            
            if not vm_ready:
                raise Exception("VM failed to reach RUNNING state in time.")

            # Step 2: Start Minecraft
            update_progress("starting_minecraft", 60, "Waiting for SSH and Minecraft service...")
            # We'll try to start the service via SSH
            ssh_base = f"gcloud compute ssh {instance_name} --zone {zone} --project {project_id} --quiet --"
            
            # Try to start the service
            update_progress("starting_minecraft", 75, "Starting Minecraft service...")
            run_cmd(f"{ssh_base} sudo systemctl start mcpserver.service", shell=True)
            
            # Step 3: Server is ready
            update_progress("ready", 90, "Server started! Waiting for plugins to load (60s)...")
            time.sleep(60)
            update_progress("completed", 100, "Done!")
            
            # Step 4: Reactivate auto-suspend monitor after 10 minutes
            # We start a separate thread for the 10-minute wait so this one can finish
            def wait_and_start_timer():
                print(f"DEBUG RESUME: Waiting 10 minutes to reactivate auto-suspend timer...", flush=True)
                time.sleep(600)
                try:
                    subprocess.run(["sudo", "systemctl", "start", "mc_auto_suspend.timer"], check=True)
                    print(f"DEBUG RESUME: Auto-suspend timer reactivated successfully.", flush=True)
                except Exception as e:
                    print(f"DEBUG RESUME: Failed to reactivate timer: {e}", flush=True)

            timer_thread = threading.Thread(target=wait_and_start_timer)
            timer_thread.daemon = True # Don't block app shutdown
            timer_thread.start()

            # Cleanup after some time
            time.sleep(30)
            if session_id in server_progress:
                del server_progress[session_id]

        except Exception as e:
            print(f"DEBUG RESUME: ERROR in sequence: {str(e)}", flush=True)
            update_progress("failed", 0, f"Error: {str(e)}")
            time.sleep(60)
            if session_id in server_progress:
                del server_progress[session_id]

@bp_server_actions.route("/confirm/<token>")
def confirm_resume(token):
    # This route is now deprecated in favor of verify_code but kept for compatibility if needed
    return redirect(url_for("profile.profile"))
