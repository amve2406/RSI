pip install --upgrade yfinance
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

# Lim inn /exec-URL-en fra RSI-prosjektet (Distribuer → Administrer distribusjoner → kopier nettapp-URL)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx4P4xvjrbzRJow1mzvQ0ppWCaAKHXHoijppIcSI7qLnv5s3mV_ZFXhALaxF0fJ6EHZbg/exec"
# Epost-knappene (Legg til / Selg) peker nå til Apps Script-siden i stedet for GitHub Pages
GITHUB_PAGES_URL = APPS_SCRIPT_URL

AKSJER = {
    "TOM.OL": "Tomra",
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

MAL_RSI = 65.0            # kursen vi regner mot
VIS_MAL_RSI_OVER = 55.0  # regn bare ut mål-kurs når RSI er minst dette


def beregn_rsi(priser, perioder=14):
    delta = priser.diff()
    gevinst = delta.clip(lower=0)
    tap = -delta.clip(upper=0)
    avg_gevinst = gevinst.ewm(com=perioder - 1, min_periods=perioder).mean()
    avg_tap = tap.ewm(com=perioder - 1, min_periods=perioder).mean()
    rs = avg_gevinst / avg_tap
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)


def beregn_rsi_detaljer(priser, perioder=14):
    """Som beregn_rsi, men returnerer også siste glattede snitt (til mål-kurs)."""
    delta = priser.diff()
    gevinst = delta.clip(lower=0)
    tap = -delta.clip(upper=0)
    avg_gevinst = gevinst.ewm(com=perioder - 1, min_periods=perioder).mean()
    avg_tap = tap.ewm(com=perioder - 1, min_periods=perioder).mean()
    rs = avg_gevinst / avg_tap
    rsi = 100 - (100 / (1 + rs))
    return {
        "rsi": round(float(rsi.iloc[-1]), 2),
        "avg_gain": float(avg_gevinst.iloc[-1]),
        "avg_loss": float(avg_tap.iloc[-1]),
    }


def malkurs_neste_dag(avg_gain, avg_loss, siste_kurs, mal_rsi=MAL_RSI, perioder=14):
    """Lukkekurs neste dag som gir mål-RSI, med samme Wilder-glatting som RSI-en."""
    if avg_loss == 0:
        return None
    rs_mal = mal_rsi / (100.0 - mal_rsi)
    n1 = perioder - 1
    rs_dag = avg_gain / avg_loss
    if rs_dag <= rs_mal:                        # under målet -> gevinstdag
        kurs = siste_kurs + n1 * (rs_mal * avg_loss - avg_gain)
    else:                                       # allerede over -> tapsdag
        kurs = siste_kurs + n1 * (avg_loss - avg_gain / rs_mal)
    return round(kurs, 2)


def hent_rsi_data(tickers):
    resultater = []
    for ticker, navn in tickers.items():
        try:
            data = yf.download(ticker, period="1y", progress=False, auto_adjust=False)
            if data.empty or len(data) < 50:
                continue
            close = data["Close"].squeeze()
            det = beregn_rsi_detaljer(close)
            rsi = det["rsi"]
            siste_kurs = round(float(close.iloc[-1]), 2)

            mal_kurs, mal_pct = "–", None
            if rsi >= VIS_MAL_RSI_OVER:
                mk = malkurs_neste_dag(det["avg_gain"], det["avg_loss"], siste_kurs)
                if mk is not None:
                    mal_kurs = mk
                    mal_pct = round((mk / siste_kurs - 1) * 100, 2)

            bors = ticker.split(".")[-1]
            resultater.append({
                "Ticker": ticker,
                "Navn": navn,
                "Børs": bors,
                "Kurs": siste_kurs,
                "RSI 14": rsi,
                "Mål 65": mal_kurs,
                "Mål 65 %": mal_pct,
            })
        except Exception as e:
            print(f"FEIL: {ticker} – {e}")
    return pd.DataFrame(resultater)


def hent_alle_posisjoner():
    try:
        url = APPS_SCRIPT_URL + "?hentAlle=true"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        return data
    except Exception as e:
        print(f"Kunne ikke hente posisjoner: {e}")
        return []


