import requests
import time
import io
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

TELEGRAM_TOKEN = "8601521492:AAGx10bdhu3UeEMAfKh0NlrdDUcxbLK85o8"
CHAT_ID = "351609302"
LIVESCORE_KEY = "qgHY8ERxSp9JnkCo"
LIVESCORE_SECRET = "wI6jj9Z2SRUKDtG3Jn1R2ToVixEGSh4p"
ODDS_API_KEY = "e610e4b32d5038e6c54a1316a571cda0"
STAKE_LINK = "https://stake.com/?c=2e44068c9b"
LOGO_PATH = "/home/Sharkbet/sharkbet_logo.png"

CRITERES = {
    "minute_debut_1": 38,
    "minute_fin_1": 45,
    "minute_debut_2": 75,
    "minute_fin_2": 90,
    "da_min": 5,
    "tirs_min": 3,
    "corners_min": 1,
    "pression_min": 65,
    "cote_min": 2.40,
    "forme_min": 2,
}

historique_stats = {}
alertes_envoyees = set()
cache_odds = {}
cache_standings = {}
cache_form = {}

ODDS_LEAGUES = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_portugal_primeira_liga", "soccer_turkey_super_lig",
    "soccer_netherlands_eredivisie", "soccer_sweden_allsvenskan",
    "soccer_japan_j_league", "soccer_china_superleague",
    "soccer_korea_kleague1", "soccer_brazil_campeonato",
    "soccer_mexico_ligamx", "soccer_argentina_primera_division",
    "soccer_denmark_superliga", "soccer_norway_eliteserien",
    "soccer_austria_bundesliga", "soccer_poland_ekstraklasa"
]
def envoyer_telegram_texte(msg):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print("ERR telegram: " + str(e))
        return False

def envoyer_telegram_image(img_bytes, caption=""):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendPhoto"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": ("alert.png", img_bytes, "image/png")}, timeout=30)
        return r.status_code == 200
    except Exception as e:
        print("ERR telegram image: " + str(e))
        return False

def get_matchs_live():
    try:
        r = requests.get("https://livescore-api.com/api-client/scores/live.json", params={"key": LIVESCORE_KEY, "secret": LIVESCORE_SECRET}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                return data.get("data", {}).get("match", [])
        return []
    except Exception as e:
        print("ERR livescores: " + str(e))
        return []

def get_stats(match_id):
    s = {"tirs_home": 0, "tirs_away": 0, "tirs_cadres_home": 0, "tirs_cadres_away": 0, "corners_home": 0, "corners_away": 0, "possession_home": 50, "possession_away": 50, "da_home": 0, "da_away": 0, "coups_francs_home": 0, "coups_francs_away": 0, "cartons_jaunes_home": 0, "cartons_jaunes_away": 0, "cartons_rouges_home": 0, "cartons_rouges_away": 0}
    try:
        r = requests.get("https://livescore-api.com/api-client/statistics/matches.json", params={"key": LIVESCORE_KEY, "secret": LIVESCORE_SECRET, "match_id": match_id}, timeout=10)
        if r.status_code != 200:
            return s
        data = r.json()
        if not data.get("success"):
            return s
        for stat in data.get("data", []):
            t = stat.get("type", "").lower()
            h = int(stat.get("home", 0) or 0)
            a = int(stat.get("away", 0) or 0)
            if "shots_on_target" in t:
                s["tirs_cadres_home"] = h
                s["tirs_cadres_away"] = a
            elif "attempts_on_goal" in t or "shots" in t:
                s["tirs_home"] = h
                s["tirs_away"] = a
            elif "corner" in t:
                s["corners_home"] = h
                s["corners_away"] = a
            elif "possesion" in t or "possession" in t:
                s["possession_home"] = h
                s["possession_away"] = a
            elif "dangerous" in t:
                s["da_home"] = h
                s["da_away"] = a
            elif "free_kick" in t or "freekick" in t:
                s["coups_francs_home"] = h
                s["coups_francs_away"] = a
            elif "yellow" in t:
                s["cartons_jaunes_home"] = h
                s["cartons_jaunes_away"] = a
            elif "red" in t:
                s["cartons_rouges_home"] = h
                s["cartons_rouges_away"] = a
    except Exception as e:
        print("ERR stats: " + str(e))
    return s

def get_odds(home, away):
    cle = home + "_" + away
    if cle in cache_odds:
        ts, d = cache_odds[cle]
        if time.time() - ts < 60:
            return d
    for league in ODDS_LEAGUES:
        try:
            r = requests.get("https://api.the-odds-api.com/v4/sports/" + league + "/odds/", params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}, timeout=10)
            if r.status_code != 200:
                continue
            for ev in r.json():
                h = ev.get("home_team", "").lower()
                a = ev.get("away_team", "").lower()
                if home.lower()[:4] in h and away.lower()[:4] in a:
                    for bk in ev.get("bookmakers", []):
                        for mk in bk.get("markets", []):
                            if mk.get("key") != "h2h":
                                continue
                            out = {o["name"]: o["price"] for o in mk.get("outcomes", [])}
                            hc = out.get(ev["home_team"], 0)
                            ac = out.get(ev["away_team"], 0)
                            dc = out.get("Draw", 0)
                            res = {"home_cote": round(hc, 2), "away_cote": round(ac, 2), "draw_cote": round(dc, 2), "favori_home": hc <= ac, "bookmaker": bk.get("title", "")}
                            cache_odds[cle] = (time.time(), res)
                            return res
        except:
            continue
    return {}
