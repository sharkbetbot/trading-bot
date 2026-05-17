import requests
import time
import hashlib
from datetime import datetime

TELEGRAM_TOKEN = "8601521492:AAGx10bdhu3UeEMAfKh0NlrdDUcxbLK85o8"
CHAT_ID = "351609302"
LIVESCORE_KEY = "qgHY8ERxSp9JnkCo"
LIVESCORE_SECRET = "wI6jj9Z2SRUKDtG3Jn1R2ToVixEGSh4p"
ODDS_API_KEY = "e610e4b32d5038e6c54a1316a571cda0"
STAKE_LINK = "https://stake.com/?c=2e44068c9b"
XBET_LINK = "https://1xbet.com"

CRITERES = {"minute_debut_1":38,"minute_fin_1":45,"minute_debut_2":75,"minute_fin_2":90,"da_min":5,"tirs_min":3,"corners_min":1,"pression_min":65,"cote_min":2.40}
historique_stats = {}
alertes_envoyees = set()
cache_odds = {}

ODDS_LEAGUES = ["soccer_epl","soccer_spain_la_liga","soccer_italy_serie_a","soccer_germany_bundesliga","soccer_france_ligue_one","soccer_uefa_champs_league","soccer_uefa_europa_league","soccer_portugal_primeira_liga","soccer_turkey_super_lig","soccer_netherlands_eredivisie","soccer_sweden_allsvenskan","soccer_japan_j_league","soccer_china_superleague","soccer_korea_kleague1","soccer_brazil_campeonato","soccer_mexico_ligamx","soccer_argentina_primera_division","soccer_denmark_superliga","soccer_norway_eliteserien","soccer_austria_bundesliga","soccer_poland_ekstraklasa"]

def get_over_line(hs,as_):
    t=hs+as_
    if t==0: return "Over 0.5"
    elif t==1: return "Over 1.5"
    elif t==2: return "Over 2.5"
    elif t==3: return "Over 3.5"
    else: return "Over "+str(t)+".5"

def make_bar(pct,width=10):
    filled=int(pct/100*width)
    return chr(9608)*filled+chr(9617)*(width-filled)

def envoyer_telegram_texte(msg):
    try:
        r=requests.post("https://api.telegram.org/bot"+TELEGRAM_TOKEN+"/sendMessage",json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"Markdown","disable_web_page_preview":True},timeout=10)
        return r.status_code==200
    except Exception as e:
        print("ERR telegram:"+str(e)); return False

def get_matchs_live():
    try:
        r=requests.get("https://livescore-api.com/api-client/scores/live.json",params={"key":LIVESCORE_KEY,"secret":LIVESCORE_SECRET},timeout=15)
        if r.status_code==200:
            d=r.json()
            if d.get("success"): return d.get("data",{}).get("match",[])
        return []
    except Exception as e:
        print("ERR live:"+str(e)); return []

def get_stats(match_id):
    s={"tirs_home":0,"tirs_away":0,"tirs_cadres_home":0,"tirs_cadres_away":0,"corners_home":0,"corners_away":0,"possession_home":50,"possession_away":50,"da_home":0,"da_away":0,"coups_francs_home":0,"coups_francs_away":0,"cartons_jaunes_home":0,"cartons_jaunes_away":0,"cartons_rouges_home":0,"cartons_rouges_away":0}
    try:
        r=requests.get("https://livescore-api.com/api-client/statistics/matches.json",params={"key":LIVESCORE_KEY,"secret":LIVESCORE_SECRET,"match_id":match_id},timeout=10)
        if r.status_code!=200: return s
        d=r.json()
        if not d.get("success"): return s
        for stat in d.get("data",[]):
            t=stat.get("type","").lower(); h=int(stat.get("home",0) or 0); a=int(stat.get("away",0) or 0)
            if "shots_on_target" in t: s["tirs_cadres_home"]=h; s["tirs_cadres_away"]=a
            elif "attempts_on_goal" in t or "shots" in t: s["tirs_home"]=h; s["tirs_away"]=a
            elif "corner" in t: s["corners_home"]=h; s["corners_away"]=a
            elif "possesion" in t or "possession" in t: s["possession_home"]=h; s["possession_away"]=a
            elif "dangerous" in t: s["da_home"]=h; s["da_away"]=a
            elif "free_kick" in t or "freekick" in t: s["coups_francs_home"]=h; s["coups_francs_away"]=a
            elif "yellow" in t: s["cartons_jaunes_home"]=h; s["cartons_jaunes_away"]=a
            elif "red" in t: s["cartons_rouges_home"]=h; s["cartons_rouges_away"]=a
    except Exception as e: print("ERR stats:"+str(e))
    return s

