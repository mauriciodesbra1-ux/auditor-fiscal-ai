import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq 2026 Fix", layout="wide", page_icon="🛡️")

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
st.title("🛡️ Auditoria Fiscal (Multi-Model Fallback)")
st.caption("Auto-ajustando modelo para evitar Erro 404")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    st.header("⚙️ Configurações")
    limite = st.number_input("Limite (R$)", value=250.0)
    st.divider()
    st.info("O sistema testará automaticamente as versões do Llama 3.2 Vision.")

arquivos = st.file_uploader("Carregar Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- FUNÇÃO DE CHAMADA AUTO-AJUSTÁVEL ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Lista de nomes possíveis para o modelo de 11B em 2026
    modelos_teste = [
        "llama-3.2-11b-vision-preview", 
        "llama-3.2-11b-vision",
        "llama-3.1-8b-instant" # Fallback apenas texto se vision falhar
    ]
    
    prompt = f"VALOR|LOCAL|CATEGORIA|STATUS. Regra: Valor > {teto} = REPROVADO. Responda apenas o pipe."
    
    erro_final = ""
    for m in modelos_teste:
        payload = {
            "model": m,
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
            r = requests.post(url, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                return r, m # Sucesso! Retorna o response e qual modelo funcionou
            else:
                erro_final = r.text
        except Exception as e:
            erro_final = str(e)
            
    return None, erro_final

# --- PROCESSAMENTO ---
if st.button("🚀 Processar") and arquivos:
    if not groq_key:
        st.error("Chave API não encontrada.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    
    for i, arq in enumerate(arquivos):
        try:
            img_b64 = preparar_imagem(arq)
            res, m_ativo = chamar_groq_vision(groq_key, img_b64, limite)
            
            if res:
                # Se o modelo usado for o preview, o log avisará
                content = res.json()['choices'][0]['message']['content']
                p = content.split('|')
                v_limpo = re.sub(r'[^\d.]', '', p[0].replace(',', '.'))
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": float(v_limpo) if v_limpo else 0.0,
                    "Local": p[1].strip() if len(p) > 1 else "N/A",
                    "Categoria": p[2].strip() if len(p) > 2 else "Geral",
                    "Status": p[3].strip().upper() if len(p) > 3 else "ERRO",
                    "Modelo": m_ativo
                })
            else:
                st.error(f"Erro em {arq.name}: {erro_final}")
        except Exception as e:
            st.error(f"Falha técnica: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.metric("Modelo Ativo Detectado", df['Modelo'].iloc[0])
        st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status'), use_container_width=True)
        st.dataframe(df)