def scanner():
    now_str = datetime.now().strftime("%H:%M:%S")
    print("=" * 50)
    print("[" + now_str + "] Scan en cours...")
    matchs = get_matchs_live()
    print(str(len(matchs)) + " matchs live")
    count = 0
    for ev in matchs:
        try:
            match_id = ev.get("id")
            if not match_id:
                continue
            minute_raw = ev.get("time", "0")
            try:
                mi = int(str(minute_raw).replace("+", "").split("+")[0])
            except:
                mi = 0
            in_window = (CRITERES["minute_debut_1"] <= mi <= CRITERES["minute_fin_1"] or CRITERES["minute_debut_2"] <= mi <= CRITERES["minute_fin_2"])
            if not in_window:
                continue
            home = ev.get("home_name", "?")
            away = ev.get("away_name", "?")
            score_raw = ev.get("score", "0 - 0")
            try:
                parts = score_raw.replace(" ", "").split("-")
                hs = int(parts[0])
                as_ = int(parts[1])
            except:
                hs, as_ = 0, 0
            ligue = ev.get("competition", {}).get("name", "?") if isinstance(ev.get("competition"), dict) else "?"
            stats = get_stats(match_id)
            update_historique(match_id, stats)
            stats_10min = get_stats_last_10min(match_id, stats)
            odds = get_odds(home, away)
            if not odds:
                continue
            favori_home = odds.get("favori_home", True)
            cote_fav = odds.get("home_cote", 0) if favori_home else odds.get("away_cote", 0)
            if cote_fav < CRITERES["cote_min"]:
                continue
            favori_mene = (hs < as_) if favori_home else (as_ < hs)
            match_nul = (hs == as_)
            if not favori_mene and not match_nul:
                continue
            situation = "mene" if favori_mene else "nul"
            fav_side = "home" if favori_home else "away"
            out_side = "away" if favori_home else "home"
            da_fav = stats_10min.get("da_" + fav_side, 0)
            tirs_fav = stats_10min.get("tirs_" + fav_side, 0)
            corners_fav = stats_10min.get("corners_" + fav_side, 0)
            coups_francs_fav = stats_10min.get("coups_francs_" + fav_side, 0)
            if da_fav < CRITERES["da_min"]:
                continue
            if tirs_fav < CRITERES["tirs_min"]:
                continue
            if (corners_fav + coups_francs_fav) < CRITERES["corners_min"]:
                continue
            ip = calcul_indice_pression(stats_10min, favori_home)
            if ip < CRITERES["pression_min"]:
                continue
            cle = str(match_id) + "_" + str(hs) + "-" + str(as_) + "_" + str(mi // 5)
            if cle in alertes_envoyees:
                continue
            favori_name = home if favori_home else away
            cote_nul = odds.get("draw_cote", 0)
            cote_out = odds.get("away_cote", 0) if favori_home else odds.get("home_cote", 0)
            minutes_range = str(max(1, mi - 10)) + "' -> " + str(mi) + "'"
            if situation == "mene":
                alerte_fr = "FAVORI MENE - " + favori_name + " pousse fort"
                alerte_en = "FAVOURITE LOSING - " + favori_name + " pushing hard"
            else:
                alerte_fr = "MATCH NUL - " + favori_name + " domine"
                alerte_en = "DRAW - " + favori_name + " dominating"
            msg_fr = (alerte_fr + "\n" + ligue + "\n" + home + " " + str(hs) + "-" + str(as_) + " " + away + " | " + str(mi) + "'\n" + "Pression: " + str(ip) + "/100 | DA: " + str(da_fav) + " | Tirs: " + str(tirs_fav) + "\n" + "BACK " + favori_name + " @ " + str(cote_fav) + "\nStake: " + STAKE_LINK)
            msg_en = (alerte_en + "\n" + ligue + "\n" + home + " " + str(hs) + "-" + str(as_) + " " + away + " | " + str(mi) + "'\n" + "Pressure: " + str(ip) + "/100 | DA: " + str(da_fav) + " | Shots: " + str(tirs_fav) + "\n" + "BACK " + favori_name + " @ " + str(cote_fav) + "\nStake: " + STAKE_LINK)
            envoyer_telegram_texte(msg_fr)
            time.sleep(1)
            envoyer_telegram_texte(msg_en)
            alertes_envoyees.add(cle)
            count += 1
            print("Alerte: " + home + " vs " + away + " " + str(hs) + "-" + str(as_) + " " + str(mi) + "'")
            time.sleep(2)
        except Exception as e:
            print("ERR: " + str(e))
    print(str(count) + " alerte(s)")

print("BOT SHARKBET DEMARRE!")
envoyer_telegram_texte("Bot SharkBet demarre! Live-score API actif. Alertes 38-45 min + 75-90 min.")
envoyer_telegram_texte("SharkBet Bot Started! Live-score API active. Alerts 38-45 min + 75-90 min.")
scanner()
while True:
    time.sleep(30)
    scanner()
