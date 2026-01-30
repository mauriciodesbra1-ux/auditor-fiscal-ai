import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq Stable 2026", layout="wide", page_icon="🛡️")

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
st.title("🛡️ Sistema de Auditoria Fiscal")
st.caption("Engine: Llama 3.2 Vision (Produção 2026)")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    st.header("⚙️ Configurações")
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.info("Utilizando modelo estável: llama-3.2-11b-vision")

arquivos = st.file_uploader("Carregar fotos das notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM ---
def preparar_imagem(upload):
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    # Redimensiona para evitar estourar limite de tokens da API gratuita
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- CHAMADA À API (FOCO NO MODELO 11B) ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # O modelo 11b é o mais acessível e estável para contas gratuitas
    modelo = "llama-3.2-11b-vision"
    
    prompt = (
        f"Extraia os dados no formato exato: VALOR|LOCAL|CATEGORIA|STATUS. "
        f"Regra: Se o valor total for maior que {teto}, o STATUS deve ser REPROVADO, caso contrário APROVADO. "
        "Não adicione texto extra, apenas o formato solicitado."
    )
    
    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                ]
            }
        ],
        "temperature": 0
    }
    
    return requests.post(url, headers=headers, json=payload, timeout=30)

# --- FLUXO PRINCIPAL ---
if st.button("🔍 Iniciar Auditoria") and arquivos:
    if not groq_key:
        st.error("⚠️ GROQ_API_KEY não configurada nos Secrets.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    status_placeholder = st.empty()

    for i, arq in enumerate(arquivos):
        status_placeholder.text(f"Processando: {arq.name}")
        try:
            img_b64 = preparar_imagem(arq)
            resp = chamar_groq_vision(groq_key, img_b64, limite)
            
            if resp.status_code == 200:
                texto = resp.json()['choices'][0]['message']['content']
                p = texto.split('|')
                
                # Parsing Numérico Seguro
                v_raw = re.sub(r'[^\d.]', '', p[0].replace(',', '.'))
                v_num = float(v_raw) if v_raw else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": v_num,
                    "Local": p[1].strip() if len(p) > 1 else "N/D",
                    "Categoria": p[2].strip() if len(p) > 2 else "Outros",
                    "Status": p[3].strip().upper() if len(p) > 3 else "ERRO"
                })
            else:
                erro_detalhe = resp.json().get('error', {}).get('message', 'Erro desconhecido')
                st.error(f"❌ Erro {resp.status_code} em {arq.name}: {erro_detalhe}")
        except Exception as e:
            st.error(f"⚠️ Falha técnica em {arq.name}: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    status_placeholder.empty()

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        
        # Dashboard Visual
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                  title="Volume por Categoria",
                                  color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'}), 
                            width='stretch')
        with col2:
            st.plotly_chart(px.pie(df, names='Status', title="Resumo Geral"), width='stretch')

        st.subheader("📋 Relatório")
        st.dataframe(df, width='stretch')
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar Relatório", csv, "auditoria.csv", "text/csv")
