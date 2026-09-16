from datetime import datetime, timedelta


def parse_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:26] if fmt.endswith("%f") else text[:19], fmt)
        except ValueError:
            continue
    return None


def interval_due(last_finished, interval_minutes, now):
    try:
        minutes = int(interval_minutes)
    except (TypeError, ValueError):
        minutes = 15
    minutes = max(minutes, 1)
    finished = parse_datetime(last_finished)
    if finished is None:
        return True
    current = parse_datetime(now) or now
    return current >= finished + timedelta(minutes=minutes)
