import os
import json
import requests
from datetime import datetime, timezone

# ----- Configuration -----
API_KEY = os.environ["API_SPORTS_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# League IDs (Premier League: 39, La Liga: 140)
LEAGUES = [1, 39, 140]   # 1 = FIFA World Cup

# State file to track already sent goals
STATE_FILE = "sent_goals.json"

# ----- Helper: load / save state -----
def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ----- Fetch live fixtures -----
def get_live_fixtures():
    url = f"{API_BASE}/fixtures?live=all"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error fetching fixtures: {resp.status_code} {resp.text}")
        return []
    data = resp.json()
    fixtures = data.get("response", [])
    # Filter only our leagues
    return [f for f in fixtures if f["league"]["id"] in LEAGUES]

# ----- Fetch events for a specific fixture -----
def get_fixture_events(fixture_id):
    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error fetching events for fixture {fixture_id}: {resp.status_code}")
        return []
    return resp.json().get("response", [])

# ----- Send a single goal as an embed (no image) -----
def send_goal_discord(goal, fixture):
    player = goal["player"]["name"]
    minute = goal["time"]["elapsed"]
    if goal["time"].get("extra"):
        minute = f"{minute}+{goal['time']['extra']}"

    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    score = f"{fixture['goals']['home']} - {fixture['goals']['away']}"
    team_scored = home if goal["team"]["id"] == fixture["teams"]["home"]["id"] else away

    embed = {
        "title": f"⚽ GOAL! {minute}'",
        "color": 0x57F287,          # Discord green
        "fields": [
            {"name": "Match", "value": f"{home} vs {away}", "inline": False},
            {"name": "Scorer", "value": player, "inline": True},
            {"name": "Score", "value": score, "inline": True},
            {"name": "Team", "value": team_scored, "inline": True}
        ],
        "footer": {"text": "⚽ Live Goal Alert"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {"embeds": [embed]}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code == 204:
        print(f"✅ Sent goal: {player} {minute}' ({team_scored})")
    else:
        print(f"❌ Discord error: {r.status_code} {r.text}")

# ----- Main logic -----
def main():
    print("Checking for live fixtures...")
    fixtures = get_live_fixtures()
    if not fixtures:
        print("No live matches in selected leagues.")
        return

    state = load_state()
    updated = False

    for match in fixtures:
        fid = match["fixture"]["id"]
        print(f"Processing match {fid}: {match['teams']['home']['name']} vs {match['teams']['away']['name']}")
        events = get_fixture_events(fid)

        if str(fid) not in state:
            state[str(fid)] = []

        new_goals = []
        for event in events:
            if event["type"] == "Goal":
                extra = event["time"].get("extra", 0)
                key = f"{event['time']['elapsed']}-{extra}-{event['player']['name']}"
                if key not in state[str(fid)]:
                    new_goals.append(event)
                    state[str(fid)].append(key)
                    updated = True

        new_goals.sort(key=lambda g: (g["time"]["elapsed"], g["time"].get("extra", 0)))

        for goal in new_goals:
            send_goal_discord(goal, match)

    if updated:
        save_state(state)
        print("State updated.")
    else:
        print("No new goals found.")

if __name__ == "__main__":
    main()
