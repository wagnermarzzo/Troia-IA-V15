import time
import telebot
import yfinance as yf
from datetime import datetime, timedelta
import pytz

# ===============================
# CONFIGURAÇÃO TELEGRAM
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# TIMEZONE
# ===============================
TZ = pytz.timezone("America/Sao_Paulo")

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X",
    "EURJPY=X", "GBPJPY=X", "EURGBP=X"
]

# ===============================
# ESTADO GLOBAL (1 SINAL)
# ===============================
estado = {
    "ativo": None,
    "tipo": None,
    "candle_analise": None,
    "candle_entrada": None
}

# ===============================
# FUNÇÕES
# ===============================
def get_candle(symbol):
    df = yf.download(symbol, period="1d", interval="1m", progress=False)
    if df.empty:
        return None

    last = df.iloc[-1]
    time_candle = last.name

    if time_candle.tzinfo is None:
        time_candle = pytz.utc.localize(time_candle)

    return {
        "open": float(last["Open"]),
        "close": float(last["Close"]),
        "time": time_candle.astimezone(TZ)
    }

def enviar_sinal(ativo, tipo, entrada):
    bot.send_message(
        CHAT_ID,
        f"📊 *TROIA IA — SINAL*\n"
        f"Ativo: `{ativo.replace('=X','')}`\n"
        f"Direção: *{tipo}*\n"
        f"Entrada: *{entrada.strftime('%H:%M')}*\n"
        f"Timeframe: 1M",
        parse_mode="Markdown"
    )

def enviar_resultado(ativo, tipo, resultado):
    bot.send_message(
        CHAT_ID,
        f"📈 *RESULTADO — TROIA IA*\n"
        f"Ativo: `{ativo.replace('=X','')}`\n"
        f"Sinal: *{tipo}*\n"
        f"Resultado: *{resultado}*",
        parse_mode="Markdown"
    )

# ===============================
# START
# ===============================
print("🤖 Troia Bot IA iniciado!")

while True:
    try:
        agora = datetime.now(TZ)

        # ==================================
        # SE NÃO HÁ SINAL → ANALISA ATIVOS
        # ==================================
        if estado["ativo"] is None:
            for ativo in ATIVOS:
                candle = get_candle(ativo)
                if not candle:
                    continue

                tipo = "CALL" if candle["close"] > candle["open"] else "PUT"
                entrada = candle["time"] + timedelta(minutes=1)

                estado.update({
                    "ativo": ativo,
                    "tipo": tipo,
                    "candle_analise": candle["time"],
                    "candle_entrada": entrada
                })

                enviar_sinal(ativo, tipo, entrada)
                break

        # ==================================
        # AGUARDA CANDLE DA ENTRADA FECHAR
        # ==================================
        else:
            candle = get_candle(estado["ativo"])
            if candle and candle["time"] > estado["candle_entrada"]:
                resultado = (
                    "GREEN"
                    if (estado["tipo"] == "CALL" and candle["close"] > candle["open"]) or
                       (estado["tipo"] == "PUT" and candle["close"] < candle["open"])
                    else "RED"
                )

                enviar_resultado(estado["ativo"], estado["tipo"], resultado)

                estado = {
                    "ativo": None,
                    "tipo": None,
                    "candle_analise": None,
                    "candle_entrada": None
                }

        time.sleep(10)

    except Exception as e:
        print("Erro:", e)
        time.sleep(10)
