Some applications require external APIs, accounts, or setup to work. Following the setup steps below will allow you to get these extensions working.
# Applications
Setup needed: Discord webhook and Google form
## Discord webhook
The first thing you need to do is get a webhook created in the discord channel you are going to use.
- This requires the "Manage Webhooks" permission on discord
1. Open the "Server Settings" menu, then go to "Integrations" in the "APPS" category
2. Select the "Webhooks" category
3. Select "New Webhook"
4. Click on your new webhook, select the channel you wish for your applications to go in
5. Click "Copy Webhook URL"
- Your webhook URL is a secret, don't share it
6. Make sepearte note of your webhooks user ID. This can be found in the webhook URL after the follow part:
- discord.com/api/webhooks/
## Google forms
You will have to create and configure your google form, and you will need the webhook URL from above
- **Important** anyone with edit access to your form will be able to see the webhook URL
1. Create a new google form. Add at least one question. The first question must ask for the discord username
2. Click on the 3 dots in the corner, and select "Script Editor"
3. Use the script provided [here](utilities/application.js)
4. In the empty "POST_URL" variable, add your webhook URL
5. Click run. You will have to allow permissions on your google account
- Note, this will probably throw an error since the app isn't verified by google. You can safely ignore this error
6. On the left side menu, go to triggers, and select "Add Trigger"
7. You need to use the following options:
- Choose which function to run: onSubmit
- Choose which deployment should run: head
- Select event source: From Form
- Select event type: On form submit
8. Click save

At this point, your setup should be complete. Submit the form and test
# Battle.net
# ChatGPT
# Dump DBG
# Giphy
Setup needed: API key
## Giphy API
1. Go to the [giphy developer site](https://developers.giphy.com/dashboard/), create an account if you don't already have one
2. In the dashboard, select "Create an App"
3. Select the "API" option (the default is "SDK")
4. Select "Next Step"
5. Enter a name and description for you app, and check the box to agree
6. You will be presented with an API key, add this to the config.yml file
- Your API is a secret, don't share it
# Github
# Google/Youtube
# IRC
# News
# Spotify
# Weather
# Wolfram Alpha