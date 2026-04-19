import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

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
                print(f"Ingen data for {ticker}")
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
            print(f"OK: {ticker} RSI={rsi}")
        except Exception as e:
            print(f"FEIL: {ticker} – {e}")
    return pd.DataFrame(resultater)

def send_email(df):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ["EMAIL_ADDRESS"]

    df_sortert = df.sort_values("RSI 14").reset_index(drop=True)
    overkjopt = df_sortert[df_sortert["RSI 14"] > 70]
    oversolgt = df_sortert[df_sortert["RSI 14"] < 30]
    noytralt = df_sortert[(df_sortert["RSI 14"] >= 30) & (df_sortert["RSI 14"] <= 70)]

    def tabell(df_del):
        if df_del.empty:
            return "<p><i>Ingen.</i></p>"
        return df_del.to_html(index=False, border=1)

    body = f"""
    <html><body style="font-family: Arial, sans-serif;">
    <h2>Nordisk RSI-rapport – {datetime.now().strftime('%d.%m.%Y')}</h2>
    <p>Oslo Bors / Stockholm / Kobenhavn / Helsinki</p>
    <h3 style="color:green">OVERSOLGT (RSI under 30) – mulig kjopssignal ({len(oversolgt)} aksjer)</h3>
    {tabell(oversolgt)}
    <h3 style="color:red">OVERKJOPT (RSI over 70) – mulig salgssignal ({len(overkjopt)} aksjer)</h3>
    {tabell(overkjopt)}
    <h3>NOYTRAL SONE (RSI 30-70) – {len(noytralt)} aksjer</h3>
    {tabell(noytralt)}
    <p><b>Totalt: {len(df)} aksjer | Overkjopt: {len(overkjopt)} | Oversolgt: {len(oversolgt)}</b></p>
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
send_email(df)
