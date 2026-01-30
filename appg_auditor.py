import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq Fix 400", layout="wide", page_icon="🦙")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Acesso negado")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditoria Fiscal (Fix 400)")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    limite = st.number_input("Limite (R$)", value=250.0)
    st.info("Ajuste: Redimensionamento automático de imagem ativado.")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- FUNÇÃO DE TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    """Redimensiona a imagem para evitar erro 400 por payload muito grande."""
    img = Image.open(upload)
    # Converte para RGB se for PNG/RGBA
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Redimensiona mantendo proporção (max 1024px)
    img.thumbnail((1024, 1024))
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- FUNÇÃO DE CHAMADA ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Em 2026, testamos o modelo preview e o estável
    modelos = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]
    
    prompt = f"Extraia os dados: VALOR|ESTABELECIMENTO|CATEGORIA|STATUS. Regra: Se valor > {teto}, STATUS=REPROVADO. Responda apenas o formato solicitado."
    
    for model in modelos:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    ]
                }
            ],
            "temperature": 0.1
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response
    return response # Retorna o último erro se falhar em todos

# --- PROCESSAMENTO ---
if st.button("🚀 Processar Notas") and arquivos:
    if not groq_key:
        st.error("Insira a chave da Groq.")
        st.stop()

    resultados = []
    barra = st.progress(0)

    for i, arq in enumerate(arquivos):
        try:
            # Novo: Tratamento da imagem antes de enviar
            img_b64 = preparar_imagem(arq)
            
            resp = chamar_groq_vision(groq_key, img_b64, limite)
            
            if resp.status_code == 200:
                texto = resp.json()['choices'][0]['message']['content']
                p = texto.split('|')
                v_limpo = re.sub(r'[^\d.]', '', p[0].replace(',', '.'))
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": float(v_limpo) if v_limpo else 0.0,
                    "Local": p[1].strip() if len(p) > 1 else "N/A",
                    "Categoria": p[2].strip() if len(p) > 2 else "Geral",
                    "Status": p[3].strip().upper() if len(p) > 3 else "ERRO"
                })
            else:
                # Se der erro 400, mostramos o motivo detalhado
                st.error(f"Erro {resp.status_code} em {arq.name}: {resp.text}")
        except Exception as e:
            st.error(f"Falha técnica: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.subheader("📊 Dashboard de Auditoria")
        st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status'), width='stretch')
        st.dataframe(df, width='stretch')
