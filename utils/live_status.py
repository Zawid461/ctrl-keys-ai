live_logs = []


def add_live_log(message):
    live_logs.append(message)


def get_live_logs():
    return live_logs


def clear_live_logs():
    global live_logs
    live_logs = []