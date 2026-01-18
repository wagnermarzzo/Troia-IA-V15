import requests
import time
import telebot
import datetime

# ===============================
# CONFIGURAÇÃO FIXA
# ===============================
TOKEN = "8536239572:AAG82o0mJw9WP3RKGrJTaLp-Hl2q8Gx6HYY"
CHAT_ID = "2055716345"
API_KEY = "128da1172fbb4aef83ca801cb3e6b928"
bot = telebot.TeleBot(TOKEN, threaded=False)

# Lista de ativos válidos em Twelve Data
ATIVOS = [
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
    "BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD",
    "SOL/USD", "XRP/USD"
]

INTERVALO = 60  # segundos
MOVIMENTO_MINIMO = 0.0005

# Estatísticas globais
stats = {"green_seq": 0}

# Últimos sinais de cada ativo
sinais_ativos = {ativo: {"sinal": None, "forca": None, "prob": None, "resultado": "🟡"} for ativo in ATIVOS}

# ===============================
# PEGAR CANDLES
# ===============================
def pegar_candles(ativo, limite=3):
    url = f"https://api.twelvedata.com/time_series?symbol={ativo}&interval=1min&apikey={API_KEY}&outputsize={limite}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if "values" not in data:
            print(f"Erro API Twelve Data {ativo}: {data}")
            return []

        candles = []
        for c in reversed(data["values"]):
            try:
                candles.append({
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "time": c["datetime"]
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
    ultimo, prev1, prev2 = candles[-1], candles[-2], candles[-3]

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
print("Troia Bot IA iniciado com Twelve Data...")
while True:
    for ativo in ATIVOS:
        candles = pegar_candles(ativo, limite=3)
        if candles:
            direcao, forca, prob = analisar_candles(candles)
            if direcao:
                sinais_ativos[ativo]["sinal"] = direcao
                sinais_ativos[ativo]["forca"] = forca
                sinais_ativos[ativo]["prob"] = prob

    checar_resultados()
    enviar_sinais()
    time.sleep(INTERVALO)
