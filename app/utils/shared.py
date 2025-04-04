from datetime import datetime


def datetime_now_sec():
    return datetime.now().replace(microsecond=0)
