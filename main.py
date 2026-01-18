import requests
import json
import time
from datetime import datetime, timedelta
import telebot
import yfinance as yf
import pytz

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"
STATUS_INTERVAL = 5  # minutos entre mensagens de "bot ativo"
LOCAL_TZ = pytz.timezone("America/Sao_Paulo")  # fuso horário local

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X",
    "EURJPY=X", "GBPJPY=X", "EURGBP=X"
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

# Converte strings do histórico para datetime
for entry in historico:
    for key in ["analisada", "entrada"]:
        if isinstance(entry.get(key), str):
            entry[key] = LOCAL_TZ.localize(datetime.strptime(entry[key], "%Y-%m-%d %H:%M:%S"))

# ===============================
# CACHE DE CANDLES
# ===============================
ultimo_candle = {}  # chave = ativo, valor = (candle, timestamp)

# ===============================
# FUNÇÕES
# ===============================
def candle_yf(ativo):
    try:
        data = yf.download(ativo, period="1d", interval="1m", progress=False)
        if not data.empty:
            last = data.iloc[-1]
            time_candle = last.name.to_pydatetime().replace(tzinfo=pytz.UTC)
            return {
                "open": float(last["Open"].iloc[0]) if hasattr(last["Open"], "iloc") else float(last["Open"]),
                "close": float(last["Close"].iloc[0]) if hasattr(last["Close"], "iloc") else float(last["Close"]),
                "time": time_candle
            }
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
    return None

def candle_yf_cache(ativo):
    agora = datetime.now(LOCAL_TZ)
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
    open_p = candle["open"]
    close_p = candle["close"]
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
    candle = candle_yf_cache(sinal["ativo"])
    if not candle:
        return None
    close_p = candle["close"]
    open_p = candle["open"]
    if sinal["tipo"] == "CALL":
        return "Green" if close_p > open_p else "Red"
    else:
        return "Green" if close_p < open_p else "Red"

# ===============================
# LOOP PRINCIPAL
# ===============================
ultimo_status = datetime.now(LOCAL_TZ) - timedelta(minutes=STATUS_INTERVAL)
sinal_ativo = next((h for h in historico if h["resultado"] == "PENDENTE"), None)
green_seq = 0
total = 0
acertos = 0
erros = 0

print("🤖 Troia Bot IA iniciado!")

while True:
    agora = datetime.now(LOCAL_TZ)

    # 1️⃣ Mensagem de status
    if (agora - ultimo_status).total_seconds() >= STATUS_INTERVAL*60:
        if not sinal_ativo:  # só envia status se não houver sinal ativo
            try:
                bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
            except Exception as e:
                print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # 2️⃣ Checar resultado do sinal ativo
    if sinal_ativo:
        # Certifica que "entrada" é datetime
        if isinstance(sinal_ativo["entrada"], str):
            sinal_ativo["entrada"] = LOCAL_TZ.localize(datetime.strptime(sinal_ativo["entrada"], "%Y-%m-%d %H:%M:%S"))

        if agora >= sinal_ativo["entrada"] + timedelta(minutes=1):
            resultado = checar_resultado(sinal_ativo)
            if resultado:
                sinal_ativo["resultado"] = resultado
                salvar_historico(historico)
                total += 1
                if resultado == "Green":
                    acertos += 1
                    green_seq += 1
                else:
                    erros += 1
                    green_seq = 0
                # envia resultado do sinal
                try:
                    msg = (
                        f"📊 **RESULTADO DO SINAL**\n"
                        f"{sinal_ativo['ativo']}: {sinal_ativo['tipo']}\n"
                        f"Resultado: {resultado}\n"
                        f"💚 Green Seq: {green_seq}\n"
                        f"📈 Total: {total} | Acertos: {acertos} | Erros: {erros}"
                    )
                    bot.send_message(CHAT_ID, msg)
                except Exception as e:
                    print(f"Erro Telegram resultado: {e}")
                sinal_ativo = None  # libera para próximo sinal

    # 3️⃣ Se não houver sinal ativo, analisa ativos
    if not sinal_ativo:
        for ativo in ATIVOS:
            candle = candle_yf_cache(ativo)
            sinal_tipo = gerar_sinal(candle)
            if sinal_tipo:
                entrada_utc = candle["time"] + timedelta(minutes=1)
                entrada_local = entrada_utc.astimezone(LOCAL_TZ)
                sinal_ativo = {
                    "ativo": ativo,
                    "tipo": sinal_tipo,
                    "analisada": agora,
                    "entrada": entrada_local,
                    "resultado": "PENDENTE"
                }
                historico.append(sinal_ativo)
                salvar_historico(historico)
                try:
                    msg = (
                        f"📊 **TROIA BOT IA - NOVO SINAL**\n"
                        f"{ativo}: {sinal_tipo}\n"
                        f"Entrada: {entrada_local.strftime('%H:%M')}"
                    )
                    bot.send_message(CHAT_ID, msg)
                except Exception as e:
                    print(f"Erro Telegram novo sinal: {e}")
                break  # apenas 1 sinal por vez

    time.sleep(5)
