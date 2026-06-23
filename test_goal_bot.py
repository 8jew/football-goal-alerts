import os
import sys
import requests
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

API_KEY = os.environ["API_SPORTS_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ----- Webhook test (plain message) -----
def send_plain_test():
    payload = {"content": "🧪 Goal bot test initiated… (plain text check)"}
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    if r.status_code == 204:
        print("✅ Plain webhook message sent.")
        return True
    else:
        print(f"❌ Plain message failed: {r.status_code} {r.text}")
        return False

# ----- Fetch fixture data -----
def get_fixture_data(fixture_id):
    url = f"{API_BASE}/fixtures?id={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Failed fixture: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json().get("response")
    if not data:
        print("❌ No fixture found")
        return None, None
    fixture = data[0]

    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ Failed events: {resp.status_code}")
        return fixture, None
    return fixture, resp.json().get("response", [])

# ----- Same image generator (copied from main) -----
def generate_test_image(fixture, goal=None):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_score = fixture["goals"]["home"] or 0
    away_score = fixture["goals"]["away"] or 0
    WIDTH, HEIGHT = 800, 400
    bg = (30, 30, 40)
    green = (87, 242, 135)
    white = (255, 255, 255)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    font_big = ImageFont.load_default()
    font_med = ImageFont.load_default()
    font_small = ImageFont.load_default()

    if goal:
        player = goal["player"]["name"]
        minute = goal["time"]["elapsed"]
        extra = goal["time"].get("extra")
        minute_str = f"{minute}'" + (f"+{extra}" if extra else "")
        team_scored = home if goal["team"]["id"] == fixture["teams"]["home"]["id"] else away
        draw.rectangle([0, 0, WIDTH, 70], fill=green)
        draw.text((20, 10), f"🧪 TEST GOAL! {minute_str}", fill=(0, 0, 0), font=font_big)
        y = 100
        draw.text((40, y), home, fill=white, font=font_med)
        draw.text((40, y + 50), away, fill=white, font=font_med)
        score_text = f"{home_score} - {away_score}"
        bbox = draw.textbbox((0, 0), score_text, font=font_big)
        score_x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((score_x, y), score_text, fill=green, font=font_big)
        draw.text((40, y + 110), f"Scorer: {player} ({team_scored})", fill=white, font=font_small)
    else:
        draw.rectangle([0, 0, WIDTH, 70], fill=green)
        draw.text((20, 10), "🧪 TEST – No goals found", fill=(0, 0, 0), font=font_big)
        draw.text((40, 140), f"{home} vs {away}", fill=white, font=font_med)

    draw.text((40, HEIGHT - 40), "Test run • not live", fill=(180, 180, 180), font=font_small)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ----- Send test image -----
def send_test_image(fixture, goal=None):
    img_buffer = generate_test_image(fixture, goal)
    files = {"file": ("test_goal.png", img_buffer, "image/png")}
    embed = {
        "title": "🧪 Test Goal Alert",
        "color": 0x57F287,
        "fields": [
            {"name": "Fixture", "value": f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}", "inline": False}
        ],
        "image": {"url": "attachment://test_goal.png"},
        "footer": {"text": "This is a test – not a live alert"}
    }
    payload = {"embeds": [embed]}
    r = requests.post(DISCORD_WEBHOOK, data={"payload_json": json.dumps(payload)}, files=files)
    if r.status_code == 204:
        print("✅ Test image sent to Discord!")
    else:
        print(f"❌ Discord error: {r.status_code} {r.text}")

# ----- Main test -----
def main():
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
        send_test_image(fixture, goals[0])
        print(f"⚽ Sent goal: {goals[0]['player']['name']} at {goals[0]['time']['elapsed']}'")
    else:
        send_test_image(fixture, None)
        print("⚠️ No goals, but test image sent anyway.")

if __name__ == "__main__":
    main()
