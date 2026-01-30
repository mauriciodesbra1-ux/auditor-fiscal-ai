import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq Multi-Model", layout="wide", page_icon="🛡️")

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
                st.error("Credenciais inválidas")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditoria Fiscal Inteligente")
st.caption("Conectando aos servidores Groq LPU...")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.write("🌐 **Modo de Compatibilidade 2026**")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- FUNÇÃO DE CHAMADA COM AUTO-TENTATIVA (FALLBACK) ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Tentaremos estes nomes em ordem de probabilidade para 2026
    modelos_para_testar = [
        "llama-3.2-11b-vision-preview", # Nome original
        "llama-3.2-11b-vision",         # Nome estável
        "llama-3.2-90b-vision-preview"  # Nome alternativo
    ]
    
    prompt = f"Retorne apenas: VALOR|LOCAL|CATEGORIA|STATUS. Regra: Valor > {teto} = REPROVADO."
    
    ultimo_erro = ""
    for modelo in modelos_para_testar:
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
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                return response, modelo # Sucesso!
            else:
                ultimo_erro = response.text
        except Exception as e:
            ultimo_erro = str(e)
            
    return None, ultimo_erro

# --- PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria") and arquivos:
    if not groq_key:
        st.error("Configure a API Key.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    
    for i, arq in enumerate(arquivos):
        try:
            img_b64 = preparar_imagem(arq)
            res, info = chamar_groq_vision(groq_key, img_b64, limite)
            
            if res:
                texto = res.json()['choices'][0]['message']['content']
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
                st.error(f"Falha em {arq.name}. Erro da API: {info}")
        except Exception as e:
            st.error(f"Erro técnico: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.subheader("📊 Resultados")
        st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status'), width='stretch')
        st.dataframe(df, width='stretch')
