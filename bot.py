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