def formater_dato(dato_str):
    try:
        if "T" in str(dato_str):
            dt = datetime.fromisoformat(str(dato_str).replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y")
        return str(dato_str)
    except:
        return str(dato_str)


def parse_dato(dato_str):
    """Parser en dato-streng (ISO med/uten tid, eller dd.mm.åååå) til et date-objekt."""
    s = str(dato_str)
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        pass
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except Exception:
        return None


def beregn_dager_holdt(dato_str, salgsdato_str):
    """Antall dager mellom kjøpsdato og salgsdato. Returnerer '–' hvis dato mangler/feiler."""
    kjop = parse_dato(dato_str)
    salg = parse_dato(salgsdato_str)
    if kjop and salg:
        return (salg - kjop).days
    return "–"


def bygg_posisjoner_html(alle_posisjoner, rsi_df):
    aktive = [p for p in alle_posisjoner if p.get("Status") == "Aktiv"]
    solgte = [p for p in alle_posisjoner if p.get("Status") == "Solgt"]

    rsi_lookup = {}
    mal_lookup = {}
    mal_pct_lookup = {}
    if not rsi_df.empty:
        for _, row in rsi_df.iterrows():
            rsi_lookup[row["Ticker"]] = row["RSI 14"]
            mal_lookup[row["Ticker"]] = row.get("Mål 65", "–")
            mal_pct_lookup[row["Ticker"]] = row.get("Mål 65 %", None)

    # Aktive posisjoner
    aktiv_html = ""
    total_aktiv_pl = 0

    if not aktive:
        aktiv_html = "<p><i>Ingen aktive posisjoner.</i></p>"
    else:
        rader = ""
        for p in aktive:
            try:
                ticker = p.get("Ticker", "")
                if "." not in ticker:
                    ticker = ticker + ".OL"
                navn = p.get("Navn", "")
                kjopskurs = float(str(p.get("Kjøpskurs", 0)).replace(",", "."))
                antall = int(str(p.get("Antall", 0)).replace(",", "."))
                dato = formater_dato(p.get("Dato", ""))
                rsi = rsi_lookup.get(ticker, "–")

                mal = mal_lookup.get(ticker, "–")
                mal_pct = mal_pct_lookup.get(ticker, None)
                if isinstance(mal, (int, float)) and pd.notna(mal) and pd.notna(mal_pct):
                    tegn_mal = "+" if mal_pct >= 0 else ""
                    mal_celle = f"{mal} <span style='color:#888'>({tegn_mal}{mal_pct}%)</span>"
                else:
                    mal_celle = "–"

                data = yf.download(ticker, period="5d", progress=False, auto_adjust=False)
                if data.empty:
                    continue
                dagens_kurs = round(float(data["Close"].squeeze().iloc[-1]), 2)

                pl = round((dagens_kurs - kjopskurs) * antall, 2)
                pl_pst = round(((dagens_kurs - kjopskurs) / kjopskurs) * 100, 2)
                total_aktiv_pl += pl
                farge = "green" if pl >= 0 else "red"
                tegn = "+" if pl >= 0 else ""
                selg_lenke = f"{GITHUB_PAGES_URL}?action=selg&ticker={ticker}&navn={navn}"

                rader += f"""<tr>
                    <td>{navn} ({ticker})</td>
                    <td>{kjopskurs}</td>
                    <td>{dagens_kurs}</td>
                    <td>{antall}</td>
                    <td style="color:{farge}"><b>{tegn}{pl} kr ({tegn}{pl_pst}%)</b></td>
                    <td>{dato}</td>
                    <td>{rsi}</td>
                    <td>{mal_celle}</td>
                    <td><a href="{selg_lenke}" style="background:#d93025;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;">Selg</a></td>
                </tr>"""
            except Exception as e:
                print(f"Feil på aktiv posisjon {p}: {e}")

        farge_aktiv = "green" if total_aktiv_pl >= 0 else "red"
        tegn_aktiv = "+" if total_aktiv_pl >= 0 else ""
        aktiv_html = f"""
        <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%">
            <tr style="background:#f0f0f0">
                <th>Aksje</th><th>Kjøpskurs</th><th>Dagens kurs</th>
                <th>Antall</th><th>P/L</th><th>Kjøpsdato</th><th>RSI 14</th><th>Kurs → RSI 65</th><th></th>
            </tr>
            {rader}
        </table>
        <p><b>Urealisert P/L: <span style="color:{farge_aktiv}">{tegn_aktiv}{round(total_aktiv_pl, 2)} kr</span></b></p>
        """

    # Solgte posisjoner
    solgt_html = ""
    total_realisert_pl = 0

    if solgte:
        rader_solgt = ""
        for p in solgte:
            try:
                ticker = p.get("Ticker", "")
                navn = p.get("Navn", "")
                kjopskurs = float(str(p.get("Kjøpskurs", 0)).replace(",", "."))
                antall = int(str(p.get("Antall", 0)).replace(",", "."))
                salgskurs = float(str(p.get("Salgskurs", 0)).replace(",", "."))
                antall_solgt = int(str(p.get("Antall solgt", antall)).replace(",", "."))
                kjopsdato = formater_dato(p.get("Dato", ""))
                salgsdato = formater_dato(p.get("Salgsdato", ""))
                dager_holdt = beregn_dager_holdt(p.get("Dato", ""), p.get("Salgsdato", ""))

                pl = round((salgskurs - kjopskurs) * antall_solgt, 2)
                pl_pst = round(((salgskurs - kjopskurs) / kjopskurs) * 100, 2)
                total_realisert_pl += pl
                farge = "green" if pl >= 0 else "red"
                tegn = "+" if pl >= 0 else ""

                rader_solgt += f"""<tr>
                    <td>{navn} ({ticker})</td>
                    <td>{kjopskurs}</td>
                    <td>{salgskurs}</td>
                    <td>{antall_solgt}</td>
                    <td style="color:{farge}"><b>{tegn}{pl} kr ({tegn}{pl_pst}%)</b></td>
                    <td>{kjopsdato}</td>
                    <td>{salgsdato}</td>
                    <td>{dager_holdt}</td>
                </tr>"""
            except Exception as e:
                print(f"Feil på solgt posisjon {p}: {e}")

        farge_solgt = "green" if total_realisert_pl >= 0 else "red"
        tegn_solgt = "+" if total_realisert_pl >= 0 else ""
        solgt_html = f"""
        <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%">
            <tr style="background:#f0f0f0">
                <th>Aksje</th><th>Kjøpskurs</th><th>Salgskurs</th>
                <th>Antall</th><th>Realisert P/L</th><th>Kjøpsdato</th><th>Salgsdato</th><th>Dager holdt</th>
            </tr>
            {rader_solgt}
        </table>
        <p><b>Realisert P/L: <span style="color:{farge_solgt}">{tegn_solgt}{round(total_realisert_pl, 2)} kr</span></b></p>
        """

    farge_total = "green" if total_realisert_pl >= 0 else "red"
    tegn_total = "+" if total_realisert_pl >= 0 else ""
    total_html = f"""
    <p style="font-size:18px"><b>💰 Total realisert P/L:
    <span style="color:{farge_total}">{tegn_total}{round(total_realisert_pl, 2)} kr</span></b></p>
    """

    return aktiv_html + total_html, solgt_html


def send_email(df, posisjoner_html, solgte_html):
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

    <h2 style="color:#1a73e8">📊 Posisjoner</h2>
    {posisjoner_html}

    <hr>
    <h3 style="color:green">OVERSOLGT (RSI under 30) – mulig kjøpssignal ({len(oversolgt)} aksjer)</h3>
    {tabell_med_knapper(oversolgt)}
    <h3 style="color:red">OVERKJØPT (RSI over 70) – mulig salgssignal ({len(overkjopt)} aksjer)</h3>
    {tabell_med_knapper(overkjopt)}
    <h3>NØYTRAL SONE (RSI 30-70) – {len(noytralt)} aksjer</h3>
    {tabell_med_knapper(noytralt)}

    <p><b>Totalt: {len(df)} aksjer | Overkjøpt: {len(overkjopt)} | Oversolgt: {len(oversolgt)}</b></p>
    <hr>
    <h3 style="color:#555">📋 Solgte posisjoner</h3>
    {solgte_html}
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
alle_posisjoner = hent_alle_posisjoner()
posisjoner_html, solgte_html = bygg_posisjoner_html(alle_posisjoner, df)
send_email(df, posisjoner_html, solgte_html)
