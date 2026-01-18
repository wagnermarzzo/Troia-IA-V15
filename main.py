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

# Lista de ativos válidos Binance Spot
ATIVOS = [
    "EURUSDT", "GBPUSDT", "AUDUSDT", "NZDUSDT",
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT",
    "SOLUSDT", "XRPUSDT"
]

INTERVALO = 60  # segundos
TIMEFRAME = "1m"
MOVIMENTO_MINIMO = 0.0005

# Estatísticas globais
stats = {
    "green_seq": 0
}

# Últimos sinais de cada ativo
sinais_ativos = {ativo: {"sinal": None, "forca": None, "prob": None, "resultado": "🟡"} for ativo in ATIVOS}

# ===============================
# PEGAR CANDLES
# ===============================
def pegar_candles(ativo, limite=3):
    url = f"https://api.binance.com/api/v3/klines?symbol={ativo}&interval={TIMEFRAME}&limit={limite}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        
        if not isinstance(data, list):
            print(f"Erro API Binance {ativo}: {data}")
            return []

        candles = []
        for c in data:
            if isinstance(c, list) and len(c) >= 5:
                try:
                    candles.append({
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "time": datetime.datetime.fromtimestamp(int(c[0])/1000).strftime('%Y-%m-%d %H:%M:%S')
                    })
                except:
                    continue
        return candles
    except Exception as e:
        print(f"Erro ao pegar candles {ativo}: {e}")
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
    else:
        return None, None, 0

    # Probabilidade simples baseada nos últimos 3 candles
    prob = 50
    if (direcao == "CALL" and prev1["close"] > prev1["open"] and prev2["close"] > prev2["open"]) or \
       (direcao == "PUT" and prev1["close"] < prev1["open"] and prev2["close"] < prev2["open"]):
        prob = 80 if forca == "Forte" else 70
    elif forca == "Médio":
        prob = 60

    return direcao, forca, prob

# ===============================
# CHECAR RESULTADO VELA
# ===============================
def checar_resultados():
    for ativo in ATIVOS:
        candles = pegar_candles(ativo, limite=2)
        if len(candles) < 2:
            continue
        vela = candles[-1]
        if vela["close"] > vela["open"]:
            resultado = "🟢 GREEN"
            stats["green_seq"] += 1
        else:
            resultado = "🔴 RED"
            stats["green_seq"] = 0
        sinais_ativos[ativo]["resultado"] = resultado

# ===============================
# ENVIAR PAINEL DE SINAIS
# ===============================
def enviar_sinais():
    mensagem = "📊 **TROIA BOT IA - SINAIS**\n\n"
    for ativo, info in sinais_ativos.items():
        sinal = info["sinal"] if info["sinal"] else "—"
        forca = info["forca"] if info["forca"] else "—"
        prob = f"{info['prob']}%" if info["prob"] else "—"
        resultado = info["resultado"]
        mensagem += f"{ativo}: Sinal={sinal} | Força={forca} | Prob={prob} | Resultado={resultado}\n"
    mensagem += f"\n💚 Green Seq: {stats['green_seq']}"
    bot.send_message(CHAT_ID, mensagem)
    print(mensagem)

# ===============================
# LOOP PRINCIPAL
# ===============================
print("Troia Bot IA iniciado...")
while True:
    # Analisar sinais para cada ativo
    for ativo in ATIVOS:
        candles = pegar_candles(ativo, limite=3)
        if candles:
            direcao, forca, prob = analisar_candles(candles)
            if direcao:
                sinais_ativos[ativo]["sinal"] = direcao
                sinais_ativos[ativo]["forca"] = forca
                sinais_ativos[ativo]["prob"] = prob

    # Checar resultados das velas reais
    checar_resultados()
    # Enviar painel limpo de sinais
    enviar_sinais()
    time.sleep(INTERVALO)
