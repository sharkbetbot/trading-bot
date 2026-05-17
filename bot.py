
import requests, time, io, os, subprocess, tempfile, hashlib
from datetime import datetime

TELEGRAM_TOKEN = "8601521492:AAGx10bdhu3UeEMAfKh0NlrdDUcxbLK85o8"
CHAT_ID = "351609302"
LIVESCORE_KEY = "qgHY8ERxSp9JnkCo"
LIVESCORE_SECRET = "wI6jj9Z2SRUKDtG3Jn1R2ToVixEGSh4p"
ODDS_API_KEY = "e610e4b32d5038e6c54a1316a571cda0"
STAKE_LINK = "https://stake.com/?c=2e44068c9b"
XBET_LINK = "https://1xbet.com"
LOGO_PATH = "/home/Sharkbet/sharkbet_logo.png"

CRITERES = {"minute_debut_1":38,"minute_fin_1":45,"minute_debut_2":75,"minute_fin_2":90,"da_min":5,"tirs_min":3,"corners_min":1,"pression_min":65,"cote_min":2.40,"forme_min":2}
historique_stats = {}
alertes_envoyees = set()
cache_odds = {}

ODDS_LEAGUES = ["soccer_epl","soccer_spain_la_liga","soccer_italy_serie_a","soccer_germany_bundesliga","soccer_france_ligue_one","soccer_uefa_champs_league","soccer_uefa_europa_league","soccer_portugal_primeira_liga","soccer_turkey_super_lig","soccer_netherlands_eredivisie","soccer_sweden_allsvenskan","soccer_japan_j_league","soccer_china_superleague","soccer_korea_kleague1","soccer_brazil_campeonato","soccer_mexico_ligamx","soccer_argentina_primera_division","soccer_denmark_superliga","soccer_norway_eliteserien","soccer_austria_bundesliga","soccer_poland_ekstraklasa"]

TEAM_COLORS = {"arsenal":("#EF0107","#9C0000","AFC"),"chelsea":("#034694","#DBA111","CFC"),"manchester city":("#6CABDD","#1c2f5e","MCI"),"manchester united":("#DA291C","#FBE122","MUN"),"liverpool":("#C8102E","#00B2A9","LIV"),"tottenham":("#132257","#FFFFFF","TOT"),"barcelona":("#A50044","#004D98","FCB"),"real madrid":("#FEBE10","#FFFFFF","RMA"),"juventus":("#000000","#FFFFFF","JUV"),"psg":("#004170","#DA291C","PSG"),"paris":("#004170","#DA291C","PSG"),"bayern":("#DC052D","#FFFFFF","BAY"),"dortmund":("#FDE100","#000000","BVB"),"inter":("#003DA5","#000000","INT"),"ac milan":("#FB090B","#000000","MIL"),"atletico":("#CE3524","#272E61","ATL"),"nottm":("#DD0000","#FFFFFF","NFO"),"forest":("#DD0000","#FFFFFF","NFO"),"newcastle":("#241F20","#41B6E6","NEW"),"west ham":("#7A263A","#1BB1E7","WHU"),"aston":("#95BFE5","#670E36","AVL"),"benfica":("#CC0000","#FFFFFF","BEN"),"porto":("#003087","#FFFFFF","POR"),"sevilla":("#D40000","#FFFFFF","SEV"),"roma":("#8E0B16","#F5C518","ROM"),"napoli":("#12A0D7","#FFFFFF","NAP"),"celtic":("#16A34A","#FFFFFF","CEL"),"rangers":("#003380","#FFFFFF","RAN")}

def get_team_info(name):
    nl = name.lower()
    for k,v in TEAM_COLORS.items():
        if k in nl: return v
    h = int(hashlib.md5(name.encode()).hexdigest()[:6],16)
    parts = name.split()
    ini = (parts[0][0]+(parts[-1][0] if len(parts)>1 else name[1])).upper()
    return (f"#{(h>>16)&0xFF:02x}{(h>>8)&0xFF:02x}{h&0xFF:02x}","#FFFFFF",ini)

