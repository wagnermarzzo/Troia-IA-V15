import time
import telebot
import yfinance as yf

# ===============================
# CONFIGURAÇÃO (SEUS DADOS)
# ===============================
TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"

TEMPO_RESULTADO = 180  # 3 minutos reais

bot = telebot.TeleBot(TOKEN, threaded=False)

# ===============================
# ATIVOS (TODOS)
# ===============================
ATIVOS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "NZDUSD=X",
    "EURJPY=X", "GBPJPY=X", "EURGBP=X"
]

# ===============================
# ESTADO GLOBAL
# ===============================
sinal_ativo = None
ultimo_ativo_idx = 0

print("🤖 Troia Bot IA iniciado!")

# ===============================
# FUNÇÕES
# ===============================
def pegar_candle(symbol):
    try:
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if df.empty:
            return None
        last = df.iloc[-1]
        return float(last["Open"]), float(last["Close"])
    except Exception:
        return None

def gerar_sinal(open_p, close_p):
    if close_p > open_p:
        return "CALL"
    elif close_p < open_p:
        return "PUT"
    return None

# ===============================
# LOOP PRINCIPAL (CORRIGIDO)
# ===============================
while True:
    agora_ts = time.time()

    # ===============================
    # EXISTE SINAL ATIVO → ESPERA 3 MIN
    # ===============================
    if sinal_ativo:
        if agora_ts - sinal_ativo["entrada_ts"] < TEMPO_RESULTADO:
            time.sleep(2)
            continue

        # CALCULA RESULTADO APÓS 3 MIN
        candle = pegar_candle(sinal_ativo["ativo"])
        if candle:
            open_p, close_p = candle
            resultado = "GREEN" if (
                (sinal_ativo["tipo"] == "CALL" and close_p > open_p) or
                (sinal_ativo["tipo"] == "PUT" and close_p < open_p)
            ) else "RED"

            bot.send_message(
                CHAT_ID,
                f"📊 RESULTADO\n"
                f"{sinal_ativo['ativo']}\n"
                f"Sinal: {sinal_ativo['tipo']}\n"
                f"Resultado: {resultado}"
            )

        sinal_ativo = None
        time.sleep(5)
        continue

    # ===============================
    # SEM SINAL → ANALISA 1 ATIVO
    # ===============================
    ativo = ATIVOS[ultimo_ativo_idx]
    ultimo_ativo_idx = (ultimo_ativo_idx + 1) % len(ATIVOS)

    candle = pegar_candle(ativo)
    if candle:
        open_p, close_p = candle
        sinal = gerar_sinal(open_p, close_p)

        if sinal:
            sinal_ativo = {
                "ativo": ativo,
                "tipo": sinal,
                "entrada_ts": time.time()
            }

            bot.send_message(
                CHAT_ID,
                f"🚨 SINAL GERADO\n"
                f"Ativo: {ativo}\n"
                f"Direção: {sinal}\n"
                f"⏱ Resultado em 3 minutos"
            )

    time.sleep(10)
