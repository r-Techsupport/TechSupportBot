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


def parse_ban_message(event) -> dict:
    # Looking for username, hostmask, action, channel, content
    username = event.source.split("!")[0]
    hostmask = event.source.split("!")[1]
    channel = event.target

    if "+b" in event.arguments[0]:
        action = "banned"
    elif "+b" in event.arguments[0]:
        action = "unbanned"
    content = f"{event.arguments[1]} was {action} from {channel}"

    return {
        "username": username,
        "hostmask": hostmask,
        "channel": channel,
        "content": content,
    }
