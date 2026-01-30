import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq 2026 Stable", layout="wide", page_icon="🛡️")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login de Auditoria")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditoria Fiscal (Modelos Estáveis 2026)")
st.info("Otimizado para evitar erros de modelos desativados (Decommissioned).")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.write("📌 **Status:** Conectado à Groq Cloud")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    # Ajuste de tamanho para garantir aceitação da API
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- CHAMADA À API COM NOMES DE MODELOS ATUALIZADOS ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Lista de modelos por ordem de prioridade na Groq em 2026
    # Removido os '-preview' que causaram o seu erro anterior
    modelos_disponiveis = [
        "llama-3.2-11b-vision",
        "llama-3.2-90b-vision",
        "llama-3.2-11b-vision-preview" # Mantido como última opção caso sua região ainda use
    ]
    
    prompt = (
        f"Analise a imagem e retorne APENAS: VALOR|ESTABELECIMENTO|CATEGORIA|STATUS. "
        f"Regra: Se valor total > {teto}, STATUS=REPROVADO. Use ponto para decimais."
    )
    
    ultimo_erro_api = ""
    for modelo in modelos_disponiveis:
        payload = {
            "model": modelo,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                ]
            }],
            "temperature": 0
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            if response.status_code == 200:
                return response, modelo
            else:
                ultimo_erro_api = response.text
        except Exception as e:
            ultimo_erro_api = str(e)
            
    return None, ultimo_erro_api

# --- PROCESSAMENTO ---
if st.button("🔍 Iniciar Processamento") and arquivos:
    if not groq_key:
        st.error("Por favor, adicione a GROQ_API_KEY nos Secrets.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    placeholder = st.empty()

    for i, arq in enumerate(arquivos):
        placeholder.info(f"Processando arquivo {i+1} de {len(arquivos)}: {arq.name}")
        try:
            img_b64 = preparar_imagem(arq)
            res, modelo_usado = chamar_groq_vision(groq_key, img_b64, limite)
            
            if res:
                content = res.json()['choices'][0]['message']['content']
                partes = content.split('|')
                
                # Limpeza de dados
                v_str = re.sub(r'[^\d.]', '', partes
