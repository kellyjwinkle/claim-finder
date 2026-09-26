"""Scheduled job: alert on upcoming claim deadlines (30/14/7/3/1 days out)."""
import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))
from components.database import get_service_client  # noqa: E402

ALERT_WINDOWS = (30, 14, 7, 3, 1)


def get_upcoming_deadlines(client):
    today = date.today()
    windows = [today + timedelta(days=d) for d in ALERT_WINDOWS]
    rows = client.table("settlements").select(
        "id, case_name, claim_deadline"
    ).eq("status", "verified").execute().data or []
    alerts = [r for r in rows if r.get("claim_deadline") and
              date.fromisoformat(r["claim_deadline"]) in windows]
    return alerts


def send_alert(alert):
    webhook_url = os.environ.get("DEADLINE_ALERT_WEBHOOK_URL")
    message = f"Claim Finder: '{alert['case_name']}' deadline is {alert['claim_deadline']}."
    if webhook_url:
        import urllib.request
        import json
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps({"text": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    else:
        print(message)


def main():
    client = get_service_client()
    for alert in get_upcoming_deadlines(client):
        send_alert(alert)


if __name__ == "__main__":
    main()
