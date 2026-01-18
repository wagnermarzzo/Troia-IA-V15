import requests
import time
import telebot
import json
import os

# ===============================
# CONFIGURAÇÃO FIXA
# ===============================
TOKEN = "8536239572:AAG82o0mJw9WP3RKGrJTaLp-Hl2q8Gx6HYY"
CHAT_ID = "2055716345"
API_KEY = "128da1172fbb4aef83ca801cb3e6b928"
bot = telebot.TeleBot(TOKEN, threaded=False)

# Lista de ativos válidos
ATIVOS = [
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
    "BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD",
    "SOL/USD", "XRP/USD"
]

INTERVALO = 60  # segundos entre checagens
MOVIMENTO_MINIMO = 0.0005

# Arquivo de histórico de sinais
HIST_FILE = "historico.json"

# Inicializa histórico se não existir
if not os.path.exists(HIST_FILE):
    with open(HIST_FILE, "w") as f:
        json.dump([], f)

# Estatísticas globais
stats = {"green_seq": 0, "total": 0, "acertos": 0, "erros": 0}

# Último sinal enviado (sinal único)
ultimo_sinal = {"ativo": None, "sinal": None, "prob": 0, "resultado": None}

# ===============================
# FUNÇÕES AUXILIARES
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

# Análise de price action simples
def analisar_candles(candles):
    if len(candles) < 3:
        return None, 0
    ultimo, prev1, prev2 = candles[-1], candles[-2], candles[-3]

    movimento = abs(ultimo["close"] - ultimo["open"])
    if movimento / ultimo["open"] < MOVIMENTO_MINIMO:
        return None, 0

    if ultimo["close"] > ultimo["open"] and prev1["close"] < prev1["open"]:
        direcao = "CALL"
    elif ultimo["close"] < ultimo["open"] and prev1["close"] > prev1["open"]:
        direcao = "PUT"
    else:
        return None, 0

    # Probabilidade inicial baseada em padrão
    prob = 50
    if (direcao == "CALL" and prev1["close"] > prev1["open"] and prev2["close"] > prev2["open"]) or \
       (direcao == "PUT" and prev1["close"] < prev1["open"] and prev2["close"] < prev2["open"]):
        prob = 80
    else:
        prob = 60

    return direcao, prob

# Atualiza resultado do último sinal
def checar_resultado():
    global ultimo_sinal, stats
    if not ultimo_sinal["ativo"]:
        return False  # nenhum sinal enviado ainda

    candles = pegar_candles(ultimo_sinal["ativo"], limite=2)
    if len(candles) < 2:
        return False

    vela = candles[-1]
    if vela["close"] > vela["open"]:
        resultado = "🟢 GREEN"
    else:
        resultado = "🔴 RED"

    ultimo_sinal["resultado"] = resultado

    # Atualiza estatísticas
    stats["total"] += 1
    if (ultimo_sinal["sinal"] == "CALL" and resultado == "🟢 GREEN") or \
       (ultimo_sinal["sinal"] == "PUT" and resultado == "🟢 GREEN"):
        stats["acertos"] += 1
        stats["green_seq"] += 1
    else:
        stats["erros"] += 1
        stats["green_seq"] = 0

    # Salva histórico
    with open(HIST_FILE, "r") as f:
        historico = json.load(f)
    historico.append(ultimo_sinal)
    with open(HIST_FILE, "w") as f:
        json.dump(historico, f, indent=2)

    return True  # sinal processado

# Escolhe o próximo sinal baseado no histórico
def proximo_sinal():
    global ultimo_sinal
    for ativo in ATIVOS:
        candles = pegar_candles(ativo, limite=3)
        if not candles:
            continue
        direcao, prob = analisar_candles(candles)
        if direcao:
            # envia apenas se não houver sinal em andamento
            ultimo_sinal = {"ativo": ativo, "sinal": direcao, "prob": prob, "resultado": None}
            return True
    return False

# Envia painel profissional para Telegram
def enviar_painel():
    if ultimo_sinal["ativo"]:
        sinal_emoji = "📈" if ultimo_sinal["sinal"]=="CALL" else "📉"
        resultado = ultimo_sinal["resultado"] if ultimo_sinal["resultado"] else "🟡 PENDENTE"
        mensagem = (
            f"📊 **TROIA BOT IA - SINAL ÚNICO**\n\n"
            f"{ultimo_sinal['ativo']}: {sinal_emoji} {ultimo_sinal['sinal']} | Prob={ultimo_sinal['prob']}% | Resultado={resultado}\n\n"
            f"💚 Green Seq: {stats['green_seq']}\n"
            f"📈 Total: {stats['total']} | Acertos: {stats['acertos']} | Erros: {stats['erros']} | Accuracy: {stats['acertos']*100/stats['total'] if stats['total']>0 else 0:.1f}%"
        )
    else:
        mensagem = "🤖 IA está analisando, aguarde..."
    bot.send_message(CHAT_ID, mensagem)
    print(mensagem)

# ===============================
# LOOP PRINCIPAL
# ===============================
print("Troia Bot IA V17 Profissional iniciado...")
while True:
    # Primeiro, checa se o último sinal já tem resultado
    if ultimo_sinal["ativo"] and not ultimo_sinal["resultado"]:
        if checar_resultado():
            enviar_painel()
            time.sleep(INTERVALO)
            continue  # só envia o próximo sinal depois de processar

    # Envia próximo sinal
    if not ultimo_sinal["resultado"]:
        if proximo_sinal():
            enviar_painel()
        else:
            enviar_painel()  # mensagem de IA analisando

    time.sleep(INTERVALO)
