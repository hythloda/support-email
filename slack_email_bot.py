import os
import smtplib
from email.mime.text import MIMEText
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Debug: Print environment variables
print("SLACK_BOT_TOKEN:", os.getenv("SLACK_BOT_TOKEN"))
print("SLACK_SIGNING_SECRET:", os.getenv("SLACK_SIGNING_SECRET"))
print("EMAIL_SENDER:", os.getenv("EMAIL_SENDER"))
print("EMAIL_PASSWORD:", os.getenv("EMAIL_PASSWORD"))

# Slack credentials
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").strip()
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "").strip()  # Add this to .env if missing
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()

# Ensure variables are not missing or empty
if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError("Missing Slack credentials in .env file (or values are empty)")
if not EMAIL_SENDER or not EMAIL_PASSWORD:
    raise ValueError("Missing email credentials in .env file (or values are empty)")

# Initialize Slack app *AFTER* checking variables
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Email credentials
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = "support@r-consortium.org"

# Ensure tokens exist
if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not SLACK_APP_TOKEN:
    raise ValueError("Missing Slack credentials in .env file")

if not EMAIL_SENDER or not EMAIL_PASSWORD:
    raise ValueError("Missing email credentials in .env file")

# Initialize Slack app
slack_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Define the /email command
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


# Start the Slack bot
if __name__ == "__main__":
    SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()
