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
    "minute_debut_1": 38, "minute_fin_1": 45,
    "minute_debut_2": 75, "minute_fin_2": 90,
    "da_min": 5, "tirs_min": 3, "corners_min": 1,
    "pression_min": 65, "cote_min": 2.40, "forme_min": 2,
}

historique_stats = {}
alertes_envoyees = set()
cache_odds = {}

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
        print("ERR image: " + str(e))
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
        print("ERR live: " + str(e))
        return []


def get_stats(match_id):
    s = {
        "tirs_home": 0, "tirs_away": 0,
        "tirs_cadres_home": 0, "tirs_cadres_away": 0,
        "corners_home": 0, "corners_away": 0,
        "possession_home": 50, "possession_away": 50,
        "da_home": 0, "da_away": 0,
        "coups_francs_home": 0, "coups_francs_away": 0,
        "cartons_jaunes_home": 0, "cartons_jaunes_away": 0,
        "cartons_rouges_home": 0, "cartons_rouges_away": 0
    }
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
                            res = {"home_cote": round(hc, 2), "away_cote": round(ac, 2), "draw_cote": round(dc, 2), "favori_home": hc <= ac}
                            cache_odds[cle] = (time.time(), res)
                            return res
        except Exception:
            continue
    return {}


def update_historique(m, s):
    t = time.time()
    if m not in historique_stats:
        historique_stats[m] = []
    historique_stats[m].append((t, s.copy()))
    historique_stats[m] = [(a, b) for a, b in historique_stats[m] if t - a <= 1800]


