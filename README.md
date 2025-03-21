# Slack Support Bot

A simple Slack bot that allows users to send support requests via `/support`, which opens a form and sends the message to a support email.

## Why Use This?

Many organizations want an easy way for team members to contact support directly from Slack without searching for email addresses or external forms. This bot makes it super simple: type `/support`, fill out a quick form, and your message goes straight to a designated support inbox.

## Requirements

Before you begin, you'll need:

* A GitHub account
* A Slack workspace where you are `owner` and create a new app
* A Heroku account (for free hosting)
* A Gmail account with 2FA for an app password
* Basic terminal or command line access (copy-paste is fine!)

## Setup Instructions

### Step 1: Clone the Repository

Open your terminal and run:

```
git clone https://github.com/YOUR_USERNAME/slack-support-bot.git
cd slack-support-bot
```

Replace `YOUR_USERNAME` with your actual GitHub username if it's a fork.

I recommend opening up the entire directory with your favorite editor such as VSCode

### Step 2: Create a Slack App

* Go to [https://api.slack.com/apps](https://api.slack.com/apps)

* Click "Create New App"

* Choose From scratch

* Name it something like Support Bot, choose your workspace

* Under "Slash Commands", create:

    * Command: /support
    * Request URL: (leave blank for now)
    * Short Description: "Open a support form"
    * Usage Hint: leave blank

* Under "OAuth & Permissions", add these bot token scopes:

    * commands
    * users:read
    * chat:write
    * chat:write.public
    * channels:read
    * Click Install App to Workspace and copy into your local .env:
        * Bot User OAuth Token (starts with xoxb- and is first line of .env
        * Signing Secret (found under Basic Information, second line of .env)

### Step 3: Set Up Email Sending

In a web browser of your choice you need an "App Passwords".

Recommend Googling this as Google changes the instructions often. Your account MUST have 2FA to have an app password

Once you have the Gmail app password, put in the local .env:
* Your Gmail address (line 3 of .env)
* App password (used instead of your regular password line 4 of .env and put the letters and spaces inside the quotes)

### Step 4: Deploy to Heroku

I like Heroku because it is free. Using this enables your Slack bot to be accessible all the time as it is running on Heroku. 

You need to make an account [here](https://www.heroku.com/). It also needs a payment method to validate your account, you will not be charged any fees. Account verification helps them prevent abuse. Having a credit card on file is the most reliable way of obtaining verified contact information but it is not used. 

Then if you don’t have Heroku installed and if you are on a mac then go to the terminal where you have your code clone:

```
brew tap heroku/brew && brew install heroku
heroku login
```
This prompts a window to log in. 


Then you will push your app to Heroku
```
heroku create slack-support-bot
git push heroku main
```
You can change the name of `slack-support-bot` to be anything. If you run more than one slack I recommend something like `project-slack-support-bot`

Notice the URL that it gives you it will be something like

```
https://your-slack-support-bot-NUMBERS.herokuapp.com
```

Set the environment variables on Heroku, this is copy-paste from your .env file with some small edits in the prefix and `--app`:
```
heroku config:set SLACK_BOT_TOKEN=xoxb-MOREDIGITS --app slack-support-bot
heroku config:set SLACK_SIGNING_SECRET=LOTSOFCHARS --app slack-support-bot
heroku config:set EMAIL_SENDER=NAME@linuxfoundation.org  --app slack-support-bot
heroku config:set EMAIL_PASSWORD="16 letters with spaces"  --app slack-support-bot
heroku config:set SUPPORT_EMAIL="support@DOMAIN"  --app slack-support-bot
```

### Step 5: Add the Heroku URL to Your Slack App

Now you have the URL that Heroku uses for your app. This is something you need so you can sync your bot with your slack instance. 

Go to your app’s Slash Command config in your browser.
Set the Request URL to the URL given from the terminal but add `/slack/events` to the end. This is because the code is written to expect that

```
https://slack-support-bot-NUMBERS.herokuapp.com/slack/events
```
Replace slack-support-bot with the actual Heroku app name.

Save changes.

Go to "Interactivity & Shortcuts." 
* Enable Interactivity
* Enter the same URL
* Save Changes


Go to "Event Subscriptions." 

* Enable event subscriptions
* Enter the same URL
* Save Changes

### Step 6: Test the Bot
In your Slack workspace:

* Type `/support`
* A form should open
* Fill in your email and message
* Submit — and it should send an email
* Check Intercom to see if it is there (takes a few minutes)


## Common Issues

* `dispatch_failed` in Slack: 
    * This usually means the bot is crashing. 
    * Run heroku logs --tail to check what's wrong
    * `heroku logs --tail --app slack-support-bot`
* No email sent
    * Double-check your email and app password

##  Need Help?
* Feel free to open an issue in the repo or reach out to the project maintainer. Everyone starts somewhere — we've got you.
* Reach out to me in slack

