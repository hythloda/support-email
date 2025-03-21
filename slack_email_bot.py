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


## This is the best way to do it but I didn't get to work with heroku and thus have the other method
# Load environment variables
#load_dotenv()

# Slack credentials
#SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
#SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").strip()
#EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
#EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()

## Not ideal but works with heroku
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "")


if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise ValueError("Missing Slack credentials in environment variables")

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
    print("Incoming Slack Request:")
    print("Headers:", request.headers)

    # Verify Slack request signature
    if not verify_slack_request(request):
        print("Slack request verification failed!")
        return jsonify({"error": "Unauthorized"}), 401

    # Handle Slack's "x-www-form-urlencoded" requests
    if request.content_type == "application/x-www-form-urlencoded":
        data = request.form.to_dict()
    # Handle JSON requests
    elif request.content_type == "application/json":
        data = request.get_json()
    else:
        return jsonify({"error": "Invalid request type"}), 415

    print("Request verified successfully!")
    print("Payload:", data)

    # Respond to Slack's challenge request
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]}), 200

    return handler.handle(request)

@slack_app.command("/support")
def open_email_form(ack, body, client, logger):
    ack()  # Acknowledge the command
    logger.info("Received `/support` command. Attempting to open modal.")

    user_id = body["user_id"]
    sender_info = client.users_info(user=user_id)
    sender_name = sender_info["user"]["real_name"]

    logger.info(f"Fetching user info: {sender_name} ({user_id})")


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
        logger.info(f"Modal opened successfully: {response}")
    except Exception as e:
        logger.error(f"Failed to open modal: {e}")


@slack_app.view("email_submission")
def handle_email_submission(ack, body, client, logger):
    ack()  # Acknowledge the submission

    user_id = body["user"]["id"]
    sender_info = client.users_info(user=user_id)
    sender_name = sender_info["user"]["real_name"]

    logger.info(f"Processing email submission from: {sender_name} ({user_id})")

    # Extract email & message from the submitted form
    try:
        email_input = body["view"]["state"]["values"]["email_block"]["email_input"]["value"]
        message_text = body["view"]["state"]["values"]["message_block"]["message_input"]["value"]
        logger.info(f"Extracted email: {email_input}")
        logger.info(f"Message: {message_text}")

        if not email_input or "@" not in email_input:
            logger.warning("Invalid email format submitted!")
            client.chat_postMessage(channel=user_id, text="Invalid email format. Please try again with `/support`.")
            return

        # Send email
        subject = f"Support Request from {sender_name}"
        email_body = f"Slack inbound request from {sender_name} ({email_input}):\n\n{message_text}"

        msg = MIMEText(email_body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = SUPPORT_EMAIL

        logger.info("Attempting to send email...")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, SUPPORT_EMAIL, msg.as_string())

            logger.info("Email sent successfully!")
            client.chat_postMessage(channel=user_id, text="Your email has been sent successfully!")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            client.chat_postMessage(channel=user_id, text=f"Failed to send email: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing email submission: {e}")
        client.chat_postMessage(channel=user_id, text="error occurred. Please try again.")

@slack_app.shortcut("forward_to_intercom")
def handle_forward_shortcut(ack, shortcut, client, logger):
    ack()
    user_id = shortcut["user"]["id"]
    channel_id = shortcut["channel"]["id"]
    message_ts = shortcut["message"]["ts"]
    message_text = shortcut["message"]["text"]

    # Determine where the message was posted (channel name or DM)
    if channel_id.startswith("D"):
        location = "a direct message"
    else:
        try:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            location = f"#{channel_name}"
        except Exception as e:
            logger.warning(f"Failed to get channel info: {e}")
            location = f"<#{channel_id}>"

    # Get original message sender's name
    original_user = shortcut["message"].get("user")
    if original_user:
        sender_info = client.users_info(user=original_user)
        sender_name = sender_info["user"]["real_name"]
    else:
        sender_name = "Unknown"

    email_subject = f"Forwarded Slack Message from {sender_name}"
    email_body = f"Forwarded by {sender_name} in {location}\n\n"
    email_body += f"Slack message from {sender_name}:\n\n"
    email_body += f"{message_text}\n\n"
    email_body += f"Slack Message Link: https://slack.com/app_redirect?channel={channel_id}&message_ts={message_ts}"

    # Send email
    msg = MIMEText(email_body)
    msg["Subject"] = email_subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = SUPPORT_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, SUPPORT_EMAIL, msg.as_string())

        # Try replying in thread (if not DM)
        try:
            if channel_id.startswith("D"):
                # DMs: no thread_ts support
                client.chat_postMessage(
                    channel=channel_id,
                    text="Message forwarded to Intercom.",
                )
            else:
                # Channel: post in thread
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=message_ts,
                    text="Message forwarded to Intercom.",
                )
        except Exception as e:
            logger.warning(f"Post in original location failed: {e}")
            dm_channel = client.conversations_open(users=[user_id])["channel"]["id"]
            client.chat_postMessage(
                channel=dm_channel,
                text="Message was forwarded to Intercom, but I couldn’t post in the original thread.",
            )

    except Exception as e:
        logger.error(f"Failed to send email or notify user: {e}")
        dm_channel = client.conversations_open(users=[user_id])["channel"]["id"]
        client.chat_postMessage(
            channel=dm_channel,
            text="Failed to forward message to Intercom. Please try again later.",
        )



if __name__ == "__main__":
    # Running on Heroku, use Flask
    port = int(os.environ.get("PORT", 5000))  # Define port correctly
    app.run(host="0.0.0.0", port=port)
