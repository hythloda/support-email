from flask import Flask, request, jsonify
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

@app.route("/slack/events", methods=["POST"])
def slack_events():
    # ✅ Ensure request is JSON
    if request.content_type != "application/json":
        return "Invalid request type", 415  # 🚨 Fix for "415 Unsupported Media Type"

    data = request.get_json()

    # ✅ Respond to Slack's challenge request
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    # ✅ Pass all other events to Slack Bolt
    return handler.handle(request)

# Slash Command /email
@slack_app.command("/email")
def open_email_form(ack, body, client):
    ack()  # Acknowledge the command

    user_id = body["user_id"]
    sender_info = client.users_info(user=user_id)
    sender_name = sender_info["user"]["real_name"]

    # Open a modal to collect the email and message
    client.views_open(
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

@slack_app.view("email_submission")
def handle_email_submission(ack, body, client):
    ack()  # Acknowledge the submission

    user_id = body["user"]["id"]
    sender_info = client.users_info(user=user_id)
    sender_name = sender_info["user"]["real_name"]

    # Extract email & message from the submitted form
    email_input = body["view"]["state"]["values"]["email_block"]["email_input"]["value"]
    message_text = body["view"]["state"]["values"]["message_block"]["message_input"]["value"]

    if not email_input or "@" not in email_input:
        client.chat_postMessage(channel=user_id, text="❌ Invalid email format. Please try again with `/email`.")
        return

    # Send email
    subject = f"Support Request from {sender_name}"
    email_body = f"Message from {sender_name} ({email_input}):\n\n{message_text}"

    msg = MIMEText(email_body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = "support@riscv.org"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, "support@riscv.org", msg.as_string())

        client.chat_postMessage(channel=user_id, text="✅ Your email has been sent successfully!")
    except Exception as e:
        client.chat_postMessage(channel=user_id, text=f"❌ Failed to send email: {str(e)}")

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

