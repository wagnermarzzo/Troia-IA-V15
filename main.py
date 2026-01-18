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
API_KEY = "128da1172fbb4aef83ca801cb3e6b928"
USE_YFINANCE = True
STATUS_INTERVAL = 5  # minutos entre mensagens de "bot ativo"

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "NZD/USD",
    "EUR/JPY", "GBP/JPY", "EUR/GBP",
    "BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD", "SOL/USD", "XRP/USD"
]

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
ultimo_candle = {}

# ===============================
# FUNÇÕES
# ===============================
def twelve_api_candle(ativo):
    symbol = ativo.replace("/", "")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&apikey={API_KEY}&outputsize=2"
    try:
        resp = requests.get(url, timeout=10).json()
        if "values" in resp:
            val = resp["values"][0]
            return {
                "open": float(val["open"]),
                "close": float(val["close"]),
                "time": datetime.strptime(val["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            }
        else:
            print(f"Erro API Twelve Data {ativo}: {resp}")
            return None
    except Exception as e:
        print(f"Erro requisição {ativo}: {e}")
        return None

def candle_yf(ativo):
    try:
        import yfinance as yf
        symbol = ativo.replace("/", "") + "=X"
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            last = data.iloc[-1]
            time_candle = last.name.to_pydatetime()
            if time_candle.tzinfo is None:
                time_candle = time_candle.replace(tzinfo=timezone.utc)
            return {"open": float(last["Open"]), "close": float(last["Close"]), "time": time_candle}
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
    return None

def twelve_api_candle_cache(ativo):
    agora = datetime.now(timezone.utc)
    if ativo in ultimo_candle:
        candle, ts = ultimo_candle[ativo]
        if (agora - ts).seconds < 60:
            return candle
    candle = candle_yf(ativo) if USE_YFINANCE else twelve_api_candle(ativo)
    if candle:
        ultimo_candle[ativo] = (candle, agora)
    return candle

def gerar_sinal(candle):
    if not candle:
        return None
    open_p = float(candle["open"])
    close_p = float(candle["close"])
    if close_p > open_p:
        return "CALL"
    elif close_p < open_p:
        return "PUT"
    else:
        return None

def salvar_historico(h):
    for entry in h:
        for key in ["analisada", "entrada"]:
            if isinstance(entry.get(key), datetime):
                entry[key] = entry[key].strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORICO_FILE, "w") as f:
        json.dump(h, f, indent=2)

def checar_resultado(sinal):
    candle = twelve_api_candle_cache(sinal["ativo"])
    if not candle:
        return None
    close_p = float(candle["close"])
    open_p = float(candle["open"])
    if sinal["tipo"] == "CALL":
        return "💚 Green" if close_p > open_p else "🔴 Red"
    else:
        return "💚 Green" if close_p < open_p else "🔴 Red"

def candle_fechado(candle):
    """Verifica se candle já fechou"""
    agora = datetime.now(timezone.utc)
    return agora >= candle["time"] + timedelta(minutes=1)

# ===============================
# LOOP PRINCIPAL
# ===============================
green_seq = 0
total = 0
acertos = 0
erros = 0
ultimo_status = datetime.now(timezone.utc) - timedelta(minutes=STATUS_INTERVAL)

print("🤖 Troia Bot IA iniciado!")

while True:
    agora = datetime.now(timezone.utc)

    # 1️⃣ Mensagem periódica de status
    if (agora - ultimo_status).seconds >= STATUS_INTERVAL * 60:
        try:
            bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
        except Exception as e:
            print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # 2️⃣ Checa sinais pendentes
    sinal_atual = next((h for h in historico if h["resultado"] == "PENDENTE"), None)
    if sinal_atual:
        candle = twelve_api_candle_cache(sinal_atual["ativo"])
        if candle and candle_fechado(candle):
            resultado = checar_resultado(sinal_atual)
            if resultado:
                sinal_atual["resultado"] = resultado
                salvar_historico(historico)
                total += 1
                if "Green" in resultado:
                    acertos += 1
                    green_seq += 1
                else:
                    erros += 1
                    green_seq = 0
                # envia resultado
                try:
                    msg = f"📊 *RESULTADO DO SINAL*\nAtivo: `{sinal_atual['ativo']}`\nTipo: *{sinal_atual['tipo']}*\nResultado: {resultado}\n💚 Green Seq: {green_seq}\n📈 Total: {total} | Acertos: {acertos} | Erros: {erros}"
                    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"Erro Telegram resultado: {e}")
        time.sleep(5)
        continue

    # 3️⃣ Analisa ativos e gera novos sinais
    for ativo in ATIVOS:
        candle = twelve_api_candle_cache(ativo)
        if candle and candle_fechado(candle):
            sinal_tipo = gerar_sinal(candle)
            if sinal_tipo:
                agora = datetime.now(timezone.utc)
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
                try:
                    emoji = "📈" if sinal_tipo == "CALL" else "📉"
                    msg = f"📊 *TROIA BOT IA - NOVO SINAL*\nAtivo: `{ativo}` {emoji}\nTipo: *{sinal_tipo}*\nEntrada: `{entrada.strftime('%H:%M')}`"
                    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"Erro Telegram novo sinal: {e}")
                break  # apenas 1 sinal por loop

    time.sleep(10)
