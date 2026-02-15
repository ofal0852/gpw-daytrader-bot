import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime
import os
import time
import pytz

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK')

TICKERS = [
    "CDR.WA", "PKN.WA", "PKO.WA", "PEO.WA", "KGH.WA", "LPP.WA", "XTB.WA",
    "DNP.WA", "MBK.WA", "ACP.WA", "SPL.WA", "11B.WA", "ALE.WA", "CYF.WA",
    "WPL.WA", "OPL.WA"
]

def send_discord(msg):
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": msg})
        except:
            pass

def get_signal(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if len(df) < 40:
            return None

        df['ema9'] = ta.ema(df['Close'], length=9)
        df['ema21'] = ta.ema(df['Close'], length=21)
        df['rsi'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        score = 0

        if last['ema9'] > last['ema21'] and prev['ema9'] <= prev['ema21']:
            score += 5
        if last['Close'] > last['ema9']:
            score += 2
        if 45 <= last['rsi'] <= 68:
            score += 2
        elif last['rsi'] < 40:
            score += 3
        if last['MACDh_12_26_9'] > prev['MACDh_12_26_9']:
            score += 3
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        if last['Volume'] > vol_avg * 1.5:
            score += 2
        if last['Close'] <= last['BBL_20_2.0'] * 1.03:
            score += 3

        if score >= 12:
            pct = round((last['Close'] / df['Low'].rolling(20).min().iloc[-1] - 1) * 100, 1)
            time_str = last.name.strftime('%H:%M')
            msg = (
                f"**🚀 {ticker.replace('.WA', '')} → LONG DAY TRADE**\n"
                f"**Cena:** {last['Close']:.2f} zł | **{time_str}**\n"
                f"**Siła:** {score}/18 | RSI: {last['rsi']:.1f}\n"
                f"Vol: {last['Volume']/vol_avg:.1f}x | Od dołka: +{pct}%\n"
                f"→ **Wejdź teraz ręcznie w XTB!**"
            )
            return msg
        return None
    except:
        return None

if __name__ == "__main__":
    warsaw_tz = pytz.timezone('Europe/Warsaw')
    now = datetime.now(warsaw_tz)
    
    if now.weekday() >= 5 or now.hour < 9 or now.hour >= 17:
        print("Poza sesją GPW – pomijam")
    else:
        print(f"Start o {now.strftime('%H:%M')} – sprawdzam tickery...")
        for tick in TICKERS:
            signal = get_signal(tick)
            if signal:
                send_discord(signal)
                print(signal)
            time.sleep(3)