def get_odds(home,away):
    cle=home+"_"+away
    if cle in cache_odds:
        ts,d=cache_odds[cle]
        if time.time()-ts<60: return d
    for league in ODDS_LEAGUES:
        try:
            r=requests.get("https://api.the-odds-api.com/v4/sports/"+league+"/odds/",params={"apiKey":ODDS_API_KEY,"regions":"eu","markets":"h2h,totals","oddsFormat":"decimal"},timeout=10)
            if r.status_code!=200: continue
            for ev in r.json():
                h=ev.get("home_team","").lower(); a=ev.get("away_team","").lower()
                if home.lower()[:4] in h and away.lower()[:4] in a:
                    res={"home_cote":0,"away_cote":0,"draw_cote":0,"over_cote":0,"favori_home":True}
                    for bk in ev.get("bookmakers",[]):
                        for mk in bk.get("markets",[]):
                            if mk.get("key")=="h2h":
                                out={o["name"]:o["price"] for o in mk.get("outcomes",[])}
                                hc=out.get(ev["home_team"],0); ac=out.get(ev["away_team"],0); dc=out.get("Draw",0)
                                res["home_cote"]=round(hc,2); res["away_cote"]=round(ac,2); res["draw_cote"]=round(dc,2); res["favori_home"]=hc<=ac
                            elif mk.get("key")=="totals":
                                for o in mk.get("outcomes",[]):
                                    if o.get("name")=="Over": res["over_cote"]=round(o.get("price",0),2)
                        if res["home_cote"]>0: break
                    if res["home_cote"]>0:
                        cache_odds[cle]=(time.time(),res); return res
        except: continue
    return {}

def update_historique(m,s):
    t=time.time()
    if m not in historique_stats: historique_stats[m]=[]
    historique_stats[m].append((t,s.copy()))
    historique_stats[m]=[(a,b) for a,b in historique_stats[m] if t-a<=1800]

def get_stats_last_10min(m,s):
    hist=historique_stats.get(m,[])
    snap=hist[0][1] if hist else None
    if snap is None: return s
    skip=["possession_home","possession_away","cartons_jaunes_home","cartons_jaunes_away","cartons_rouges_home","cartons_rouges_away"]
    return {k:max(0,s[k]-snap[k]) if k not in skip else s[k] for k in s}

def calcul_indice_pression(s,fh):
    sd="home" if fh else "away"; op="away" if fh else "home"
    def ratio(a,b): return (a/(a+b))*100 if (a+b)>0 else 50
    return round(ratio(s["tirs_cadres_"+sd],s["tirs_cadres_"+op])*0.25+ratio(s["corners_"+sd],s["corners_"+op])*0.20+s["possession_"+sd]*0.20+ratio(s["da_"+sd],s["da_"+op])*0.35,1)

