import requests
import json
import time
from datetime import datetime, timedelta, timezone
import telebot
import yfinance as yf

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"  # SEU TOKEN
CHAT_ID = "2055716345"  # SEU CHAT ID
STATUS_INTERVAL = 5  # minutos entre mensagens de "bot ativo"
PROB_THRESHOLD = 60  # destaque se probabilidade histórica >= 60%

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
except FileNotFoundError:
    historico = []

# ===============================
# CACHE DE CANDLES
# ===============================
ultimo_candle = {}  # chave=ativo, valor=(candle, timestamp)

# ===============================
# FUNÇÕES
# ===============================
def candle_cache(ativo):
    agora = datetime.now(timezone.utc)
    if ativo in ultimo_candle:
        candle, ts = ultimo_candle[ativo]
        if (agora - ts).seconds < 60:
            return candle
    symbol = YF_SYMBOLS[ativo]
    try:
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if data.empty:
            return None
        last = data.iloc[-1]
        time_candle = last.name.to_pydatetime().replace(tzinfo=timezone.utc)
        candle = {
            "open": float(last["Open"]),
            "close": float(last["Close"]),
            "time": time_candle
        }
        ultimo_candle[ativo] = (candle, agora)
        return candle
    except Exception as e:
        print(f"Erro yfinance {ativo}: {e}")
        return None

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

def calcular_probabilidade(ativo, tipo):
    historico_ativo = [h for h in historico if h["ativo"]==ativo and h["tipo"]==tipo and h["resultado"] in ["Green","Red"]]
    if not historico_ativo:
        return 0
    greens = sum(1 for h in historico_ativo if h["resultado"]=="Green")
    return round(greens/len(historico_ativo)*100,2)

def checar_resultado(sinal):
    agora = datetime.now(timezone.utc)
    # espera candle de entrada fechar
    if agora < sinal["entrada"] + timedelta(minutes=1):
        return None
    candle = candle_cache(sinal["ativo"])
    if not candle:
        return None
    open_p = candle["open"]
    close_p = candle["close"]
    if sinal["tipo"] == "CALL":
        return "Green" if close_p > open_p else "Red"
    else:
        return "Green" if close_p < open_p else "Red"

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

    # Mensagem de status
    if (agora - ultimo_status).seconds >= STATUS_INTERVAL*60:
        try:
            bot.send_message(CHAT_ID, "🤖 TROIA BOT IA está ativo e analisando os ativos...")
        except Exception as e:
            print(f"Erro Telegram status: {e}")
        ultimo_status = agora

    # Checa sinal pendente
    sinal_atual = next((s for s in historico if s["resultado"]=="PENDENTE"), None)
    if sinal_atual:
        resultado = checar_resultado(sinal_atual)
        if resultado:
            sinal_atual["resultado"] = resultado
            salvar_historico(historico)
            total +=1
            if resultado=="Green":
                acertos+=1
                green_seq+=1
            else:
                erros+=1
                green_seq=0
            prob = calcular_probabilidade(sinal_atual["ativo"], sinal_atual["tipo"])
            destaque = "💥 ENTRADA SEGURA!" if prob>=PROB_THRESHOLD else ""
            try:
                msg = f"""📊 **RESULTADO DO SINAL** {destaque}
{sinal_atual['ativo']}: {sinal_atual['tipo']}
Resultado: {resultado}
Probabilidade histórica: {prob}%
💚 Green Seq: {green_seq}
📈 Total: {total} | Acertos: {acertos} | Erros: {erros}"""
                bot.send_message(CHAT_ID, msg)
            except Exception as e:
                print(f"Erro Telegram resultado: {e}")
        time.sleep(10)
        continue

    # Nenhum sinal pendente → analisa todos ativos e gera próximo sinal
    for ativo in ATIVOS:
        if any(s for s in historico if s["ativo"]==ativo and s["resultado"]=="PENDENTE"):
            continue
        candle = candle_cache(ativo)
        if not candle:
            continue
        sinal_tipo = gerar_sinal(candle)
        if sinal_tipo:
            # entrada é o próximo candle
            proximo_minuto = (candle["time"] + timedelta(minutes=1)).replace(second=0,microsecond=0)
            novo_sinal = {
                "ativo": ativo,
                "tipo": sinal_tipo,
                "analisada": agora,
                "entrada": proximo_minuto,
                "resultado": "PENDENTE"
            }
            historico.append(novo_sinal)
            salvar_historico(historico)
            prob = calcular_probabilidade(ativo,sinal_tipo)
            destaque = "💥 ENTRADA SEGURA!" if prob>=PROB_THRESHOLD else ""
            try:
                msg = f"""📊 **TROIA BOT IA - NOVO SINAL** {destaque}
{ativo}: {sinal_tipo}
Entrada (candle): {proximo_minuto.strftime('%H:%M')}
Probabilidade histórica: {prob}%"""
                bot.send_message(CHAT_ID,msg)
            except Exception as e:
                print(f"Erro Telegram novo sinal: {e}")
            break  # somente 1 sinal por vez

    time.sleep(10)
