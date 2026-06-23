import os
import sys
import requests
from datetime import datetime, timezone

API_KEY = os.environ["API_SPORTS_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ----- Step 0: Verify webhook with a plain text message -----
def send_plain_test():
    """Send a simple text message to Discord to confirm webhook works."""
    payload = {
        "content": "🧪 Goal bot test initiated… (plain text message check)"
    }
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code == 204:
        print("✅ Plain webhook message sent successfully.")
        return True
    else:
        print(f"❌ Webhook plain message failed: {r.status_code} {r.text}")
        return False

# ----- Step 1: Fetch fixture data -----
def get_fixture_data(fixture_id):
    url = f"{API_BASE}/fixtures?id={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch fixture {fixture_id}: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json().get("response")
    if not data:
        print(f"❌ No fixture found with ID {fixture_id}")
        return None, None
    fixture = data[0]

    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch events: {resp.status_code}")
        return fixture, None
    events = resp.json().get("response", [])
    return fixture, events

# ----- Step 2: Send goal embed (or fallback) -----
def send_goal_embed(fixture, goal=None):
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
        title = "⚽ TEST GOAL ALERT"
        description = f"No goals found in fixture, but everything works.\nFixture: {home} vs {away}"

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
        print("✅ Goal embed sent to Discord!")
    else:
        print(f"❌ Discord embed error: {r.status_code} {r.text}")

# ----- Main test flow -----
def main():
    # 1. Verify plain webhook message first
    if not send_plain_test():
        print("Aborting test – webhook is not working.")
        sys.exit(1)

    # 2. Get fixture ID
    fixture_id = os.environ.get("FIXTURE_ID")
    if not fixture_id:
        print("❌ No FIXTURE_ID provided. Set it as a secret or environment variable.")
        sys.exit(1)

    print(f"🧪 Testing with fixture ID: {fixture_id}")
    fixture, events = get_fixture_data(fixture_id)
    if not fixture:
        sys.exit(1)

    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    print(f"📺 Match: {home} vs {away}")

    goals = [e for e in events if e["type"] == "Goal"] if events else []
    if goals:
        send_goal_embed(fixture, goals[0])
        print(f"⚽ Sent first goal: {goals[0]['player']['name']} at {goals[0]['time']['elapsed']}'")
    else:
        send_goal_embed(fixture, None)
        print("⚠️ No goals in this fixture, but test is successful.")

if __name__ == "__main__":
    main()
