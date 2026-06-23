import os
import json
import requests
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ----- Configuration -----
API_KEY = os.environ["API_SPORTS_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

LEAGUES = [39, 140]          # Premier League, La Liga
STATE_FILE = "sent_goals.json"

# ----- State helpers -----
def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ----- API calls -----
def get_live_fixtures():
    url = f"{API_BASE}/fixtures?live=all"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error fetching fixtures: {resp.status_code} {resp.text}")
        return []
    data = resp.json()
    return [f for f in data.get("response", []) if f["league"]["id"] in LEAGUES]

def get_fixture_events(fixture_id):
    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error fetching events: {resp.status_code}")
        return []
    return resp.json().get("response", [])

# ----- Image generator -----
def generate_match_image(fixture, goal):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_score = fixture["goals"]["home"] or 0
    away_score = fixture["goals"]["away"] or 0
    player = goal["player"]["name"]
    minute = goal["time"]["elapsed"]
    extra = goal["time"].get("extra")
    minute_str = f"{minute}'" + (f"+{extra}" if extra else "")
    team_scored = home if goal["team"]["id"] == fixture["teams"]["home"]["id"] else away

    WIDTH, HEIGHT = 800, 400
    bg = (30, 30, 40)
    green = (87, 242, 135)
    white = (255, 255, 255)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    # Use default font (no external file needed)
    font_big = ImageFont.load_default()
    font_med = ImageFont.load_default()
    font_small = ImageFont.load_default()

    # Top green bar with "GOAL!"
    draw.rectangle([0, 0, WIDTH, 70], fill=green)
    draw.text((20, 10), f"⚽ GOAL!  {minute_str}", fill=(0, 0, 0), font=font_big)

    # Team names
    y = 100
    draw.text((40, y), home, fill=white, font=font_med)
    draw.text((40, y + 50), away, fill=white, font=font_med)

    # Score (centered)
    score_text = f"{home_score} - {away_score}"
    bbox = draw.textbbox((0, 0), score_text, font=font_big)
    score_x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((score_x, y), score_text, fill=green, font=font_big)

    # Scorer info
    draw.text((40, y + 110), f"Scorer: {player} ({team_scored})", fill=white, font=font_small)

    # Footer
    elapsed = fixture['fixture']['status'].get('elapsed', 0)
    draw.text((40, HEIGHT - 40), f"Live • {elapsed}'", fill=(180, 180, 180), font=font_small)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ----- Send to Discord -----
def send_goal_discord(goal, fixture):
    img_buffer = generate_match_image(fixture, goal)
    files = {"file": ("goal.png", img_buffer, "image/png")}
    embed = {
        "title": "⚽ New Goal!",
        "color": 0x57F287,
        "fields": [
            {"name": "Match", "value": f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}", "inline": False},
            {"name": "Score", "value": f"{fixture['goals']['home']} - {fixture['goals']['away']}", "inline": True}
        ],
        "image": {"url": "attachment://goal.png"}
    }
    payload = {"embeds": [embed]}
    r = requests.post(DISCORD_WEBHOOK, data={"payload_json": json.dumps(payload)}, files=files)
    if r.status_code == 204:
        print(f"✅ Sent goal image: {goal['player']['name']} {goal['time']['elapsed']}'")
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
        print(f"Processing {match['teams']['home']['name']} vs {match['teams']['away']['name']}")
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
