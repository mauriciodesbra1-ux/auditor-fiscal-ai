import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq 2026 Final", layout="wide", page_icon="🛡️")

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
st.title("🛡️ Auditoria Fiscal Inteligente (Groq Stable)")
st.caption("Versão de Produção 2026 - Llama 3.2 Vision")

# API Key via Secrets
groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    st.header("⚙️ Configurações")
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.info("Otimizado para evitar erros 400/404 de modelos.")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    # Redimensiona para garantir compatibilidade com limites da API
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- CHAMADA À API COM TRATAMENTO DE ERROS CORRIGIDO ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Modelos estáveis para 2026
    modelos_disponiveis = ["llama-3.2-11b-vision", "llama-3.2-90b-vision"]
    
    prompt = (
        f"Extraia estritamente: VALOR|LOCAL|CATEGORIA|STATUS. "
        f"Regra: Se valor > {teto}, STATUS=REPROVADO, senão APROVADO. "
        "Responda apenas a string separada por pipe."
    )
    
    erro_acumulado = "Nenhum modelo disponível respondeu."
    
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
                return response, None # Retorna sucesso e nenhum erro
            else:
                erro_acumulado = response.text
        except Exception as e:
            erro_acumulado = str(e)
            
    return None, erro_acumulado

# --- PROCESSAMENTO ---
if st.button("🔍 Iniciar Processamento") and arquivos:
    if not groq_key:
        st.error("Adicione a GROQ_API_KEY nos Secrets.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    msg_status = st.empty()

    for i, arq in enumerate(arquivos):
        msg_status.info(f"Analisando: {arq.name}")
        try:
            img_b64 = preparar_imagem(arq)
            res, erro_msg = chamar_groq_vision(groq_key, img_b64, limite)
            
            if res:
                content = res.json()['choices'][0]['message']['content']
                partes = content.split('|')
                
                # Parsing Numérico Seguro (Fix syntax error)
                v_str = re.sub(r'[^\d.]', '', partes[0].replace(',', '.'))
                valor = float(v_str) if v_str else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": valor,
                    "Local": partes[1].strip() if len(partes) > 1 else "N/D",
                    "Categoria": partes[2].strip() if len(partes) > 2 else "Geral",
                    "Status": partes[3].strip().upper() if len(partes) > 3 else "ERRO"
                })
            else:
                st.error(f"Erro no arquivo {arq.name}: {erro_msg}")
        except Exception as e:
            st.error(f"Falha técnica em {arq.name}: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    msg_status.empty()

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.subheader("📊 Relatório Analítico")
        
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                  color_discrete_map={'APROVADO':'#00cc96', 'REPROVADO':'#ef553b'}), 
                            use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, names='Status', hole=0.4, 
                                  color_discrete_sequence=['#00cc96', '#ef553b']), 
                            use_container_width=True)
            
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Baixar Dados", df.to_csv(index=False).encode('utf-8'), 
                           "auditoria.csv", "text/csv")