def get_over_line(hs,as_):
    t=hs+as_
    return "Over "+str(t)+".5" if t>0 else "Over 0.5"

def get_logo_b64():
    try:
        import base64
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH,"rb") as f: return base64.b64encode(f.read()).decode()
    except: pass
    return ""

def envoyer_telegram_texte(msg):
    try:
        r=requests.post("https://api.telegram.org/bot"+TELEGRAM_TOKEN+"/sendMessage",json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML","disable_web_page_preview":True},timeout=10)
        return r.status_code==200
    except Exception as e:
        print("ERR telegram:"+str(e)); return False

def envoyer_telegram_image(img_bytes,caption=""):
    try:
        r=requests.post("https://api.telegram.org/bot"+TELEGRAM_TOKEN+"/sendPhoto",data={"chat_id":CHAT_ID,"caption":caption},files={"photo":("alert.png",img_bytes,"image/png")},timeout=30)
        return r.status_code==200
    except Exception as e:
        print("ERR image:"+str(e)); return False

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

def generer_html_alerte(data,lang="fr"):
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
    mr=data.get("minutes_range",str(max(1,mi-10))+"-> "+str(mi))
    date_str=datetime.now().strftime("%d/%m/%Y %H:%M")
    c1h,c2h,inh=get_team_info(home); c1a,c2a,ina=get_team_info(away)
    logo_b64=get_logo_b64()
    logo_tag='<img src="data:image/png;base64,'+logo_b64+'" class="logo"/>' if logo_b64 else '<div class="logo">SB</div>'
    yj_h=s.get("cartons_jaunes_home",0); yj_a=s.get("cartons_jaunes_away",0)
    cr_h=s.get("cartons_rouges_home",0); cr_a=s.get("cartons_rouges_away",0)
    cr_color="#dc2626" if (cr_h+cr_a)>0 else "#16a34a"
    alert_icon="&#9917;" if situation=="mene" else "&#129309;"
    alert_label=("FAVOURITE LOSING" if EN else "FAVORI MENE") if situation=="mene" else ("DRAW" if EN else "MATCH NUL")
    best_cote=max(c_fav,round(c_fav+0.05,2))
    title_txt="TRADING ALERT" if EN else "ALERTE TRADING"
    trade_txt="RECOMMENDED TRADE" if EN else "TRADE CONSEILLE"
    sofa_txt="Live stats on SofaScore" if EN else "Stats live sur SofaScore"
    fav_lbl="Favourite" if EN else "Favori"
    los_lbl="Losing" if EN else "Mene"

    def bar(label,pct,color):
        pct=int(pct); pa=max(0,100-pct)
        return f'<div class="bar-item"><div class="bar-label">{label}</div><div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color};"></div><span class="bar-pct-home">{pct}%</span><span class="bar-pct-away">{pa}%</span></div></div>'

    def ksrow(lbl,hv,av,sub="",even=True):
        bg="#13161d" if even else "#111318"
        sub_h=f'<div class="ks-sub">{sub}</div>' if sub else ""
        return f'<div class="ks-row" style="background:{bg};"><div class="ks-label">{lbl}{sub_h}</div><div class="ks-home" style="color:{c1h};">{hv}</div><div class="ks-away" style="color:{c1a};">{av}</div></div>'

    def oddsrow(icon,lbl,so,xo,even=True):
        bg="#13161d" if even else "#111318"
        best=max(so,xo)
        sc="#10b981" if so>=best else "#6b7280"
        xc="#10b981" if xo>=best else "#6b7280"
        return f'<div class="odds-row" style="background:{bg};"><div class="odds-market">{icon} {lbl}</div><div class="odds-val" style="color:{sc};">{so}</div><div class="odds-val" style="color:{xc};">{xo}</div></div>'

    xg_h=round(s10.get("tirs_cadres_"+fav_s,0)*0.15,1)
    xg_a=round(s10.get("tirs_cadres_"+out_s,0)*0.15,1)
    bars_html=(bar("Indice Pression" if not EN else "Pressure",ip,"#dc2626")+bar("Possession",s10.get("possession_"+fav_s,50),"#ea580c")+bar("Tirs" if not EN else "Shots",min(100,s10.get("tirs_"+fav_s,0)*12),"#d97706")+bar("Att. Dang." if not EN else "Dang. Attacks",min(100,s10.get("da_"+fav_s,0)*10),"#db2777")+bar("Momentum",min(100,int(ip)-3),"#7c3aed"))
    ks_html=(ksrow("Tirs total" if not EN else "Total Shots",s10.get("tirs_"+fav_s,0),s10.get("tirs_"+out_s,0),even=True)+ksrow("Corners",s10.get("corners_"+fav_s,0),s10.get("corners_"+out_s,0),even=False)+ksrow("Att. Dang.",s10.get("da_"+fav_s,0),s10.get("da_"+out_s,0),even=True)+ksrow("Attaques" if not EN else "Attacks",s10.get("coups_francs_"+fav_s,0)+s10.get("da_"+fav_s,0),s10.get("da_"+out_s,0),even=False)+ksrow("xG","%.1f"%xg_h,"%.1f"%xg_a,sub="Buts attendus. >0.5=danger" if not EN else "Exp. goals. >0.5=danger",even=True))
    odds_html=(oddsrow("&#9917;",fav_name[:16],c_fav,round(c_fav+0.05,2),even=True)+oddsrow("&#129309;","Nul" if not EN else "Draw",c_nul,round(c_nul+0.03,2),even=False)+oddsrow("&#128309;",(away if fh else home)[:16],c_out,round(c_out+0.04,2),even=True)+oddsrow("&#128200;",over_line+" - 1 but de plus" if not EN else over_line+" - 1 more goal",round(c_over,2),round(c_over+0.03,2),even=False))

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800;900&family=Barlow:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#111318;font-family:'Barlow',sans-serif;width:480px;}}
.header{{background:linear-gradient(135deg,#0f1e3d,#1a3a6b);padding:14px 16px;display:flex;align-items:center;gap:12px;border-bottom:2px solid #2a4a8a;}}
.logo{{width:52px;height:52px;border-radius:50%;border:2px solid rgba(255,255,255,0.3);object-fit:cover;flex-shrink:0;}}
.header-title{{font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:800;color:white;letter-spacing:1px;text-transform:uppercase;}}
.header-sub{{font-size:11px;color:#7a9cc8;margin-top:2px;}}
.score-section{{background:#16191f;padding:16px;border-bottom:1px solid #1e2330;}}
.teams-row{{display:flex;align-items:center;justify-content:space-between;gap:8px;}}
.team{{text-align:center;flex:1;}}
.team-badge{{width:56px;height:56px;border-radius:50%;margin:0 auto 8px;display:flex;align-items:center;justify-content:center;font-family:'Barlow Condensed',sans-serif;font-size:15px;font-weight:900;border:3px solid;}}
.badge-home{{background:{c1h};border-color:{c2h};color:{c2h};}}
.badge-away{{background:{c1a};border-color:{c2a};color:{c2a};}}
.team-name{{font-size:13px;font-weight:700;}}
.team-home .team-name{{color:{c1h};}} .team-home .team-status{{color:{c1h};font-size:10px;margin-top:2px;}}
.team-away .team-name{{color:{c1a};}} .team-away .team-status{{color:{c1a};font-size:10px;margin-top:2px;}}
.score-center{{text-align:center;flex-shrink:0;}}
.score-box{{background:linear-gradient(180deg,#1a3a6b,#0f1e3d);border:2px solid #2a4a8a;border-radius:12px;padding:10px 18px;margin-bottom:8px;}}
.score-digits{{font-family:'Barlow Condensed',sans-serif;font-size:36px;font-weight:900;color:white;letter-spacing:6px;line-height:1;}}
.minute-badge{{background:#f59e0b;color:white;font-family:'Barlow Condensed',sans-serif;font-size:14px;font-weight:800;padding:5px 16px;border-radius:20px;display:inline-block;white-space:nowrap;}}
.alert-banner{{background:linear-gradient(90deg,#78350f,#92400e);border-left:4px solid #f59e0b;border-right:4px solid #f59e0b;padding:10px 16px;font-family:'Barlow Condensed',sans-serif;font-size:15px;font-weight:800;color:#fef3c7;text-align:center;text-transform:uppercase;}}
.cards-row{{display:flex;gap:8px;padding:10px 12px;background:#16191f;border-bottom:1px solid #1e2330;}}
.card-group{{flex:1;display:flex;align-items:center;gap:8px;background:#1e2330;border-radius:8px;padding:8px 10px;}}
.card-label{{font-size:11px;color:#7a9cc8;font-weight:600;}}
.card-badges{{display:flex;align-items:center;gap:4px;margin-left:auto;}}
.cbadge{{width:26px;height:34px;border-radius:3px 3px 4px 4px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:white;}}
.yellow-card{{background:#f59e0b;}}
.vs-sep{{font-size:10px;color:#4a5568;}}
.section-title{{background:linear-gradient(90deg,#0f1e3d,#1a2a4a);color:#7ab3ff;font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:800;text-align:center;padding:7px;letter-spacing:1.5px;text-transform:uppercase;border-top:1px solid #1e2330;border-bottom:1px solid #1e2330;}}
.stats-section{{background:#111318;padding:10px 12px 6px;}}
.team-labels{{display:flex;justify-content:space-between;margin-bottom:6px;}}
.bar-item{{margin-bottom:8px;}}
.bar-label{{font-size:11px;font-weight:600;color:#8899bb;margin-bottom:3px;text-align:center;}}
.bar-track{{height:22px;background:#1e2330;border-radius:6px;overflow:hidden;position:relative;}}
.bar-fill{{height:100%;border-radius:6px;position:absolute;left:0;top:0;}}
.bar-pct-home{{position:absolute;left:6px;font-size:11px;font-weight:700;color:white;line-height:22px;}}
.bar-pct-away{{position:absolute;right:6px;font-size:11px;font-weight:600;color:#6b7280;line-height:22px;}}
.key-stats{{background:#111318;}}
.ks-header{{display:flex;padding:6px 12px;background:#0d1017;}}
.ks-header .label{{flex:1;font-size:11px;font-weight:700;color:#4a5568;}}
.ks-header .home-h{{width:60px;text-align:center;font-size:11px;font-weight:700;color:{c1h};}}
.ks-header .away-h{{width:60px;text-align:center;font-size:11px;font-weight:700;color:{c1a};}}
.ks-row{{display:flex;align-items:center;padding:8px 12px;border-bottom:1px solid #1a1d24;}}
.ks-label{{flex:1;font-size:12px;color:#8899bb;}} .ks-sub{{font-size:10px;color:#4a5568;margin-top:1px;}}
.ks-home{{width:60px;text-align:center;font-size:18px;font-weight:800;font-family:'Barlow Condensed',sans-serif;}}
.ks-away{{width:60px;text-align:center;font-size:18px;font-weight:800;font-family:'Barlow Condensed',sans-serif;}}
.odds-section{{background:#111318;}}
.odds-header{{display:flex;padding:6px 12px;background:#0d1017;}}
.odds-header .mkt{{flex:1;font-size:11px;font-weight:700;color:#4a5568;}}
.odds-header .stake-h{{width:80px;text-align:center;font-size:11px;font-weight:700;color:#10b981;}}
.odds-header .xbet-h{{width:80px;text-align:center;font-size:11px;font-weight:700;color:#3b82f6;}}
.odds-row{{display:flex;align-items:center;padding:9px 12px;border-bottom:1px solid #1a1d24;}}
.odds-market{{flex:1;font-size:12px;color:#c0cce0;font-weight:500;}}
.odds-val{{width:80px;text-align:center;font-size:17px;font-weight:800;font-family:'Barlow Condensed',sans-serif;}}
.trade-section{{background:linear-gradient(180deg,#052e16,#14532d);padding:14px 12px;text-align:center;border-top:2px solid #16a34a;}}
.trade-label{{font-size:11px;color:#86efac;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;}}
.trade-action{{font-family:'Barlow Condensed',sans-serif;font-size:22px;font-weight:900;color:white;margin-bottom:12px;}}
.trade-btns{{display:flex;gap:8px;margin-bottom:10px;}}
.trade-btn{{flex:1;border-radius:10px;padding:10px 8px;display:flex;align-items:center;justify-content:center;gap:6px;}}
.btn-stake{{background:#059669;border:2px solid #34d399;}}
.btn-xbet{{background:#1d4ed8;border:2px solid #60a5fa;}}
.btn-name{{font-size:14px;font-weight:800;color:white;font-family:'Barlow Condensed',sans-serif;display:block;}}
.btn-odd{{font-size:11px;color:rgba(255,255,255,0.75);display:block;}}
.sofa-link{{display:inline-block;background:rgba(255,255,255,0.1);color:#86efac;font-size:11px;font-weight:600;padding:6px 16px;border-radius:20px;border:1px solid rgba(255,255,255,0.15);}}
.trade-footer{{font-size:10px;color:#86efac;opacity:0.5;margin-top:8px;}}
</style></head><body>
<div class="header">{logo_tag}<div><div class="header-title">{title_txt} &mdash; SharkBet</div><div class="header-sub">{ligue} &bull; {date_str}</div></div></div>
<div class="score-section"><div class="teams-row">
<div class="team team-home"><div class="team-badge badge-home">{inh}</div><div class="team-name">{home[:14]}</div><div class="team-status">{fav_lbl}</div></div>
<div class="score-center"><div class="score-box"><div class="score-digits">{hs}&ndash;{as_}</div></div><div class="minute-badge">{mi}' &mdash; {mt}</div></div>
<div class="team team-away"><div class="team-badge badge-away">{ina}</div><div class="team-name">{away[:14]}</div><div class="team-status">{los_lbl}</div></div>
</div></div>
<div class="alert-banner">{alert_icon} {alert_label} &mdash; {fav_name}</div>
<div class="cards-row">
<div class="card-group"><span class="card-label">&#127 Jaunes</span><div class="card-badges"><div class="cbadge yellow-card">{yj_h}</div><span class="vs-sep">vs</span><div class="cbadge yellow-card">{yj_a}</div></div></div>
<div class="card-group" style="border:1px solid {cr_color};"><span class="card-label" style="color:{cr_color};">&#128308; Rouges</span><div class="card-badges"><div class="cbadge" style="background:{cr_color};">{cr_h}</div><span class="vs-sep">vs</span><div class="cbadge" style="background:{cr_color};">{cr_a}</div></div></div>
</div>
<div class="section-title">&#9201; LAST 10 MIN ({mr})</div>
<div class="stats-section"><div class="team-labels"><span style="font-size:11px;font-weight:700;color:{c1h};">&#128308; {home[:12]}</span><span style="font-size:11px;font-weight:700;color:{c1a};">{away[:12]} &#128309;</span></div>{bars_html}</div>
<div class="section-title">&#128202; {"KEY STATS" if EN else "CHIFFRES CLES"} &mdash; LAST 10 MIN</div>
<div class="key-stats"><div class="ks-header"><span class="label">Stat</span><span class="home-h">{inh}</span><span class="away-h">{ina}</span></div>{ks_html}</div>
<div class="section-title">&#128185; {"LIVE ODDS" if EN else "COTES LIVE"}</div>
<div class="odds-section"><div class="odds-header"><span class="mkt">{"Market" if EN else "Marche"}</span><span class="stake-h">Stake</span><span class="xbet-h">1xBet</span></div>{odds_html}</div>
<div class="trade-section">
<div class="trade-label">&#9989; {trade_txt}</div>
<div class="trade-action">BACK {fav_name} @ {best_cote}</div>
<div class="trade-btns">
<div class="trade-btn btn-stake"><span style="font-size:16px;">&#127919;</span><span><span class="btn-name">Stake</span><span class="btn-odd">@ {c_fav}</span></span></div>
<div class="trade-btn btn-xbet"><span style="font-size:16px;">&#128142;</span><span><span class="btn-name">1xBet</span><span class="btn-odd">@ {round(c_fav+0.05,2)}</span></span></div>
</div>
<div class="sofa-link">&#128202; {sofa_txt}</div>
<div class="trade-footer">SharkBet &bull; {date_str}</div>
</div></body></html>"""

def html_to_png(html_content):
    with tempfile.NamedTemporaryFile(mode="w",suffix=".html",delete=False,encoding="utf-8") as f:
        f.write(html_content); html_path=f.name
    png_path=html_path.replace(".html",".png")
    try:
        subprocess.run(["wkhtmltoimage","--width","480","--quality","95","--quiet","--disable-smart-width",html_path,png_path],capture_output=True,timeout=30)
        if os.path.exists(png_path):
            with open(png_path,"rb") as f: return f.read()
    except Exception as e: print("ERR wkhtmltoimage:"+str(e))
    finally:
        for p in [html_path,png_path]:
            try: os.unlink(p)
            except: pass
    return None

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
            fav_side="home" if favori_home else "away"; out_side="away" if favori_home else "home"
            if stats_10min.get("da_"+fav_side,0)<CRITERES["da_min"]: continue
            if stats_10min.get("tirs_"+fav_side,0)<CRITERES["tirs_min"]: continue
            if stats_10min.get("corners_"+fav_side,0)+stats_10min.get("coups_francs_"+fav_side,0)<CRITERES["corners_min"]: continue
            ip=calcul_indice_pression(stats_10min,favori_home)
            if ip<CRITERES["pression_min"]: continue
            cle=str(match_id)+"_"+str(hs)+"-"+str(as_)+"_"+str(mi//5)
            if cle in alertes_envoyees: continue
            data_alerte={"home":home,"away":away,"score_home":hs,"score_away":as_,"minute":mi,"ligue":ligue,"favori_home":favori_home,"situation":situation,"stats":stats,"stats_10min":stats_10min,"indice_pression":ip,"odds":odds,"minutes_range":str(max(1,mi-10))+"-> "+str(mi)+"'"}
            fav_name=home if favori_home else away
            for lang in ["fr","en"]:
                try:
                    png=html_to_png(generer_html_alerte(data_alerte,lang=lang))
                    if png: envoyer_telegram_image(png)
                    else: raise Exception("PNG failed")
                    envoyer_telegram_texte("&#127919; <b>Stake:</b> <a href='"+STAKE_LINK+"'>"+STAKE_LINK+"</a>\n&#128142; <b>1xBet:</b> <a href='"+XBET_LINK+"'>"+XBET_LINK+"</a>\n&#128202; <b>SofaScore:</b> <a href='https://www.sofascore.com'>sofascore.com</a>")
                    print("OK "+lang+": "+home+" vs "+away+" "+str(hs)+"-"+str(as_)+" "+str(mi)+"'")
                except Exception as e:
                    print("ERR "+lang+": "+str(e))
                    envoyer_telegram_texte("BACK "+fav_name+" @ "+str(cote_fav)+"\n"+STAKE_LINK)
                time.sleep(1)
            alertes_envoyees.add(cle); count+=1; time.sleep(2)
        except Exception as e: print("ERR:"+str(e))
    print(str(count)+" alerte(s)")

print("BOT SHARKBET DEMARRE!")
envoyer_telegram_texte("&#x1F988; SharkBet v4 demarre! Alertes HTML haute qualite.")
envoyer_telegram_texte("&#x1F988; SharkBet v4 started! HTML high quality alerts.")
scanner()
while True:
    time.sleep(30)
    scanner()
