import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ----- Configuration -----
API_KEY = os.environ["API_SPORTS_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# League IDs (World Cup: 1, Premier: 39, La Liga: 140)
LEAGUES = [1, 39, 140]

# State file
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
        print(f"Error fetching fixtures: {resp.status_code}")
        return []
    data = resp.json()
    return [f for f in data.get("response", []) if f["league"]["id"] in LEAGUES]

# ----- Fetch fixtures for a specific date -----
def get_fixtures_by_date(date_str, league_id):
    url = f"{API_BASE}/fixtures?league={league_id}&season=2026&date={date_str}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error fetching fixtures for {date_str}: {resp.status_code}")
        return []
    return resp.json().get("response", [])

# ----- Fetch events for a fixture -----
def get_fixture_events(fixture_id):
    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error fetching events: {resp.status_code}")
        return []
    return resp.json().get("response", [])

# ----- Send a goal embed -----
def send_goal_embed(goal, fixture):
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
        "color": 0x57F287,
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

# ----- Send final result embed -----
def send_final_result_embed(fixture):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_score = fixture["goals"]["home"] or 0
    away_score = fixture["goals"]["away"] or 0
    status = fixture["fixture"]["status"]["long"]

    embed = {
        "title": f"🏁 FULL TIME",
        "color": 0xE67E22,   # orange
        "fields": [
            {"name": "Match", "value": f"{home} vs {away}", "inline": False},
            {"name": "Score", "value": f"{home_score} - {away_score}", "inline": True},
            {"name": "Status", "value": status, "inline": True}
        ],
        "footer": {"text": "📊 Match Result"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {"embeds": [embed]}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code == 204:
        print(f"✅ Sent final result: {home} {home_score}-{away_score} {away}")
    else:
        print(f"❌ Discord error: {r.status_code} {r.text}")

# ----- Check for finished matches -----
def check_finished_matches(state, manual_mode=False):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sent_finals = state.get("sent_finals", [])
    now = datetime.now(timezone.utc)

    for league in LEAGUES:
        fixtures = get_fixtures_by_date(today, league)
        if not fixtures:
            continue

        for fixture in fixtures:
            fid = str(fixture["fixture"]["id"])
            status = fixture["fixture"]["status"]["short"]

            # Only finished matches
            if status not in ["FT", "AET", "PEN"]:
                continue

            # Skip if already sent
            if fid in sent_finals:
                continue

            # Time limit: only send if within 2 hours, OR manual mode (send all)
            match_time = datetime.fromtimestamp(fixture["fixture"]["timestamp"], timezone.utc)
            time_diff = (now - match_time).total_seconds()

            if not manual_mode and time_diff > 7200:  # 2 hours
                continue

            # Send result
            send_final_result_embed(fixture)
            sent_finals.append(fid)
            state["sent_finals"] = sent_finals
            save_state(state)
            print(f"✅ Final result sent for {fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}")

# ----- Main logic -----
def main():
    # Detect if manually triggered
    manual_run = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if manual_run:
        print("🔁 Manual run detected – will send results of all finished matches today.")

    print("Checking for live fixtures...")
    fixtures = get_live_fixtures()

    state = load_state()
    updated = False

    # Process live fixtures for goals
    if fixtures:
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
                send_goal_embed(goal, match)

        if updated:
            save_state(state)
            print("State updated for goals.")
    else:
        print("No live matches in selected leagues.")

    # Now check for finished matches
    print("Checking for recently finished matches...")
    check_finished_matches(state, manual_mode=manual_run)

if __name__ == "__main__":
    main()
