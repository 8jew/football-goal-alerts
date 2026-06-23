import os
import sys
import requests
from datetime import datetime, timezone

API_KEY = os.environ["API_SPORTS_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

def send_plain_test():
    """Send a plain text message to verify the webhook works."""
    payload = {"content": "🧪 Goal bot test initiated (plain text check)"}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code == 204:
        print("✅ Plain text sent.")
        return True
    else:
        print(f"❌ Plain message failed: {r.status_code} {r.text}")
        return False

def get_fixture_data(fixture_id):
    url = f"{API_BASE}/fixtures?id={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Fixture fetch failed: {resp.status_code}")
        return None, None
    data = resp.json().get("response")
    if not data:
        return None, None
    fixture = data[0]

    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Events fetch failed: {resp.status_code}")
        return fixture, None
    events = resp.json().get("response", [])
    return fixture, events

def send_test_embed(fixture, goal=None):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    if goal:
        player = goal["player"]["name"]
        minute = goal["time"]["elapsed"]
        extra = goal["time"].get("extra")
        minute_str = f"{minute}+{extra}" if extra else str(minute)
        score = f"{fixture['goals']['home']} - {fixture['goals']['away']}"
        team_scored = home if goal["team"]["id"] == fixture["teams"]["home"]["id"] else away
        title = f"⚽ TEST GOAL! {minute_str}'"
        description = f"Scorer: **{player}** ({team_scored})"
    else:
        title = "🧪 TEST – No goals found"
        description = f"Fixture: {home} vs {away}"

    embed = {
        "title": title,
        "color": 0x57F287,
        "fields": [
            {"name": "Match", "value": f"{home} vs {away}", "inline": False},
            {"name": "Score", "value": f"{fixture.get('goals', {}).get('home', '?')} - {fixture.get('goals', {}).get('away', '?')}", "inline": True}
        ] if goal else [],
        "footer": {"text": "🧪 Test run — not a live alert"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if description:
        embed["description"] = description

    payload = {"embeds": [embed]}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code == 204:
        print("✅ Test embed sent!")
    else:
        print(f"❌ Discord embed error: {r.status_code} {r.text}")

def main():
    # 1. Plain text test
    if not send_plain_test():
        sys.exit(1)

    fixture_id = os.environ.get("FIXTURE_ID")
    if not fixture_id:
        print("❌ No FIXTURE_ID provided.")
        sys.exit(1)

    print(f"🧪 Testing fixture ID: {fixture_id}")
    fixture, events = get_fixture_data(fixture_id)
    if not fixture:
        sys.exit(1)

    goals = [e for e in events if e["type"] == "Goal"] if events else []
    if goals:
        send_test_embed(fixture, goals[0])
        print(f"⚽ Sent first goal: {goals[0]['player']['name']} at {goals[0]['time']['elapsed']}'")
    else:
        send_test_embed(fixture, None)
        print("⚠️ No goals, but test embed sent anyway.")

if __name__ == "__main__":
    main()
