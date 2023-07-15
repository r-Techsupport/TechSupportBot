def parse_irc_message(event) -> dict:
    # Looking for username, hostmask, action, channel, content
    username = event.source.split("!")[0]
    hostmask = event.source.split("!")[1]
    channel = event.target
    content = event.arguments[0]

    return {
        "username": username,
        "hostmask": hostmask,
        "channel": channel,
        "content": content,
    }
