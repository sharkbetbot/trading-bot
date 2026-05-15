import requests, schedule, time
from datetime import datetime

TELEGRAM_TOKEN = "8601521492:AAGx10bdhu3UeEMAfKh0NlrdDUcxbLK85o8"
CHAT_ID = "351609302"

def envoyer_telegram(msg):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print("OK" if r.status_code == 200 else "ERR:" + r.text)
    except Exception as e:
        print("ERR:" + str(e))

def test_sofascore():
    try:
        r = requests.get(
            "https://api.sofascore.com/api/v1/sport/football/events/live",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=15
        )
        print("SofaScore status: " + str(r.status_code))
        if r.status_code == 200:
            envoyer_telegram("✅ SofaScore fonctionne sur Render!")
        else:
            envoyer_telegram("❌ SofaScore bloqué: " + str(r.status_code))
    except Exception as e:
        envoyer_telegram("❌ Erreur: " + str(e))

print("TEST DEMARRE")
envoyer_telegram("🤖 Test Render démarré...")
test_sofascore()
