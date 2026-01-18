import requests
import json
import time
from datetime import datetime, timedelta, timezone
import telebot

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"
USE_YFINANCE = True  # True = Yahoo Finance (Forex + Cripto)
STATUS_INTERVAL = 5  # minutos entre mensagens de "bot ativo"
PROB_THRESHOLD = 60  # Probabilidade mínima (%) para sinal destacado

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "NZD/USD",
    "EUR/JPY", "GBP/JPY", "EUR/GBP",
    "BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD", "SOL/USD", "XRP/USD"
]

YF_SYMBOLS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "EUR/GBP": "EURGBP=X",
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "BNB/USD": "BNB-USD",
    "ADA/USD": "ADA-USD", "SOL/USD": "SOL-USD", "XRP/USD": "XRP-USD"
}

# ===============================
# HISTÓRICO
# ===============================
HISTORICO_FILE = "historico.json"

try:
    with open(HISTORICO_FILE, "r") as f:
        historico = json.load(f)
except FileNotFoundError:
    historico = []

# ===============================
# CACHE DE CANDLES
# ===============================
ultimo_candle = {}  # chave = ativo, valor = (candle, timestamp)

# ===============================
# FUNÇÕES
# ===============================
def candle_yf(ativo):
    try:
        import yfinance as yf
        symbol = YF_SYMBOLS.get(ativo)
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            last = data.iloc[-1]
            time_candle = last.name.to_pydatetime()
            if time_candle.tzinfo is None:
                time_candle = time_candle.replace(tzinfo=timezone.utc)
            return {
                "open": float(last["Open"].iloc[0]) if hasattr(last["Open"], "iloc") else float(last["Open"]),
                "close": float(last["Close"].iloc[0]) if hasattr(last["Close"], "iloc") else float(last["Close"]),
                "time": time_candle
            }
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
    return None

def candle_cache(ativo):
    agora = datetime.now(timezone.utc)
    if ativo in ultimo_candle:
        candle, ts = ultimo_candle[ativo]
        if (agora - ts).seconds < 60:
            return candle
    candle = candle_yf(ativo)
    if candle:
        ultimo_candle[ativo] = (candle, agora)
    return candle

def gerar_sinal(candle):
    if not candle:
        return None
    open_p = candle["open"]
    close_p = candle["close"]
    if close_p > open_p:
        return "CALL"
    elif close_p < open_p:
        return "PUT"
    return None

def salvar_historico(h):
    for entry in h:
        for key in ["analisada", "entrada"]:
            if isinstance(entry.get(key), datetime):
                entry[key] = entry[key].strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORICO_FILE, "w") as f:
        json.dump(h, f, indent=2)

def candle_fechado(candle):
    agora = datetime.now(timezone.utc)
    return agora >= candle["time"] + timedelta(minutes=1)

def calcular_probabilidade(ativo, tipo):
    total = 0
    acertos = 0
    for entry in historico:
        if entry["ativo"] == ativo and entry["resultado"] in ["Green", "Red"]:
            total += 1
            if (entry["tipo"] == "CALL" and entry["resultado"] == "Green") or \
               (entry["tipo"] == "PUT" and entry["resultado"] == "Green"):
                acertos += 1
    if total == 0:
        return 0
    return int((acertos / total) * 100)

def checar_resultado(sinal):
    candle = candle_cache(sinal["ativo"])
    if not candle or not candle_fechado(candle):
        return None
    close_p = candle["close"]
    open_p = candle["open"]
    if sinal["tipo"] == "CALL":
        return "Green" if close_p > open_p else "Red"
    else:
        return "Green" if close_p < open_p else "Red"

# ===============================
# LOOP PRINCIPAL (1 sinal por vez)
# ===============================
ultimo_status = datetime.now(timezone.utc) - timedelta(minutes=STATUS_INTERVAL)
print("🤖 Troia Bot IA iniciado!")

while True:
    agora = datetime.now(timezone.utc)

    # 1️⃣ Mensagem periódica de referência
    if (agora - ultimo_status).seconds >= STATUS_INTERVAL * 60:
        try:
            bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
        except Exception as e:
            print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # 2️⃣ Checa se existe sinal pendente
    sinal_atual = next((s for s in historico if s["resultado"] == "PENDENTE"), None)

    if sinal_atual:
        resultado = checar_resultado(sinal_atual)
        if resultado:
            sinal_atual["resultado"] = resultado
            salvar_historico(historico)
            prob = calcular_probabilidade(sinal_atual["ativo"], sinal_atual["tipo"])
            destaque = "💥 ENTRADA SEGURA!" if prob >= PROB_THRESHOLD else ""
            try:
                msg = f"📊 **RESULTADO DO SINAL** {destaque}\n{sinal_atual['ativo']}: {sinal_atual['tipo']}\nResultado: {resultado}\nProbabilidade histórica: {prob}%"
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram resultado: {e}")
        # Espera o resultado antes de analisar próximo ativo
        time.sleep(10)
        continue

    # 3️⃣ Nenhum sinal pendente → gera próximo sinal
    for ativo in ATIVOS:
        candle = candle_cache(ativo)
        if not candle or not candle_fechado(candle):
            continue
        sinal_tipo = gerar_sinal(candle)
        if sinal_tipo:
            entrada = agora + timedelta(minutes=1)
            novo_sinal = {
                "ativo": ativo,
                "tipo": sinal_tipo,
                "analisada": agora,
                "entrada": entrada,
                "resultado": "PENDENTE"
            }
            historico.append(novo_sinal)
            salvar_historico(historico)
            prob = calcular_probabilidade(ativo, sinal_tipo)
            destaque = "💥 ENTRADA SEGURA!" if prob >= PROB_THRESHOLD else ""
            try:
                msg = f"📊 **TROIA BOT IA - NOVO SINAL** {destaque}\n{ativo}: {sinal_tipo}\nEntrada: {entrada.strftime('%H:%M')}\nProbabilidade histórica: {prob}%"
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram novo sinal: {e}")
            break  # ⚠️ somente 1 sinal por vez

    time.sleep(10)