def generer_message(data,lang="fr"):
    EN=lang=="en"
    home=data.get("home","HOME"); away=data.get("away","AWAY")
    hs=data.get("score_home",0); as_=data.get("score_away",0)
    mi=data.get("minute",80); ligue=data.get("ligue","Football")
    fh=data.get("favori_home",True); situation=data.get("situation","mene")
    s=data.get("stats",{}); s10=data.get("stats_10min",s)
    ip=data.get("indice_pression",65); odds=data.get("odds",{})
    fav_s="home" if fh else "away"; out_s="away" if fh else "home"
    fav_name=home if fh else away
    mt=("1st Half" if EN else "1ere MT") if mi<=45 else ("2nd Half" if EN else "2eme MT")
    c_fav=odds.get("home_cote",0) if fh else odds.get("away_cote",0)
    c_nul=odds.get("draw_cote",0); c_out=odds.get("away_cote",0) if fh else odds.get("home_cote",0)
    c_over=odds.get("over_cote",0) or 1.85
    over_line=get_over_line(hs,as_)
    mr=data.get("minutes_range",str(max(1,mi-10))+"->"+str(mi))
    date_str=datetime.now().strftime("%d/%m/%Y %H:%M")
    yj_h=s.get("cartons_jaunes_home",0); yj_a=s.get("cartons_jaunes_away",0)
    cr_h=s.get("cartons_rouges_home",0); cr_a=s.get("cartons_rouges_away",0)
    p10=int(ip); pos10=int(s10.get("possession_"+fav_s,50))
    shots10=min(100,int(s10.get("tirs_"+fav_s,0)*12))
    da10=min(100,int(s10.get("da_"+fav_s,0)*10))
    mom10=min(100,int(ip)-3)
    xg_h=round(s10.get("tirs_cadres_"+fav_s,0)*0.15,1)
    xg_a=round(s10.get("tirs_cadres_"+out_s,0)*0.15,1)
    best_cote=max(c_fav,round(c_fav+0.05,2))
    def best_str(so,xo):
        if so>=xo: return "Stake *"+str(so)+"* ✅ | 1xBet "+str(xo)
        else: return "Stake "+str(so)+" | 1xBet *"+str(xo)+"* ✅"
    alert_line=("⚠️ *FAVOURITE LOSING*" if EN else "⚠️ *FAVORI MENE*") if situation=="mene" else ("⚠️ *DRAW — FAV PUSHES*" if EN else "⚠️ *MATCH NUL — FAV POUSSE*")
    sep="┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
    msg=(
        ("🦈 *TRADING ALERT — SharkBet*" if EN else "🦈 *ALERTE TRADING — SharkBet*")+"

"
        "🏆 "+ligue+" • "+date_str+"
"
        +sep+"
"
        "🔴 *"+home+"*
"
        "        "+str(hs)+" — "+str(as_)+"
"
        "🔵 *"+away+"*
"
        +alert_line+" — *"+fav_name+"*
"
        "⏱ *"+str(mi)+" MIN — "+mt+"*
"
        "🟡 "+("Yellow" if EN else "Jaunes")+": "+str(yj_h)+"-"+str(yj_a)+"  •  🔴 "+("Red" if EN else "Rouges")+": "+str(cr_h)+"-"+str(cr_a)+"
"
        +sep+"

"
        "⏱ *LAST 10 MIN ("+mr+")*
"
        "`"+("Pressure  " if EN else "Pression  ")+" "+make_bar(p10)+"  "+str(p10)+"%`
"
        "`Possession "+make_bar(pos10)+"  "+str(pos10)+"%`
"
        "`"+("Shots     " if EN else "Tirs      ")+" "+make_bar(shots10)+"   "+str(s10.get("tirs_"+fav_s,0))+" `
"
        "`"+("Dang.Att. " if EN else "Att. Dang.")+" "+make_bar(da10)+"   "+str(s10.get("da_"+fav_s,0))+" `
"
        "`Momentum  "+make_bar(mom10)+"  "+str(mom10)+"%`

"
        "🎯 "+("Shots" if EN else "Tirs")+" *"+str(s10.get("tirs_"+fav_s,0))+"* vs "+str(s10.get("tirs_"+out_s,0))
        +"   📐 Corners *"+str(s10.get("corners_"+fav_s,0))+"* vs "+str(s10.get("corners_"+out_s,0))+"
"
        "⚡ DA *"+str(s10.get("da_"+fav_s,0))+"* vs "+str(s10.get("da_"+out_s,0))
        +"   📉 xG *"+str(xg_h)+"* vs "+str(xg_a)+"
"
        +("_xG = expected goals. Above 0.5 = real danger_" if EN else "_xG = qualite des occasions. Plus de 0.5 = danger_")+"

"
        +sep+"
"
        "💹 *"+("LIVE ODDS" if EN else "COTES LIVE")+"*

"
        "⚽ *"+fav_name+"*   "+best_str(c_fav,round(c_fav+0.05,2))+"
"
        "🤝 *"+("Draw" if EN else "Nul")+"*        "+best_str(c_nul,round(c_nul+0.03,2))+"
"
        "🔵 *"+(away if fh else home)+"*   "+best_str(c_out,round(c_out+0.04,2))+"
"
        "📈 *"+over_line+"*   "+best_str(round(c_over,2),round(c_over+0.03,2))+"

"
        +sep+"
"
        "🟢 _"+("RECOMMENDED TRADE" if EN else "TRADE CONSEILLE")+"_
"
        "*BACK "+fav_name+" @ "+str(best_cote)+"*
"
        +sep+"

"
        "🎯 Stake: "+STAKE_LINK+"
"
        "💎 1xBet: "+XBET_LINK+"
"
        "📊 SofaScore: https://www.sofascore.com"
    )
    return msg

