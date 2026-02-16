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

# Pamięć otwartych pozycji (resetuje się co dzień)
open_positions = {}

def send_discord(msg):
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": msg})
        except:
            pass

def get_entry_signal(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="10m", progress=False)
        if len(df) < 40:
            return None, None

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
        if last['ema9'] > last['ema21'] and prev['ema9'] <= prev['ema21']: score += 5
        if last['Close'] > last['ema9']: score += 2
        if 45 <= last['rsi'] <= 68: score += 2
        elif last['rsi'] < 40: score += 3
        if last['MACDh_12_26_9'] > prev['MACDh_12_26_9']: score += 3
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        if last['Volume'] > vol_avg * 1.5: score += 2
        if last['Close'] <= last['BBL_20_2.0'] * 1.03: score += 3

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
            return msg, last['Close']
        return None, None
    except:
        return None, None


def check_exit(ticker, entry_price):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if len(df) < 30: return None

        df['ema9'] = ta.ema(df['Close'], length=9)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        warsaw_now = datetime.now(pytz.timezone('Europe/Warsaw'))
        minutes_to_close = (17 - warsaw_now.hour) * 60 - warsaw_now.minute

        exit_reasons = []
        current_profit = (last['Close'] / entry_price - 1) * 100

        if last['Close'] < last['ema9'] and prev['Close'] >= prev['ema9']:
            exit_reasons.append("EMA9 przebita w dół")
        if last['MACDh_12_26_9'] < prev['MACDh_12_26_9']:
            exit_reasons.append("MACD histogram spada")
        if current_profit >= 3.0:
            exit_reasons.append(f"+{current_profit:.1f}% – cel osiągnięty")
        if minutes_to_close <= 30 and minutes_to_close > 0:
            exit_reasons.append("≤30 min do zamknięcia sesji")

        if exit_reasons:
            time_str = last.name.strftime('%H:%M')
            msg = (
                f"**⚠️ {ticker.replace('.WA', '')} → EXIT / ROZWAŻ SPRZEDAŻ**\n"
                f"**Cena:** {last['Close']:.2f} zł | **{time_str}**\n"
                f"**Zysk:** {current_profit:+.1f}%\n"
                f"Powód: {', '.join(exit_reasons[:2])}\n"
                f"→ **Zamknij ręcznie w XTB**"
            )
            return msg
        return None
    except:
        return None


if __name__ == "__main__":
    warsaw_tz = pytz.timezone('Europe/Warsaw')
    now = datetime.now(warsaw_tz)
    hour = now.hour
    minute = now.minute

    if now.weekday() >= 5 or hour < 9 or hour >= 17:
        print("Poza sesją GPW")
        exit()

    print(f"Start o {now.strftime('%H:%M')} – sprawdzam tickery...")

    signals_sent = 0   # licznik sygnałów w tym przebiegu

    # 1. Najpierw sprawdzamy wyjścia
    to_remove = []
    for ticker, entry_price in list(open_positions.items()):
        exit_msg = check_exit(ticker, entry_price)
        if exit_msg:
            send_discord(exit_msg)
            print(exit_msg)
            signals_sent += 1
            to_remove.append(ticker)

    for t in to_remove:
        del open_positions[t]

    # 2. Potem szukamy nowych wejść
    for tick in TICKERS:
        entry_msg, entry_price = get_entry_signal(tick)
        if entry_msg:
            send_discord(entry_msg)
            print(entry_msg)
            open_positions[tick] = entry_price
            signals_sent += 1
        time.sleep(2.5)

    # 3. Status co pół godziny (jeśli nic się nie działo)
    if (minute % 30 == 0) and signals_sent == 0:
        status_msg = f"**Bot przeanalizował {len(TICKERS)} spółek – nie ma nic wartego uwagi** ({now.strftime('%H:%M')})"
        send_discord(status_msg)
        print(status_msg)

    print(f"Zakończono przebieg. Sygnałów wysłanych: {signals_sent}")
