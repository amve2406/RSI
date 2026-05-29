import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import urllib.request
import json

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzwy59fxVohZ-8iI4Ix0bOxARNukv4vliowAXY-hU1SA_HbW7jZExyt99YDnD2nnt34/exec"
GITHUB_PAGES_URL = "https://amve2406.github.io/RSI/"

AKSJER = {
    "EQNR.OL": "Equinor",
    "DNB.OL": "DNB Bank",
    "TEL.OL": "Telenor",
    "MOWI.OL": "Mowi",
    "YAR.OL": "Yara International",
    "AKRBP.OL": "Aker BP",
    "ORK.OL": "Orkla",
    "SALM.OL": "SalMar",
    "SUBC.OL": "Subsea 7",
    "NHY.OL": "Norsk Hydro",
    "KOG.OL": "Kongsberg Gruppen",
    "SCATC.OL": "Scatec",
    "STB.OL": "Storebrand",
    "GJF.OL": "Gjensidige Forsikring",
    "AUTO.OL": "AutoStore",
    "NOD.OL": "Nordic Semiconductor",
    "AKSO.OL": "Aker Solutions",
    "AKER.OL": "Aker ASA",
    "ABB.ST": "ABB",
    "ALFA.ST": "Alfa Laval",
    "ASSA-B.ST": "Assa Abloy B",
    "AZN.ST": "AstraZeneca",
    "ATCO-A.ST": "Atlas Copco A",
    "BOL.ST": "Boliden",
    "EPI-A.ST": "Epiroc A",
    "EQT.ST": "EQT",
    "ERIC-B.ST": "Ericsson B",
    "EVO.ST": "Evolution",
    "SHB-A.ST": "Handelsbanken A",
    "HM-B.ST": "H&M B",
    "HEXA-B.ST": "Hexagon B",
    "INVE-B.ST": "Investor B",
    "NDA-SE.ST": "Nordea SE",
    "SAAB-B.ST": "Saab B",
    "SAND.ST": "Sandvik",
    "SEB-A.ST": "SEB A",
    "SKF-B.ST": "SKF B",
    "SWED-A.ST": "Swedbank A",
    "VOLV-B.ST": "Volvo B",
    "MAERSK-A.CO": "Maersk A",
    "MAERSK-B.CO": "Maersk B",
    "AMBU-B.CO": "Ambu B",
    "CARL-B.CO": "Carlsberg B",
    "COLO-B.CO": "Coloplast B",
    "DANSKE.CO": "Danske Bank",
    "DEMANT.CO": "Demant",
    "DSV.CO": "DSV",
    "GMAB.CO": "Genmab",
    "GN.CO": "GN Store Nord",
    "NKT.CO": "NKT",
    "NOVO-B.CO": "Novo Nordisk B",
    "PNDORA.CO": "Pandora",
    "TRYG.CO": "Tryg",
    "VWS.CO": "Vestas",
    "ORSTED.CO": "Orsted",
    "ELISA.HE": "Elisa",
    "FORTUM.HE": "Fortum",
    "KNEBV.HE": "KONE",
    "KCR.HE": "Konecranes",
    "METSO.HE": "Metso",
    "NESTE.HE": "Neste",
    "NOKIA.HE": "Nokia",
    "NDA-FI.HE": "Nordea FI",
    "SAMPO.HE": "Sampo",
    "STERV.HE": "Stora Enso R",
    "TIETO.HE": "TietoEVRY",
    "UPM.HE": "UPM-Kymmene",
    "VALMT.HE": "Valmet",
    "WRT1V.HE": "Wartsila",
    "KEMIRA.HE": "Kemira",
    "KESKOB.HE": "Kesko B",
    "OUT1V.HE": "Outokumpu",
    "HUH1V.HE": "Huhtamaki",
    "ORNBV.HE": "Orion",
    "QTCOM.HE": "Qt Group",
}

def beregn_rsi(priser, perioder=14):
    delta = priser.diff()
    gevinst = delta.clip(lower=0)
    tap = -delta.clip(upper=0)
    avg_gevinst = gevinst.ewm(com=perioder - 1, min_periods=perioder).mean()
    avg_tap = tap.ewm(com=perioder - 1, min_periods=perioder).mean()
    rs = avg_gevinst / avg_tap
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)

def hent_rsi_data(tickers):
    resultater = []
    for ticker, navn in tickers.items():
        try:
            data = yf.download(ticker, period="1y", progress=False, auto_adjust=False)
            if data.empty or len(data) < 50:
                continue
            close = data["Close"].squeeze()
            rsi = beregn_rsi(close)
            siste_kurs = round(float(close.iloc[-1]), 2)
            bors = ticker.split(".")[-1]
            resultater.append({
                "Ticker": ticker,
                "Navn": navn,
                "Børs": bors,
                "Kurs": siste_kurs,
                "RSI 14": rsi
            })
        except Exception as e:
            print(f"FEIL: {ticker} – {e}")
    return pd.DataFrame(resultater)

