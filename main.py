import requests
import json
import time
from datetime import datetime, timedelta, timezone
import telebot

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"  # seu token
CHAT_ID = "2055716345"  # seu chat_id
USE_YFINANCE = True
STATUS_INTERVAL = 5  # minutos entre mensagem "bot ativo"
PROB_THRESHOLD = 60  # percentual histórico para entrada segura

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# ATIVOS (YFinance atualizado)
# ===============================
ATIVOS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X",
    "EURJPY=X", "GBPJPY=X", "EURGBP=X",
    "BTC-USD", "ETH-USD", "BNB-USD", "ADA-USD", "SOL-USD", "XRP-USD"
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
ultimo_candle = {}  # ativo -> (candle, timestamp)

# ===============================
# FUNÇÕES
# ===============================
def candle_yf(ativo):
    try:
        import yfinance as yf
        data = yf.download(ativo, period="1d", interval="1m", progress=False)
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
        if (agora - ts).seconds < 60:
            return candle
    candle = candle_yf(ativo) if USE_YFINANCE else None
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

def candle_fechado(candle):
    return datetime.now(timezone.utc) >= candle["time"] + timedelta(minutes=1)

def salvar_historico(h):
    for entry in h:
        for key in ["analisada", "entrada"]:
            if isinstance(entry.get(key), datetime):
                entry[key] = entry[key].strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORICO_FILE, "w") as f:
        json.dump(h, f, indent=2)

def checar_resultado(sinal):
    candle = candle_cache(sinal["ativo"])
    if not candle or not candle_fechado(candle):
        return None
    close_p = float(candle["close"])
    open_p = float(candle["open"])
    if sinal["tipo"] == "CALL":
        return "Green" if close_p > open_p else "Red"
    else:
        return "Green" if close_p < open_p else "Red"

def calcular_probabilidade(ativo, tipo):
    total = sum(1 for s in historico if s["ativo"] == ativo and s["tipo"] == tipo and s["resultado"] != "PENDENTE")
    green = sum(1 for s in historico if s["ativo"] == ativo and s["tipo"] == tipo and s["resultado"] == "Green")
    if total == 0:
        return 0
    return int((green / total) * 100)

# ===============================
# LOOP PRINCIPAL
# ===============================
ultimo_status = datetime.now(timezone.utc) - timedelta(minutes=STATUS_INTERVAL)
green_seq = 0
total = 0
acertos = 0
erros = 0

print("🤖 Troia Bot IA iniciado!")

while True:
    agora = datetime.now(timezone.utc)

    # 🔹 Status periódico
    if (agora - ultimo_status).seconds >= STATUS_INTERVAL * 60:
        try:
            bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
        except Exception as e:
            print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # 🔹 Checa sinal pendente
    sinal_atual = next((s for s in historico if s["resultado"] == "PENDENTE"), None)
    if sinal_atual:
        resultado = checar_resultado(sinal_atual)
        if resultado:
            sinal_atual["resultado"] = resultado
            salvar_historico(historico)

            total += 1
            if resultado == "Green":
                acertos += 1
                green_seq += 1
            else:
                erros += 1
                green_seq = 0

            prob = calcular_probabilidade(sinal_atual["ativo"], sinal_atual["tipo"])
            destaque = "💥 ENTRADA SEGURA!" if prob >= PROB_THRESHOLD else ""

            try:
                msg = (
                    f"📊 **RESULTADO DO SINAL** {destaque}\n"
                    f"Ativo: {sinal_atual['ativo']}\n"
                    f"Tipo: {sinal_atual['tipo']}\n"
                    f"Resultado: {resultado}\n"
                    f"Probabilidade histórica: {prob}%\n"
                    f"💚 Green Seq: {green_seq}\n"
                    f"📈 Total: {total} | ✅ Acertos: {acertos} | ❌ Erros: {erros}"
                )
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram resultado: {e}")

        time.sleep(10)
        continue

    # 🔹 Nenhum sinal pendente → gerar próximo sinal (1 por vez)
    for ativo in ATIVOS:
        if any(s for s in historico if s["ativo"] == ativo and s["resultado"] == "PENDENTE"):
            continue

        candle = candle_cache(ativo)
        if not candle:
            continue

        sinal_tipo = gerar_sinal(candle)
        if sinal_tipo:
            entrada = candle["time"] + timedelta(minutes=1)  # próximo candle
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
                msg = (
                    f"📊 **NOVO SINAL TROIA BOT IA** {destaque}\n"
                    f"Ativo: {ativo}\n"
                    f"Tipo: {sinal_tipo}\n"
                    f"Entrada (próximo candle): {entrada.strftime('%H:%M')}\n"
                    f"Probabilidade histórica: {prob}%"
                )
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram novo sinal: {e}")

            break  # ⚠️ somente 1 sinal por vez

    time.sleep(10)
