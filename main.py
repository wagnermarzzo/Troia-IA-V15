import requests
import json
import time
from datetime import datetime, timedelta, timezone
import telebot
import yfinance as yf

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"
STATUS_INTERVAL = 5  # minutos entre mensagens de status

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
    "EUR/USD":"EURUSD=X", "GBP/USD":"GBPUSD=X", "USD/JPY":"USDJPY=X",
    "AUD/USD":"AUDUSD=X", "NZD/USD":"NZDUSD=X", "EUR/JPY":"EURJPY=X",
    "GBP/JPY":"GBPJPY=X", "EUR/GBP":"EURGBP=X",
    "BTC/USD":"BTC-USD", "ETH/USD":"ETH-USD", "BNB/USD":"BNB-USD",
    "ADA/USD":"ADA-USD", "SOL/USD":"SOL-USD", "XRP/USD":"XRP-USD"
}

# ===============================
# HISTÓRICO
# ===============================
HISTORICO_FILE = "historico.json"
try:
    with open(HISTORICO_FILE, "r") as f:
        historico = json.load(f)
        # Corrige datetime de strings
        for h in historico:
            for key in ["analisada", "entrada"]:
                if key in h and isinstance(h[key], str):
                    h[key] = datetime.fromisoformat(h[key])
except FileNotFoundError:
    historico = []

# ===============================
# FUNÇÕES
# ===============================
def candle_yf(ativo):
    symbol = YF_SYMBOLS[ativo]
    try:
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            last = data.iloc[-1]
            open_p = float(last["Open"])
            close_p = float(last["Close"])
            time_candle = last.name.to_pydatetime().replace(tzinfo=timezone.utc)
            return {"open": open_p, "close": close_p, "time": time_candle}
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
    return None

def candle_fechado(candle):
    agora = datetime.now(timezone.utc)
    return agora >= candle["time"] + timedelta(minutes=1)

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

def salvar_historico():
    to_save = []
    for entry in historico:
        save_entry = entry.copy()
        for key in ["analisada", "entrada"]:
            if isinstance(save_entry.get(key), datetime):
                save_entry[key] = save_entry[key].isoformat()
        to_save.append(save_entry)
    with open(HISTORICO_FILE, "w") as f:
        json.dump(to_save, f, indent=2)

def enviar_sinal_telegram(sinal):
    entrada_local = sinal["entrada"].astimezone() if isinstance(sinal["entrada"], datetime) else datetime.now()
    msg = (
        f"📊 **TROIA BOT IA - NOVO SINAL**\n"
        f"Ativo: {sinal['ativo']}\n"
        f"Tipo: {sinal['tipo']}\n"
        f"Entrada: {entrada_local.strftime('%H:%M')}\n"
        f"Probabilidade: {sinal.get('probabilidade','?')}%"
    )
    bot.send_message(CHAT_ID, msg)

def enviar_resultado_telegram(sinal, resultado, green_seq, total, acertos, erros):
    msg = (
        f"📊 **RESULTADO DO SINAL**\n"
        f"{sinal['ativo']}: {sinal['tipo']}\n"
        f"Resultado: {resultado}\n"
        f"💚 Green Seq: {green_seq}\n"
        f"📈 Total: {total} | Acertos: {acertos} | Erros: {erros}"
    )
    bot.send_message(CHAT_ID, msg)

def checar_resultado(sinal):
    candle = candle_yf(sinal["ativo"])
    if not candle:
        return None
    # só verifica resultado após a vela de entrada fechar
    agora = datetime.now(timezone.utc)
    if agora < sinal["entrada"] + timedelta(minutes=1):
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
green_seq = 0
total = 0
acertos = 0
erros = 0
ultimo_status = datetime.now(timezone.utc) - timedelta(minutes=STATUS_INTERVAL)

print("🤖 Troia Bot IA iniciado!")

while True:
    agora = datetime.now(timezone.utc)

    # 1️⃣ Status periódico
    if (agora - ultimo_status).total_seconds() >= STATUS_INTERVAL*60:
        try:
            bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
        except Exception as e:
            print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # 2️⃣ Checa se existe sinal pendente
    sinal_atual = next((h for h in historico if h["resultado"]=="PENDENTE"), None)
    if sinal_atual:
        resultado = checar_resultado(sinal_atual)
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
            try:
                enviar_resultado_telegram(sinal_atual, resultado, green_seq, total, acertos, erros)
            except Exception as e:
                print(f"Erro Telegram resultado: {e}")
        time.sleep(5)
        continue  # só processa 1 sinal por vez

    # 3️⃣ Gera novo sinal apenas se não há sinal pendente
    for ativo in ATIVOS:
        candle = candle_yf(ativo)
        if not candle or not candle_fechado(candle):
            continue
        sinal_tipo = gerar_sinal(candle)
        if sinal_tipo:
            # entrada na próxima vela
            entrada = candle["time"] + timedelta(minutes=1)
            novo_sinal = {
                "ativo": ativo,
                "tipo": sinal_tipo,
                "analisada": agora,
                "entrada": entrada,
                "resultado": "PENDENTE",
                "probabilidade": 60
            }
            historico.append(novo_sinal)
            salvar_historico()
            try:
                enviar_sinal_telegram(novo_sinal)
            except Exception as e:
                print(f"Erro Telegram novo sinal: {e}")
            break  # apenas 1 sinal por loop

    time.sleep(10)