def scanner():
    now_str=datetime.now().strftime("%H:%M:%S")
    print("="*50); print("["+now_str+"] Scan en cours...")
    matchs=get_matchs_live(); print(str(len(matchs))+" matchs live")
    count=0
    for ev in matchs:
        try:
            match_id=ev.get("id")
            if not match_id: continue
            try: mi=int(str(ev.get("time","0")).replace("+","").split("+")[0])
            except: mi=0
            if not(CRITERES["minute_debut_1"]<=mi<=CRITERES["minute_fin_1"] or CRITERES["minute_debut_2"]<=mi<=CRITERES["minute_fin_2"]): continue
            home=ev.get("home_name","?"); away=ev.get("away_name","?")
            try:
                parts=ev.get("score","0 - 0").replace(" ","").split("-"); hs=int(parts[0]); as_=int(parts[1])
            except: hs=as_=0
            ligue=ev.get("competition",{}).get("name","?") if isinstance(ev.get("competition"),dict) else "?"
            stats=get_stats(match_id); update_historique(match_id,stats); stats_10min=get_stats_last_10min(match_id,stats)
            odds=get_odds(home,away)
            if not odds: continue
            favori_home=odds.get("favori_home",True)
            cote_fav=odds.get("home_cote",0) if favori_home else odds.get("away_cote",0)
            if cote_fav<CRITERES["cote_min"]: continue
            favori_mene=(hs<as_) if favori_home else (as_<hs); match_nul=(hs==as_)
            if not favori_mene and not match_nul: continue
            situation="mene" if favori_mene else "nul"
            fav_side="home" if favori_home else "away"
            if stats_10min.get("da_"+fav_side,0)<CRITERES["da_min"]: continue
            if stats_10min.get("tirs_"+fav_side,0)<CRITERES["tirs_min"]: continue
            if stats_10min.get("corners_"+fav_side,0)+stats_10min.get("coups_francs_"+fav_side,0)<CRITERES["corners_min"]: continue
            ip=calcul_indice_pression(stats_10min,favori_home)
            if ip<CRITERES["pression_min"]: continue
            cle=str(match_id)+"_"+str(hs)+"-"+str(as_)+"_"+str(mi//5)
            if cle in alertes_envoyees: continue
            data_alerte={"home":home,"away":away,"score_home":hs,"score_away":as_,"minute":mi,"ligue":ligue,"favori_home":favori_home,"situation":situation,"stats":stats,"stats_10min":stats_10min,"indice_pression":ip,"odds":odds,"minutes_range":str(max(1,mi-10))+"->"+str(mi)}
            for lang in ["fr","en"]:
                envoyer_telegram_texte(generer_message(data_alerte,lang=lang))
                print("Alerte "+lang+": "+home+" vs "+away+" "+str(hs)+"-"+str(as_)+" "+str(mi)+"'")
                time.sleep(1)
            alertes_envoyees.add(cle); count+=1; time.sleep(2)
        except Exception as e: print("ERR:"+str(e))
    print(str(count)+" alerte(s)")

print("BOT SHARKBET DEMARRE!")
envoyer_telegram_texte("🦈 *SharkBet demarre!* Alertes actives.")
envoyer_telegram_texte("🦈 *SharkBet started!* Alerts active.")
scanner()
while True:
    time.sleep(30)
    scanner()
