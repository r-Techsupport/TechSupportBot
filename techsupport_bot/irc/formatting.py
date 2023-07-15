def get_user(split_message: list):
    username = split_message[0][1:].split("!")[0]
    return username


def get_hostmask(split_message: list):
    hostmask = split_message[0].split("!")[1]
    return hostmask


def get_action(split_message: list):
    action = split_message[1]
    return action


def get_channel(split_message: list):
    channel = split_message[2]
    return channel


def get_content(split_message: list):
    content = " ".join(split_message[3:])
    if content.startswith(":"):
        content = content[1:]
    return content


def split_space(raw_message: str):
    parts = raw_message[:-2].split(" ")
    return parts


def parse_irc_message(raw_message: str) -> dict:
    # Looking for username, hostmask, action, channel, content
    try:
        split_message = split_space(raw_message)
        username = get_user(split_message)
        hostmask = get_hostmask(split_message)
        action = get_action(split_message)
        channel = get_channel(split_message)
        content = get_content(split_message)
    except IndexError:
        return None

    return {
        "username": username,
        "hostmask": hostmask,
        "action": action,
        "channel": channel,
        "content": content,
    }
