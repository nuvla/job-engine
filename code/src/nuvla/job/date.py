# -*- coding: utf-8 -*-
# should be moved to nuvla.api.util.date
from datetime import datetime, time, timezone, timedelta


def parse_nuvla_date(date: str) -> datetime:
    return datetime.fromisoformat(date[:-1] + '+00:00')


def nuvla_date(date: datetime) -> str:
    return date.astimezone(timezone.utc) \
        .isoformat('T', timespec='milliseconds') \
        .replace('+00:00', 'Z')


def utcnow() -> datetime:
    return datetime.utcnow()


def today_start_time() -> datetime:
    return datetime.combine(utcnow(), time.min)


def today_end_time() -> datetime:
    return datetime.combine(utcnow(), time.max)


def _time_rm_nanos(time_str):
    time1, time2 = time_str.rsplit('.', 1)
    return '.'.join([time1, time2[:6]])


def timestr2dtime(time_str):
    return datetime.fromisoformat(_time_rm_nanos(time_str))


def plus(date: datetime, td: timedelta) -> datetime:
    return date + td


def minus(date: datetime, td: timedelta) -> datetime:
    return date - td