def hent_posisjoner():
    try:
        req = urllib.request.Request(APPS_SCRIPT_URL)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        return data
    except Exception as e:
        print(f"Kunne ikke hente posisjoner: {e}")
        return []

def bygg_posisjoner_html(posisjoner):
    if not posisjoner:
        return "<p><i>Ingen aktive posisjoner.</i></p>"

    rader = ""
    total_pl = 0

    for p in posisjoner:
        try:
            ticker = p.get("Ticker", "")
            # Legg til børs-suffiks hvis mangler
            if "." not in ticker:
                ticker = ticker + ".OL"
            navn = p.get("Navn", "")
            kjopskurs = float(p.get("Kjøpskurs", 0))
            antall = int(p.get("Antall", 0))
            dato = p.get("Dato", "")

            data = yf.download(ticker, period="5d", progress=False, auto_adjust=False)
            if data.empty:
                continue
            dagens_kurs = round(float(data["Close"].squeeze().iloc[-1]), 2)

            pl = round((dagens_kurs - kjopskurs) * antall, 2)
            pl_pst = round(((dagens_kurs - kjopskurs) / kjopskurs) * 100, 2)
            total_pl += pl
            farge = "green" if pl >= 0 else "red"
            tegn = "+" if pl >= 0 else ""

            rader += f"""
            <tr>
                <td>{navn} ({ticker})</td>
                <td>{kjopskurs}</td>
                <td>{dagens_kurs}</td>
                <td>{antall}</td>
                <td style="color:{farge}"><b>{tegn}{pl} kr ({tegn}{pl_pst}%)</b></td>
                <td>{dato}</td>
            </tr>"""
        except Exception as e:
            print(f"Feil på posisjon {p}: {e}")

    total_farge = "green" if total_pl >= 0 else "red"
    tegn = "+" if total_pl >= 0 else ""

    return f"""
    <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%">
        <tr style="background:#f0f0f0">
            <th>Aksje</th>
            <th>Kjøpskurs</th>
            <th>Dagens kurs</th>
            <th>Antall</th>
            <th>P/L</th>
            <th>Kjøpsdato</th>
        </tr>
        {rader}
    </table>
    <p><b>Total P/L: <span style="color:{total_farge}">{tegn}{round(total_pl, 2)} kr</span></b></p>
    """

def send_email(df, posisjoner_html):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ["EMAIL_ADDRESS"]

    df_sortert = df.sort_values("RSI 14").reset_index(drop=True)
    overkjopt = df_sortert[df_sortert["RSI 14"] > 70]
    oversolgt = df_sortert[df_sortert["RSI 14"] < 30]
    noytralt = df_sortert[(df_sortert["RSI 14"] >= 30) & (df_sortert["RSI 14"] <= 70)]

    def tabell_med_knapper(df_del):
        if df_del.empty:
            return "<p><i>Ingen.</i></p>"
        rader = ""
        for _, row in df_del.iterrows():
            lenke = f"{GITHUB_PAGES_URL}?ticker={row['Ticker']}&navn={row['Navn']}"
            rader += f"""<tr>
                <td>{row['Ticker']}</td>
                <td>{row['Navn']}</td>
                <td>{row['Børs']}</td>
                <td>{row['Kurs']}</td>
                <td>{row['RSI 14']}</td>
                <td><a href="{lenke}" style="background:#2ea44f;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;">+ Legg til</a></td>
            </tr>"""
        return f"""<table border="1" cellpadding="6" style="border-collapse:collapse">
            <tr style="background:#f0f0f0">
                <th>Ticker</th><th>Navn</th><th>Børs</th><th>Kurs</th><th>RSI 14</th><th></th>
            </tr>{rader}</table>"""

    body = f"""
    <html><body style="font-family: Arial, sans-serif;">
    <h2>Nordisk RSI-rapport – {datetime.now().strftime('%d.%m.%Y')}</h2>

    <h2 style="color:#1a73e8">📊 Aktive posisjoner</h2>
    {posisjoner_html}

    <hr>
    <h3 style="color:green">OVERSOLGT (RSI under 30) – mulig kjøpssignal ({len(oversolgt)} aksjer)</h3>
    {tabell_med_knapper(oversolgt)}
    <h3 style="color:red">OVERKJØPT (RSI over 70) – mulig salgssignal ({len(overkjopt)} aksjer)</h3>
    {tabell_med_knapper(overkjopt)}
    <h3>NØYTRAL SONE (RSI 30-70) – {len(noytralt)} aksjer</h3>
    {tabell_med_knapper(noytralt)}

    <p><b>Totalt: {len(df)} aksjer | Overkjøpt: {len(overkjopt)} | Oversolgt: {len(oversolgt)}</b></p>
    </body></html>
    """

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = f"Nordisk RSI – {datetime.now().strftime('%d.%m.%Y')}"
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print(f"E-post sendt! {len(df)} aksjer analysert.")

df = hent_rsi_data(AKSJER)
posisjoner = hent_posisjoner()
posisjoner_html = bygg_posisjoner_html(posisjoner)
send_email(df, posisjoner_html)
