import time
import json
import requests
from datetime import datetime, timedelta
import telebot

# ===============================
# CONFIGURAÇÃO
# ===============================
API_KEY = "128da1172fbb4aef83ca801cb3e6b928"
TOKEN = "8536239572:AAG82o0mJw9WP3RKGrJTaLp-Hl2q8HYY"
CHAT_ID = "2055716345"

ATIVOS = [
    "BTC/USD", "ETH/USD", "BNB/USD", "ADA/USD", "SOL/USD",
    "XRP/USD", "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD"
]

bot = telebot.TeleBot(TOKEN, threaded=False)
historico_file = "historico.json"

# Inicializa histórico se não existir
try:
    with open(historico_file, "r") as f:
        historico = json.load(f)
except:
    historico = []

# Contadores
green_seq = 0
total = 0
acertos = 0
erros = 0

# ===============================
# FUNÇÕES
# ===============================

def salvar_historico():
    # Serializa datetime como string
    serializado = []
    for item in historico:
        serializado.append({
            "ativo": item["ativo"],
            "sinal": item["sinal"],
            "analise_hora": item["analise_hora"].strftime("%H:%M:%S"),
            "entrada_hora": item["entrada_hora"].strftime("%H:%M:%S"),
            "resultado": item["resultado"]
        })
    with open(historico_file, "w") as f:
        json.dump(serializado, f, indent=2)

def pegar_candle_1m(ativo):
    url = f"https://api.twelvedata.com/time_series?symbol={ativo}&interval=1min&outputsize=2&apikey={API_KEY}"
    r = requests.get(url).json()
    if "values" in r:
        # Última vela
        return r["values"][0], r["values"][1]  # candle atual, anterior
    else:
        print(f"Erro API Twelve Data {ativo}: {r}")
        return None, None

def gerar_sinal(ativo):
    # Aprendizado simples: baseia-se no último resultado do mesmo ativo
    ultimo = next((x for x in reversed(historico) if x["ativo"] == ativo), None)
    if ultimo:
        if ultimo["resultado"] == "WIN":
            return "CALL" if ultimo["sinal"] == "CALL" else "PUT"
        else:
            return "PUT" if ultimo["sinal"] == "CALL" else "CALL"
    else:
        # Sem histórico, sorteio 50/50
        import random
        return random.choice(["CALL", "PUT"])

def checar_resultado(sinal, candle):
    open_price = float(candle["open"])
    close_price = float(candle["close"])
    if sinal == "CALL":
        return "WIN" if close_price > open_price else "LOSS"
    else:
        return "WIN" if close_price < open_price else "LOSS"

def enviar_telegram(ativo, sinal, analise_hora, entrada_hora, resultado, green_seq, total, acertos, erros):
    accuracy = (acertos/total*100) if total>0 else 0
    msg = f"📊 **TROIA BOT IA - SINAL ÚNICO**\n"
    msg += f"{ativo}: {('📈' if sinal=='CALL' else '📉')} {sinal}\n"
    msg += f"⏱ Analisada: {analise_hora}\n"
    msg += f"⏱ Entrada: {entrada_hora}\n"
    msg += f"Resultado: {resultado if resultado else '🟡 PENDENTE'}\n"
    msg += f"💚 Green Seq: {green_seq}\n"
    msg += f"📈 Total: {total} | Acertos: {acertos} | Erros: {erros} | Accuracy: {accuracy:.1f}%"
    bot.send_message(CHAT_ID, msg)

# ===============================
# LOOP PRINCIPAL
# ===============================
while True:
    for ativo in ATIVOS:
        candle_atual, candle_anterior = pegar_candle_1m(ativo)
        if candle_atual is None:
            bot.send_message(CHAT_ID, f"🤖 IA está analisando {ativo}, aguarde...")
            continue

        sinal = gerar_sinal(ativo)
        analise_hora = datetime.now()
        # Próxima vela
        entrada_hora = analise_hora + timedelta(minutes=1)
        resultado = None

        # Adiciona ao histórico como PENDENTE
        historico.append({
            "ativo": ativo,
            "sinal": sinal,
            "analise_hora": analise_hora,
            "entrada_hora": entrada_hora,
            "resultado": resultado
        })
        salvar_historico()
        enviar_telegram(ativo, sinal, analise_hora.strftime("%H:%M"), entrada_hora.strftime("%H:%M"), resultado, green_seq, total, acertos, erros)

        # Espera a vela fechar
        while datetime.now() < entrada_hora + timedelta(seconds=60):
            time.sleep(1)

        # Pega a vela fechada
        candle_atual, _ = pegar_candle_1m(ativo)
        resultado = checar_resultado(sinal, candle_atual)

        # Atualiza histórico
        historico[-1]["resultado"] = resultado
        salvar_historico()

        # Atualiza contadores
        total += 1
        if resultado == "WIN":
            acertos += 1
            green_seq += 1
        else:
            erros += 1
            green_seq = 0

        # Reenvia resultado no Telegram
        enviar_telegram(ativo, sinal, analise_hora.strftime("%H:%M"), entrada_hora.strftime("%H:%M"), resultado, green_seq, total, acertos, erros)

        # Espera 1s antes do próximo ativo para não estourar limite
        time.sleep(1)
