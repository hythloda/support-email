from flask import Flask, request, jsonify
import time 
import hashlib
import hmac
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText


# Load environment variables
load_dotenv()

# Slack credentials
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").strip()
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "").strip()  # Required for Socket Mode
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()

# Ensure required environment variables are set
if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError("Missing Slack credentials in .env file (or values are empty)")
if not EMAIL_SENDER or not EMAIL_PASSWORD:
    raise ValueError("Missing email credentials in .env file (or values are empty)")

# Initialize Slack Bolt App
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Flask for handling Slack events (needed for request verification)
app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

def verify_slack_request(req):
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    slack_signature = req.headers.get("X-Slack-Signature")

    # If the request is too old, reject it (to prevent replay attacks)
    if abs(time.time() - int(timestamp)) > 300:
        return False

    # Create the Slack signature base string
    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}"

    # Compute the expected signature
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature)


@app.route("/slack/events", methods=["POST"])
def slack_events():
    print("📩 Incoming Slack Request:")
    print("Headers:", request.headers)

    # ✅ Verify Slack request signature
    if not verify_slack_request(request):
        print("🚨 Slack request verification failed!")
        return jsonify({"error": "Unauthorized"}), 401

    # ✅ Handle Slack's "x-www-form-urlencoded" requests
    if request.content_type == "application/x-www-form-urlencoded":
        data = request.form.to_dict()
    # ✅ Handle JSON requests
    elif request.content_type == "application/json":
        data = request.get_json()
    else:
        return jsonify({"error": "Invalid request type"}), 415

    print("✅ Request verified successfully!")
    print("Payload:", data)

    # ✅ Respond to Slack's challenge request
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]}), 200

    return handler.handle(request)

@slack_app.command("/support")
def open_email_form(ack, body, client, logger):
    ack()  # Acknowledge the command
    logger.info("📝 Received `/support` command. Attempting to open modal.")

    user_id = body["user_id"]
    sender_info = client.users_info(user=user_id)
    sender_name = sender_info["user"]["real_name"]

    logger.info(f"🔍 Fetching user info: {sender_name} ({user_id})")


    try:
        response = client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "email_submission",
                "title": {"type": "plain_text", "text": "Send an Email"},
                "submit": {"type": "plain_text", "text": "Send"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "email_block",
                        "label": {"type": "plain_text", "text": "Enter your Email"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "email_input",
                            "placeholder": {"type": "plain_text", "text": "you@example.com"},
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "message_block",
                        "label": {"type": "plain_text", "text": "Enter Your Message"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "message_input",
                            "multiline": True,
                            "placeholder": {"type": "plain_text", "text": "Enter your message here"},
                        },
                    },
                ],
            },
        )
        logger.info(f"✅ Modal opened successfully: {response}")
    except Exception as e:
        logger.error(f"❌ Failed to open modal: {e}")


@slack_app.view("email_submission")
def handle_email_submission(ack, body, client, logger):
    ack()  # Acknowledge the submission

    user_id = body["user"]["id"]
    sender_info = client.users_info(user=user_id)
    sender_name = sender_info["user"]["real_name"]

    logger.info(f"📩 Processing email submission from: {sender_name} ({user_id})")

    # Extract email & message from the submitted form
    try:
        email_input = body["view"]["state"]["values"]["email_block"]["email_input"]["value"]
        message_text = body["view"]["state"]["values"]["message_block"]["message_input"]["value"]
        logger.info(f"📨 Extracted email: {email_input}")
        logger.info(f"📝 Message: {message_text}")

        if not email_input or "@" not in email_input:
            logger.warning("❌ Invalid email format submitted!")
            client.chat_postMessage(channel=user_id, text="❌ Invalid email format. Please try again with `/support`.")
            return

        # Send email
        subject = f"Support Request from {sender_name}"
        email_body = f"Message from {sender_name} ({email_input}):\n\n{message_text}"

        msg = MIMEText(email_body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = "support@riscv.org"

        logger.info("📧 Attempting to send email...")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, "support@riscv.org", msg.as_string())

            logger.info("✅ Email sent successfully!")
            client.chat_postMessage(channel=user_id, text="✅ Your email has been sent successfully!")
        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            client.chat_postMessage(channel=user_id, text=f"❌ Failed to send email: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Error processing email submission: {e}")
        client.chat_postMessage(channel=user_id, text="❌ An error occurred. Please try again.")

# **Start the bot correctly based on execution environment**
if __name__ == "__main__":
    # Determine whether to use Flask (Heroku) or Socket Mode (local)
    if os.getenv("HEROKU_APP_NAME"):
        # Running on Heroku, use Flask
        port = int(os.environ.get("PORT", 5000))  # Define port correctly
        app.run(host="0.0.0.0", port=port)
    else:
        # Running locally, use Slack Socket Mode
        SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()

