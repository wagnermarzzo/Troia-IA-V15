import requests
import json
import time
from datetime import datetime, timedelta
import telebot

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"
API_KEY = "128da1172fbb4aef83ca801cb3e6b928"
USE_YFINANCE = True  # True = usa Yahoo Finance (sem limite), False = usa Twelve Data

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
ultimo_candle = {}  # chave = ativo, valor = (candle, timestamp)

# ===============================
# FUNÇÕES
# ===============================
def twelve_api_candle(ativo):
    """Pega candle mais recente da Twelve Data"""
    symbol = ativo.replace("/", "")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&apikey={API_KEY}&outputsize=2"
    try:
        resp = requests.get(url, timeout=10).json()
        if "values" in resp:
            return resp["values"][0]  # candle mais recente
        else:
            print(f"Erro API Twelve Data {ativo}: {resp}")
            return None
    except Exception as e:
        print(f"Erro requisição {ativo}: {e}")
        return None

def candle_yf(ativo):
    """Usa Yahoo Finance para pegar candle (sem limite diário)"""
    try:
        import yfinance as yf
        symbol = ativo.replace("/", "") + "=X"
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            last = data.iloc[-1]
            return {"open": last["Open"], "close": last["Close"]}
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
    return None

def twelve_api_candle_cache(ativo):
    """Cache de candle por ativo, atualiza a cada 60s"""
    agora = datetime.now()
    if ativo in ultimo_candle:
        candle, ts = ultimo_candle[ativo]
        if (agora - ts).seconds < 60:
            return candle
    # consulta API
    candle = candle_yf(ativo) if USE_YFINANCE else twelve_api_candle(ativo)
    if candle:
        ultimo_candle[ativo] = (candle, agora)
    return candle

def gerar_sinal(candle):
    """Exemplo simples de Price Action: fechamento acima abertura = CALL"""
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
    """Salva histórico convertendo datetime para string"""
    for entry in h:
        for key in ["analisada", "entrada"]:
            if isinstance(entry.get(key), datetime):
                entry[key] = entry[key].strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORICO_FILE, "w") as f:
        json.dump(h, f, indent=2)

def checar_resultado(sinal):
    """Verifica resultado da vela de entrada"""
    candle = twelve_api_candle_cache(sinal["ativo"])
    if not candle:
        return None
    close_p = float(candle["close"])
    open_p = float(candle["open"])
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

print("🤖 Troia Bot IA iniciado!")

while True:
    # 1️⃣ Checa sinais pendentes
    sinal_atual = next((h for h in historico if h["resultado"] == "PENDENTE"), None)

    if sinal_atual:
        agora = datetime.now()
        entrada = datetime.strptime(sinal_atual["entrada"], "%Y-%m-%d %H:%M:%S") \
            if isinstance(sinal_atual["entrada"], str) else sinal_atual["entrada"]
        if agora >= entrada:
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
                msg = f"📊 **RESULTADO DO SINAL**\n\n"
                msg += f"{sinal_atual['ativo']}: {sinal_atual['tipo']}\n"
                msg += f"Resultado: {resultado}\n"
                msg += f"💚 Green Seq: {green_seq}\n"
                msg += f"📈 Total: {total} | Acertos: {acertos} | Erros: {erros}\n"
                try:
                    bot.send_message(CHAT_ID, msg)
                except Exception as e:
                    print(f"Erro Telegram: {e}")
        else:
            print(f"Aguardando entrada de {sinal_atual['ativo']}...")
        time.sleep(10)
        continue

    # 2️⃣ Se não tiver sinal pendente, analisa novos ativos
    for ativo in ATIVOS:
        candle = twelve_api_candle_cache(ativo)
        sinal_tipo = gerar_sinal(candle)
        if sinal_tipo:
            agora = datetime.now()
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
            total += 1
            msg = f"📊 **TROIA BOT IA - SINAL ÚNICO**\n\n"
            msg += f"{ativo}: 📈 {sinal_tipo}\n"
            msg += f"⏱ Analisada: {agora.strftime('%H:%M')}\n"
            msg += f"⏱ Entrada: {entrada.strftime('%H:%M')}\n"
            msg += f"Resultado: 🟡 PENDENTE\n"
            msg += f"💚 Green Seq: {green_seq}\n"
            msg += f"📈 Total: {total} | Acertos: {acertos} | Erros: {erros}\n"
            try:
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram: {e}")
            break  # só gera 1 sinal por loop

    time.sleep(30)  # evita flood e excesso de chamadas
