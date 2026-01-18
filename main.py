import requests
import json
import time
from datetime import datetime, timedelta, timezone
import telebot
import yfinance as yf

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"  # seu token
CHAT_ID = "2055716345"  # seu chat id
STATUS_INTERVAL = 5  # minutos entre mensagens de "bot ativo"
USE_YFINANCE = True  # estamos usando yfinance

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "NZD/USD",
    "EUR/JPY", "GBP/JPY", "EUR/GBP",
    "BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD", "SOL/USD", "XRP/USD"
]

# Símbolos corretos para yfinance
YF_SYMBOLS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "NZD/USD": "NZDUSD=X",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "EUR/GBP": "EURGBP=X",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "BNB/USD": "BNB-USD",
    "ADA/USD": "ADA-USD",
    "SOL/USD": "SOL-USD",
    "XRP/USD": "XRP-USD"
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
        symbol = YF_SYMBOLS[ativo]
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            last = data.iloc[-1]
            time_candle = last.name.to_pydatetime().replace(tzinfo=timezone.utc)
            return {"open": float(last["Open"]), "close": float(last["Close"]), "time": time_candle}
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
    return None

def candle_cache(ativo):
    agora = datetime.now(timezone.utc)
    if ativo in ultimo_candle:
        candle, ts = ultimo_candle[ativo]
        if (agora - ts).total_seconds() < 60:
            return candle
    candle = candle_yf(ativo)
    if candle:
        ultimo_candle[ativo] = (candle, agora)
    return candle

def gerar_sinal(candle):
    if not candle:
        return None
    if candle["close"] > candle["open"]:
        return "CALL"
    elif candle["close"] < candle["open"]:
        return "PUT"
    return None

def salvar_historico():
    h = historico.copy()
    for entry in h:
        for key in ["analisada", "entrada"]:
            if isinstance(entry.get(key), datetime):
                entry[key] = entry[key].strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORICO_FILE, "w") as f:
        json.dump(h, f, indent=2)

def candle_fechado(candle):
    agora = datetime.now(timezone.utc)
    return agora >= candle["time"] + timedelta(minutes=1)

def checar_resultado(sinal):
    agora = datetime.now(timezone.utc)
    if agora < sinal["entrada"] + timedelta(minutes=1):
        return None
    candle = candle_cache(sinal["ativo"])
    if not candle:
        return None
    if sinal["tipo"] == "CALL":
        return "Green" if candle["close"] > candle["open"] else "Red"
    else:
        return "Green" if candle["close"] < candle["open"] else "Red"

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

    # 1️⃣ Mensagem periódica (bot ativo)
    if (agora - ultimo_status).total_seconds() >= STATUS_INTERVAL*60:
        try:
            bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
        except Exception as e:
            print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # 2️⃣ Checa se há sinal pendente
    sinal_atual = next((h for h in historico if h["resultado"] == "PENDENTE"), None)

    if sinal_atual:
        entrada = sinal_atual["entrada"]
        if isinstance(entrada, str):
            entrada = datetime.strptime(entrada, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        resultado = checar_resultado({**sinal_atual, "entrada": entrada})
        if resultado:
            sinal_atual["resultado"] = resultado
            salvar_historico()
            total += 1
            if resultado == "Green":
                acertos += 1
                green_seq += 1
            else:
                erros += 1
                green_seq = 0
            # envia resultado
            msg = (
                f"📊 **RESULTADO DO SINAL**\n"
                f"{sinal_atual['ativo']}: {sinal_atual['tipo']}\n"
                f"Resultado: {resultado}\n"
                f"💚 Green Seq: {green_seq}\n"
                f"📈 Total: {total} | Acertos: {acertos} | Erros: {erros}\n"
                f"⏰ Hora do resultado: {datetime.now().strftime('%H:%M:%S')}"
            )
            try:
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram resultado: {e}")
        time.sleep(5)
        continue  # só processa o próximo sinal após resultado

    # 3️⃣ Analisa todos os ativos e gera **apenas 1 sinal por vez**
    for ativo in ATIVOS:
        candle = candle_cache(ativo)
        if candle and candle_fechado(candle):
            sinal_tipo = gerar_sinal(candle)
            if sinal_tipo:
                entrada = candle["time"] + timedelta(minutes=1)
                novo_sinal = {
                    "ativo": ativo,
                    "tipo": sinal_tipo,
                    "analisada": datetime.now(timezone.utc),
                    "entrada": entrada,
                    "resultado": "PENDENTE"
                }
                historico.append(novo_sinal)
                salvar_historico()
                msg = (
                    f"📊 **NOVO SINAL TROIA-IA**\n"
                    f"{ativo}: {sinal_tipo}\n"
                    f"⏰ Entrada: {entrada.astimezone().strftime('%H:%M:%S')}\n"
                    f"✅ Apenas 1 sinal ativo por vez"
                )
                try:
                    bot.send_message(CHAT_ID, msg)
                except Exception as e:
                    print(f"Erro Telegram novo sinal: {e}")
                break  # só 1 sinal por loop

    time.sleep(5)
