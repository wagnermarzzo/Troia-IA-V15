import requests
import time
import telebot
import datetime

# ===============================
# CONFIGURAÇÃO
# ===============================
TOKEN = "8536239572:AAG82o0mJw9WP3RKGrJTaLp-Hl2q8Gx6HYY"
CHAT_ID = "2055716345"
bot = telebot.TeleBot(TOKEN, threaded=False)

ATIVOS = [
    "EURUSDT", "GBPUSDT", "USDJPY", "AUDUSDT", "NZDUSDT",
    "EURJPY", "GBPJPY", "EURGBP",
    "BTCUSDT", "ETHUSDT", "BNBUSDT"
]

INTERVALO = 60  # segundos
TIMEFRAME = "1m"
MOVIMENTO_MINIMO = 0.0005

# Estatísticas globais
stats = {
    "total_sinais": 0,
    "call": 0,
    "put": 0,
    "forte": 0,
    "medio": 0,
    "fraco": 0,
    "alta_prob": 0,
    "green_seq": 0
}

# Últimos sinais para dashboard
dashboard_sinais = {ativo: {"sinal": None, "forca": None, "prob": None, "resultado": "🟡"} for ativo in ATIVOS}

# ===============================
# PEGAR CANDLES
# ===============================
def pegar_candles(ativo, limite=3):
    url = f"https://api.binance.com/api/v3/klines?symbol={ativo}&interval={TIMEFRAME}&limit={limite}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        candles = []
        for c in data:
            candles.append({
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "time": datetime.datetime.fromtimestamp(int(c[0])/1000).strftime('%Y-%m-%d %H:%M:%S')
            })
        return candles
    except Exception as e:
        print("Erro ao pegar candles:", e)
        return []

# ===============================
# ANALISE DE PRICE ACTION
# ===============================
def analisar_candles(candles):
    if len(candles) < 3:
        return None, None, 0
    ultimo = candles[-1]
    prev1 = candles[-2]
    prev2 = candles[-3]

    movimento = abs(ultimo["close"] - ultimo["open"])
    pct_mov = movimento / ultimo["open"]

    if pct_mov < MOVIMENTO_MINIMO:
        return None, None, 0

    if ultimo["close"] > ultimo["open"] and prev1["close"] < prev1["open"]:
        direcao = "CALL"
        forca = "Forte" if pct_mov > 0.002 else "Médio"
    elif ultimo["close"] < ultimo["open"] and prev1["close"] > prev1["open"]:
        direcao = "PUT"
        forca = "Forte" if pct_mov > 0.002 else "Médio"
    elif (ultimo["high"] - max(ultimo["open"], ultimo["close"])) / (ultimo["high"] - ultimo["low"]) > 0.6:
        direcao = "PUT"
        forca = "Médio"
    elif (min(ultimo["open"], ultimo["close"]) - ultimo["low"]) / (ultimo["high"] - ultimo["low"]) > 0.6:
        direcao = "CALL"
        forca = "Médio"
    elif ultimo["high"] < prev1["high"] and ultimo["low"] > prev1["low"]:
        direcao = None
        forca = "Fraco"
    else:
        return None, None, 0

    prob = 50
    if (direcao == "CALL" and prev1["close"] > prev1["open"] and prev2["close"] > prev2["open"]) or \
       (direcao == "PUT" and prev1["close"] < prev1["open"] and prev2["close"] < prev2["open"]):
        prob = 80 if forca == "Forte" else 70
    elif forca == "Médio":
        prob = 60
    else:
        prob = 50

    return direcao, forca, prob

# ===============================
# ATUALIZA DASHBOARD
# ===============================
def atualizar_dashboard():
    mensagem = "📊 **TROIA BOT IA DASHBOARD**\n\n"
    for ativo, info in dashboard_sinais.items():
        sinal = info["sinal"] if info["sinal"] else "—"
        forca = info["forca"] if info["forca"] else "—"
        prob = f"{info['prob']}%" if info["prob"] else "—"
        resultado = info["resultado"]
        mensagem += f"{ativo}: Sinal={sinal} | Força={forca} | Prob={prob} | Resultado={resultado}\n"
    mensagem += f"\n💚 Green Seq: {stats['green_seq']}"
    bot.send_message(CHAT_ID, mensagem)
    print(mensagem)

# ===============================
# CHECAR RESULTADOS E ATUALIZAR DASHBOARD
# ===============================
def checar_resultados():
    for ativo in ATIVOS:
        candles = pegar_candles(ativo, limite=2)
        if len(candles) < 2:
            continue
        vela_resultado = candles[-1]
        # Green/Red baseado na vela real
        if vela_resultado["close"] > vela_resultado["open"]:
            resultado = "🟢 GREEN"
            stats["green_seq"] += 1
        else:
            resultado = "🔴 RED"
            stats["green_seq"] = 0
        dashboard_sinais[ativo]["resultado"] = resultado

# ===============================
# LOOP PRINCIPAL
# ===============================
print("Troia Bot IA Dashboard iniciado...")
while True:
    for ativo in ATIVOS:
        candles = pegar_candles(ativo, limite=3)
        if candles:
            direcao, forca, prob = analisar_candles(candles)
            if direcao:
                # Atualiza dashboard
                dashboard_sinais[ativo]["sinal"] = direcao
                dashboard_sinais[ativo]["forca"] = forca
                dashboard_sinais[ativo]["prob"] = prob
    # Checa resultados das velas reais
    checar_resultados()
    # Envia dashboard completo
    atualizar_dashboard()
    time.sleep(INTERVALO)
