# NB! Requires Python 3.7 due to datetime.fromisoformat()

from datetime import datetime, timedelta
import hashlib


def _time_rm_nanos(time_str):
    time1, time2 = time_str.rsplit('.', 1)
    return '.'.join([time1, time2[:6]])


def timestr2dtime(time_str):
    return datetime.fromisoformat(_time_rm_nanos(time_str))


def timenow():
    return datetime.utcnow()


def timenow_plus(seconds):
    return timenow() + timedelta(seconds=seconds)


def utc_from_now_iso(seconds):
    return timenow_plus(seconds).isoformat('T', timespec='milliseconds') + 'Z'


def unique_id(*args):
    return hashlib.md5(':'.join(map(str, args)).encode()).hexdigest()