def get_stats_last_10min(m, s):
    def creer_image_alerte(data, lang="fr"):
    W, H = 800, 1200
    img = Image.new("RGB", (W, H), "#f0f4f8")
    draw = ImageDraw.Draw(img)
    try:
        fb = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        fn = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f22 = ImageFont.truetype(fb, 22)
        f18 = ImageFont.truetype(fb, 18)
        f16 = ImageFont.truetype(fn, 16)
        f14 = ImageFont.truetype(fb, 14)
        f12 = ImageFont.truetype(fn, 12)
        f11 = ImageFont.truetype(fn, 11)
    except Exception:
        f22 = f18 = f16 = f14 = f12 = f11 = ImageFont.load_default()

    if lang == "en":
        txt = {
            "alert": "TRADING ALERT", "favori_mene": "FAVOURITE LOSING",
            "match_nul": "DRAW", "last10": "LAST 10 MIN",
            "key_stats": "KEY STATS", "live_odds": "LIVE ODDS",
            "trade": "RECOMMENDED TRADE", "back": "BACK",
            "best_odds": "Best odds", "secondhalf": "2nd Half",
            "halftime": "1st Half", "pression": "Pressure Index",
            "possession": "Possession", "shots": "Shots",
            "da": "Dangerous Attacks", "momentum": "Momentum",
            "total_shots": "Total Shots", "corners": "Corners",
            "keypasses": "Key Passes", "attacks": "Attacks",
            "xg": "xG (Expected Goals)",
            "xg_desc": "Quality of chances. Above 0.5 = real danger",
            "draw": "Draw", "yellow": "Yellow Cards", "red": "Red Cards",
            "sofascore": "View on SofaScore"
        }
    else:
        txt = {
            "alert": "ALERTE TRADING", "favori_mene": "FAVORI MENE",
            "match_nul": "MATCH NUL", "last10": "LAST 10 MIN",
            "key_stats": "CHIFFRES CLES", "live_odds": "COTES LIVE",
            "trade": "TRADE CONSEILLE", "back": "BACK",
            "best_odds": "Meilleure cote", "secondhalf": "2eme MT",
            "halftime": "1ere MT", "pression": "Indice Pression",
            "possession": "Possession", "shots": "Tirs",
            "da": "Att. Dang.", "momentum": "Momentum",
            "total_shots": "Tirs total", "corners": "Corners",
            "keypasses": "Passes cles", "attacks": "Attaques",
            "xg": "xG (buts attendus)",
            "xg_desc": "Qualite des occasions. Au-dessus de 0.5 = danger",
            "draw": "Nul", "yellow": "Cartons jaunes", "red": "Cartons rouges",
            "sofascore": "Voir sur SofaScore"
        }

    def rbox(x1, y1, x2, y2, fc, ec=None, lw=0, r=8):
        draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fc, outline=ec, width=lw)

    def ctext(text, y, font, color, x1=0, x2=W):
        bb = draw.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
        draw.text(((x2 - x1 - tw) // 2 + x1, y), text, font=font, fill=color)

    date_str = datetime.now().strftime("%d/%m/%Y %H:%M") if lang == "fr" else datetime.now().strftime("%m/%d/%Y %H:%M")
    home = data.get("home", "HOME")
    away = data.get("away", "AWAY")
    hs = data.get("score_home", 0)
    as_ = data.get("score_away", 0)
    mi = data.get("minute", 80)
    ligue = data.get("ligue", "Football")
    favori_home = data.get("favori_home", True)
    situation = data.get("situation", "mene")
    s = data.get("stats", {})
    s10 = data.get("stats_10min", s)
    ip = data.get("indice_pression", 65)
    odds = data.get("odds", {})
    fav_side = "home" if favori_home else "away"
    out_side = "away" if favori_home else "home"
    favori_name = home if favori_home else away
    mi_temps = txt["halftime"] if mi <= 45 else txt["secondhalf"]
    cote_fav = odds.get("home_cote", 0) if favori_home else odds.get("away_cote", 0)
    cote_nul = odds.get("draw_cote", 0)
    cote_out = odds.get("away_cote", 0) if favori_home else odds.get("home_cote", 0)
    minutes_range = data.get("minutes_range", str(max(1, mi - 10)) + "' -> " + str(mi) + "'")

    y = 0
    rbox(0, y, W, 85, "#1e3a5f")
    try:
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH).convert("RGBA").resize((65, 65))
            img.paste(logo, (15, 10), logo)
    except Exception:
        pass
    draw.text((95, 18), txt["alert"] + " - SharkBet", font=f22, fill="white")
    draw.text((95, 50), ligue + "   |   " + date_str, font=f16, fill="#94a3b8")
    y = 95

    rbox(10, y, W - 10, y + 115, "#f8fafc", ec="#e2e8f0", lw=1)
    draw.text((25, y + 12), home[:14], font=f18, fill="#dc2626")
    draw.text((25, y + 38), "Favori" if lang == "fr" else "Favourite", font=f12, fill="#dc2626")
    aw_w = draw.textbbox((0, 0), away[:14], font=f18)[2]
    draw.text((W - 25 - aw_w, y + 12), away[:14], font=f18, fill="#2563eb")
    losing_txt = "Mene" if lang == "fr" else "Losing"
    lo_w = draw.textbbox((0, 0), losing_txt, font=f12)[2]
    draw.text((W - 25 - lo_w, y + 38), losing_txt, font=f12, fill="#2563eb")
    rbox(W // 2 - 65, y + 10, W // 2 + 65, y + 70, "#1e3a5f", r=10)
    ctext(str(hs) + " - " + str(as_), y + 22, f22, "white")
    rbox(W // 2 - 60, y + 73, W // 2 + 60, y + 98, "#f59e0b", r=12)
    ctext(str(mi) + "'  -  " + mi_temps, y + 77, f14, "white")
    y += 125

    alerte_txt = txt["favori_mene"] + " - " + favori_name if situation == "mene" else txt["match_nul"] + " - " + favori_name
    rbox(10, y, W - 10, y + 38, "#fef3c7", ec="#f59e0b", lw=2)
    ctext(alerte_txt, y + 10, f14, "#78350f")
    y += 48

    rbox(10, y, W // 2 - 5, y + 38, "#fffbeb", ec="#f59e0b", lw=1)
    draw.text((20, y + 10), txt["yellow"] + ": " + str(s.get("cartons_jaunes_home", 0)) + " vs " + str(s.get("cartons_jaunes_away", 0)), font=f14, fill="#92400e")
    cr_h = s.get("cartons_rouges_home", 0)
    cr_a = s.get("cartons_rouges_away", 0)
    cr_color = "#dc2626" if (cr_h + cr_a) > 0 else "#166534"
    cr_bg = "#fef2f2" if (cr_h + cr_a) > 0 else "#ecfdf5"
    rbox(W // 2 + 5, y, W - 10, y + 38, cr_bg, ec=cr_color, lw=1)
    draw.text((W // 2 + 15, y + 10), txt["red"] + ": " + str(cr_h) + " vs " + str(cr_a), font=f14, fill=cr_color)
    y += 48

    rbox(10, y, W - 10, y + 28, "#1e3a5f", r=6)
    ctext(txt["last10"] + "  (" + minutes_range + ")", y + 6, f14, "white")
    y += 36

    draw.text((25, y + 2), home[:10], font=f12, fill="#dc2626")
    aw2_w = draw.textbbox((0, 0), away[:10], font=f12)[2]
    draw.text((W - 25 - aw2_w, y + 2), away[:10], font=f12, fill="#2563eb")
    y += 18

    bars = [
        (txt["pression"], ip, "#dc2626"),
        (txt["possession"], s10.get("possession_" + fav_side, 50), "#ea580c"),
        (txt["shots"], min(100, s10.get("tirs_" + fav_side, 0) * 12), "#d97706"),
        (txt["da"], min(100, s10.get("da_" + fav_side, 0) * 10), "#db2777"),
        (txt["momentum"], min(100, ip - 3), "#7c3aed"),
    ]

    for label, pct, color in bars:
        rbox(10, y, W - 10, y + 32, "#ffffff")
        draw.text((15, y + 8), label, font=f12, fill="#475569")
        bx, bw, bh = 200, 560, 18
        by = y + 7
        rbox(bx, by, bx + bw, by + bh, "#e5e7eb", r=4)
        fw = int(bw * pct / 100)
        if fw > 0:
            rbox(bx, by, bx + fw, by + bh, color, r=4)
        pct_away = max(0, 100 - int(pct))
        if fw > 25:
            draw.text((bx + 4, by + 2), str(int(pct)) + "%", font=f11, fill="white")
        if (bw - fw) > 25:
            draw.text((bx + fw + 4, by + 2), str(pct_away) + "%", font=f11, fill="#6b7280")
        y += 36

    rbox(10, y, W - 10, y + 28, "#1e3a5f", r=6)
    ctext(txt["key_stats"] + "  (" + txt["last10"] + ")", y + 6, f14, "white")
    y += 36

    col1, col2, col3 = 20, 500, 660
    rbox(10, y, W - 10, y + 24, "#f8fafc")
    draw.text((col1, y + 4), "Stat", font=f12, fill="#6b7280")
    draw.text((col2, y + 4), home[:6], font=f14, fill="#dc2626")
    draw.text((col3, y + 4), away[:6], font=f14, fill="#2563eb")
    y += 26

    key_stats_list = [
        (txt["total_shots"], s10.get("tirs_" + fav_side, 0), s10.get("tirs_" + out_side, 0)),
        (txt["corners"], s10.get("corners_" + fav_side, 0), s10.get("corners_" + out_side, 0)),
        (txt["da"], s10.get("da_" + fav_side, 0), s10.get("da_" + out_side, 0)),
        (txt["attacks"], s10.get("coups_francs_" + fav_side, 0) + s10.get("da_" + fav_side, 0), s10.get("da_" + out_side, 0)),
        (txt["xg"], round(s10.get("tirs_cadres_" + fav_side, 0) * 0.15, 1), round(s10.get("tirs_cadres_" + out_side, 0) * 0.15, 1)),
    ]

    for i, (label, hv, av) in enumerate(key_stats_list):
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        extra = 12 if label == txt["xg"] else 0
        rbox(10, y, W - 10, y + 30 + extra, bg)
        draw.text((col1, y + 7), label, font=f12, fill="#374151")
        draw.text((col2, y + 5), str(hv), font=f16, fill="#dc2626")
        draw.text((col3, y + 5), str(av), font=f16, fill="#2563eb")
        if label == txt["xg"]:
            draw.text((col1, y + 22), txt["xg_desc"], font=f11, fill="#9ca3af")
        y += 32 + extra

    rbox(10, y, W - 10, y + 28, "#1e3a5f", r=6)
    ctext(txt["live_odds"], y + 6, f14, "white")
    y += 36

    rbox(10, y, W - 10, y + 24, "#f8fafc")
    draw.text((20, y + 4), "Market" if lang == "en" else "Marche", font=f12, fill="#6b7280")
    draw.text((420, y + 4), "Stake", font=f14, fill="#059669")
    draw.text((580, y + 4), "1xBet", font=f14, fill="#1a56db")
    y += 26

    odds_rows = [
        (favori_name[:14], cote_fav, round(cote_fav + 0.05, 2)),
        (txt["draw"], cote_nul, round(cote_nul + 0.03, 2)),
        ((away if favori_home else home)[:14], cote_out, round(cote_out + 0.04, 2)),
    ]

    for i, (label, s_odd, x_odd) in enumerate(odds_rows):
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        rbox(10, y, W - 10, y + 30, bg)
        draw.text((20, y + 7), label, font=f12, fill="#374151")
        best = max(s_odd, x_odd)
        draw.text((420, y + 5), str(s_odd), font=f16, fill="#16a34a" if s_odd >= best else "#374151")
        draw.text((580, y + 5), str(x_odd), font=f16, fill="#16a34a" if x_odd >= best else "#374151")
        y += 32

    y += 5
    rbox(0, y, W, y + 130, "#14532d")
    ctext(txt["trade"], y + 10, f14, "#86efac")
    best_cote = max(cote_fav, round(cote_fav + 0.05, 2))
    ctext(txt["back"] + " " + favori_name + " @ " + str(best_cote), y + 32, f22, "white")
    btn_y = y + 65
    rbox(20, btn_y, 370, btn_y + 48, "#059669", ec="#34d399", lw=2, r=10)
    draw.text((35, btn_y + 8), "Stake  @  " + str(cote_fav), font=f16, fill="white")
    draw.text((35, btn_y + 28), txt["best_odds"], font=f12, fill="#86efac")
    rbox(W - 370, btn_y, W - 20, btn_y + 48, "#1a56db", ec="#60a5fa", lw=2, r=10)
    draw.text((W - 355, btn_y + 8), "1xBet  @  " + str(round(cote_fav + 0.05, 2)), font=f16, fill="white")
    ctext(txt["sofascore"], y + 118, f12, "#86efac")

    buf = io.BytesIO()
    final_h = min(H, y + 130)
    img = img.crop((0, 0, W, final_h))
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


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
            try:
                mi = int(str(ev.get("time", "0")).replace("+", "").split("+")[0])
            except Exception:
                mi = 0
            in_window = (
                CRITERES["minute_debut_1"] <= mi <= CRITERES["minute_fin_1"] or
                CRITERES["minute_debut_2"] <= mi <= CRITERES["minute_fin_2"]
            )
            if not in_window:
                continue
            home = ev.get("home_name", "?")
            away = ev.get("away_name", "?")
            try:
                parts = ev.get("score", "0 - 0").replace(" ", "").split("-")
                hs = int(parts[0])
                as_ = int(parts[1])
            except Exception:
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
            coups_fav = stats_10min.get("coups_francs_" + fav_side, 0)
            if da_fav < CRITERES["da_min"]:
                continue
            if tirs_fav < CRITERES["tirs_min"]:
                continue
            if (corners_fav + coups_fav) < CRITERES["corners_min"]:
                continue
            ip = calcul_indice_pression(stats_10min, favori_home)
            if ip < CRITERES["pression_min"]:
                continue
            cle = str(match_id) + "_" + str(hs) + "-" + str(as_) + "_" + str(mi // 5)
            if cle in alertes_envoyees:
                continue
            minutes_range = str(max(1, mi - 10)) + "' -> " + str(mi) + "'"
            data_alerte = {
                "home": home, "away": away,
                "home_logo": None, "away_logo": None,
                "score_home": hs, "score_away": as_,
                "minute": mi, "ligue": ligue,
                "favori_home": favori_home, "situation": situation,
                "stats": stats, "stats_10min": stats_10min,
                "indice_pression": ip, "odds": odds,
                "minutes_range": minutes_range
            }
            for lang in ["fr", "en"]:
                try:
                    img_bytes = creer_image_alerte(data_alerte, lang=lang)
                    envoyer_telegram_image(img_bytes)
                    print("Alerte " + lang + ": " + home + " vs " + away + " " + str(hs) + "-" + str(as_) + " " + str(mi) + "'")
                except Exception as e:
                    print("ERR image " + lang + ": " + str(e))
                    envoyer_telegram_texte("TRADE: BACK " + (home if favori_home else away) + " @ " + str(cote_fav) + "\n" + home + " " + str(hs) + "-" + str(as_) + " " + away + " " + str(mi) + "'\n" + STAKE_LINK)
                time.sleep(1)
            alertes_envoyees.add(cle)
            count += 1
            time.sleep(2)
        except Exception as e:
            print("ERR: " + str(e))
    print(str(count) + " alerte(s)")


print("BOT SHARKBET DEMARRE!")
envoyer_telegram_texte("Bot SharkBet demarre! Alertes visuelles actives.")
envoyer_telegram_texte("SharkBet Bot Started! Visual alerts active.")
scanner()
while True:
    time.sleep(30)
    scanner()
hist = historique_stats.get(m, [])
    snap = hist[0][1] if hist else None
    if snap is None:
        return s
    skip = ["possession_home", "possession_away", "cartons_jaunes_home", "cartons_jaunes_away", "cartons_rouges_home", "cartons_rouges_away"]
    return {k: max(0, s[k] - snap[k]) if k not in skip else s[k] for k in s}


def calcul_indice_pression(s, fh):
    sd = "home" if fh else "away"
    op = "away" if fh else "home"

    def ratio(a, b):
        return (a / (a + b)) * 100 if (a + b) > 0 else 50

    return round(
        ratio(s["tirs_cadres_" + sd], s["tirs_cadres_" + op]) * 0.25 +
        ratio(s["corners_" + sd], s["corners_" + op]) * 0.20 +
        s["possession_" + sd] * 0.20 +
        ratio(s["da_" + sd], s["da_" + op]) * 0.35, 1
    )
