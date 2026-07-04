import yfinance as yf
import pandas as pd
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import urllib.request
import json

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx4P4xvjrbzRJow1mzvQ0ppWCaAKHXHoijppIcSI7qLnv5s3mV_ZFXhALaxF0fJ6EHZbg/exec"

SALG_RSI = 25          # RSI-nivå du selger på
PERIODER = 14
STATE_FIL = "varsel_state.json"


def hent_aktive_posisjoner():
    try:
        url = APPS_SCRIPT_URL + "?hentAlle=true"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        return [p for p in data if p.get("Status") == "Aktiv"]
    except Exception as e:
        print(f"Kunne ikke hente posisjoner: {e}")
        return []


def wilder_komponenter(ticker, perioder=PERIODER):
    """avg_gain/avg_loss t.o.m. GÅRSDAGENS lukk (ekskluderer dagens ufullstendige candle)."""
    data = yf.download(ticker, period="1y", progress=False, auto_adjust=False)
    if data.empty:
        return None
    data = data[data.index.date < date.today()]
    if len(data) < perioder + 1:
        return None
    close = data["Close"].squeeze()
    delta = close.diff()
    gevinst = delta.clip(lower=0)
    tap = -delta.clip(upper=0)
    avg_gevinst = gevinst.ewm(com=perioder - 1, min_periods=perioder).mean()
    avg_tap = tap.ewm(com=perioder - 1, min_periods=perioder).mean()
    return {
        "avg_gain_prev": float(avg_gevinst.iloc[-1]),
        "avg_loss_prev": float(avg_tap.iloc[-1]),
        "forrige_lukk": float(close.iloc[-1]),
    }


def hent_live_kurs(ticker):
    try:
        pris = yf.Ticker(ticker).fast_info["lastPrice"]
        if pris:
            return float(pris)
    except Exception:
        pass
    try:
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not data.empty:
            return float(data["Close"].squeeze().iloc[-1])
    except Exception:
        pass
    return None


def regn_target_kurs(komponenter, target_rsi, perioder=PERIODER):
    avg_gain_prev = komponenter["avg_gain_prev"]
    avg_loss_prev = komponenter["avg_loss_prev"]
    forrige_lukk = komponenter["forrige_lukk"]
    if avg_loss_prev == 0:
        return None  # RSI allerede ~100, ingen meningsfull target
    rs_target = target_rsi / (100 - target_rsi)
    avg_gain_needed = rs_target * avg_loss_prev
    gain_needed = avg_gain_needed * perioder - avg_gain_prev * (perioder - 1)
    return round(forrige_lukk + gain_needed, 2)


def regn_dagens_rsi(komponenter, live_pris, perioder=PERIODER):
    forrige_lukk = komponenter["forrige_lukk"]
    endring = live_pris - forrige_lukk
    gevinst = max(endring, 0)
    tap = max(-endring, 0)
    avg_gain = (komponenter["avg_gain_prev"] * (perioder - 1) + gevinst) / perioder
    avg_loss = (komponenter["avg_loss_prev"] * (perioder - 1) + tap) / perioder
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def last_state():
    if os.path.exists(STATE_FIL):
        with open(STATE_FIL) as f:
            return json.load(f)
    return {}


def lagre_state(state):
    with open(STATE_FIL, "w") as f:
        json.dump(state, f)


def send_varsel(triggede):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ["EMAIL_ADDRESS"]

    rader = ""
    for t in triggede:
        rader += f"""<tr>
            <td>{t['navn']} ({t['ticker']})</td>
            <td>{t['forrige_lukk']}</td>
            <td>{t['target_kurs']}</td>
            <td>{t['live_kurs']}</td>
            <td><b>{t['dagens_rsi']}</b></td>
        </tr>"""

    body = f"""
    <html><body style="font-family: Arial, sans-serif;">
    <h2>🔔 RSI-salgssignal – {datetime.now().strftime('%d.%m.%Y %H:%M')}</h2>
    <p>Følgende posisjoner har nådd RSI ≥ {SALG_RSI} i dag:</p>
    <table border="1" cellpadding="6" style="border-collapse:collapse">
        <tr style="background:#f0f0f0">
            <th>Aksje</th><th>Forrige lukk</th><th>Target-kurs (RSI={SALG_RSI})</th><th>Live kurs</th><th>Dagens RSI</th>
        </tr>
        {rader}
    </table>
    </body></html>
    """

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = f"🔔 RSI-salgssignal utløst ({len(triggede)} aksje{'r' if len(triggede) != 1 else ''})"
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
    print(f"Varsel sendt for {len(triggede)} aksjer.")


def main():
    posisjoner = hent_aktive_posisjoner()
    if not posisjoner:
        print("Ingen aktive posisjoner.")
        return

    state = last_state()
    i_dag = date.today().isoformat()
    triggede = []

    for p in posisjoner:
        ticker = p.get("Ticker", "")
        if "." not in ticker:
            ticker = ticker + ".OL"
        navn = p.get("Navn", ticker)

        if state.get(ticker) == i_dag:
            continue  # allerede varslet i dag

        komponenter = wilder_komponenter(ticker)
        if not komponenter:
            print(f"Hopper over {ticker} – for lite historikk.")
            continue

        live_pris = hent_live_kurs(ticker)
        if live_pris is None:
            print(f"Fant ikke live-kurs for {ticker}.")
            continue

        target_kurs = regn_target_kurs(komponenter, SALG_RSI)
        dagens_rsi = regn_dagens_rsi(komponenter, live_pris)

        print(f"{ticker}: forrige lukk={komponenter['forrige_lukk']} live={live_pris} "
              f"target={target_kurs} RSI={dagens_rsi}")

        if target_kurs is not None and live_pris >= target_kurs:
            triggede.append({
                "ticker": ticker,
                "navn": navn,
                "forrige_lukk": komponenter["forrige_lukk"],
                "target_kurs": target_kurs,
                "live_kurs": live_pris,
                "dagens_rsi": dagens_rsi,
            })
            state[ticker] = i_dag

    if triggede:
        send_varsel(triggede)
        lagre_state(state)
    else:
        print("Ingen posisjoner har nådd terskelen ennå.")


if __name__ == "__main__":
    main()
