Some applications require external APIs, accounts, or setup to work. Following the setup steps below will allow you to get these extensions working.

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
# GitHub
Setup needed: API key, repository
## Repository
1. Make, or fork, a copy of this repo
2. Note down the name and owner of this new repo
## GitHub API key
1. On you GitHub account settings page, go to "Developer Settings"
2. On the side, go to "Personal access tokens", and select "Fine-grained token"
3. Name your token, select the resource owner
4. It's recommended that you pick "Only select repositories"
5. The only permissions needed is read and write under issues
6. After that, press generate token
# Google/Youtube
# News
Setup needed: API key
## NewsAPI.org API Key
1. Go to https://newsapi.org/register
2. Fill out your name, password, and fill out the captcha
3. Click submit, and you'll get your API key
# Relay
Setup needed: IRC account
## IRC account
1. Login to libera.chat using your client of choice
2. Reigster your nickname (/msg NickServ REGISTER YourPassword youremail@example.com)
3. You will get an email, run the command in your email to verify your registration
### (Optional) Getting a cloak
Cloaks are useful if you need to join a channel that is whitelisted, as your IP can change but a cloak cannot
1. Join the clock channel (/join #libera-cloak)
2. Send the message (!cloakme)
## Config.yml setup
1. Put your IRC account and server information in config.yml, and enable IRC
```
irc:
    enable_irc: False
    server: "irc.libera.chat"
    port: 6667
    channels: [""]
    name: ""
    password: ""
```
# Spotify
# Weather
# Wolfram Alpha
Setup needed: API Key
## WolframAlpha API Key
1. Create an account on wolfram alpha
2. Go to https://developer.wolframalpha.com/portal/myapps/
3. Click on "Get an app ID"
4. Fill out the information, and you will be presented with your API key