import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Groq Edition", layout="wide", page_icon="🦙")

# --- ESTILO ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { border-radius: 10px; background-color: white; border: 1px solid #e0e0e0; padding: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login - Auditoria Groq")
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
st.title("🛡️ Auditoria com Llama 3.2 Vision (Groq)")
st.info("Versão 2.0 - Alta Performance")

# Chave da API nos Secrets
groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    st.header("⚙️ Configurações")
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.caption("Ficheiro ativo: appg_auditor.py")

arquivos = st.file_uploader("Upload das Notas Fiscais", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- LÓGICA DE CHAMADA ---
def chamar_groq_vision(api_key, base64_image, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    prompt = (
        f"Extraia os dados no formato: VALOR|ESTABELECIMENTO|CATEGORIA|STATUS. "
        f"Se o valor for maior que {teto}, STATUS=REPROVADO. Caso contrário, APROVADO. "
        f"Retorne apenas os dados separados por pipe."
    )
    
    payload = {
        "model": "llama-3.2-11b-vision-preview",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "temperature": 0
    }
    
    return requests.post(url, headers=headers, json=payload, timeout=30)

# --- PROCESSAMENTO ---
if st.button("🚀 Processar com Groq") and arquivos:
    if not groq_key:
        st.error("Configure a GROQ_API_KEY nos Secrets ou na barra lateral.")
        st.stop()

    resultados = []
    progresso = st.progress(0)
    msg = st.empty()

    for i, arq in enumerate(arquivos):
        msg.info(f"Analisando: {arq.name}")
        try:
            img_b64 = base64.b64encode(arq.read()).decode('utf-8')
            resp = chamar_groq_vision(groq_key, img_b64, limite)
            
            if resp.status_code == 200:
                texto = resp.json()['choices'][0]['message']['content']
                p = texto.split('|')
                
                # Limpeza e Parsing
                v_limpo = re.sub(r'[^\d.]', '', p[0].replace(',', '.'))
                valor = float(v_limpo) if v_limpo else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": valor,
                    "Local": p[1].strip() if len(p) > 1 else "Desconhecido",
                    "Categoria": p[2].strip() if len(p) > 2 else "Geral",
                    "Status": p[3].strip().upper() if len(p) > 3 else "ERRO"
                })
            else:
                st.error(f"Erro na nota {arq.name}: Status {resp.status_code}")
        except Exception as e:
            st.error(f"Falha técnica: {str(e)}")
        
        progresso.progress((i + 1) / len(arquivos))

    msg.empty()

    # --- RESULTADOS ---
    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Notas", len(df))
        c2.metric("Total (R$)", f"R$ {df['Valor (R$)'].sum():.2f}")
        c3.metric("Aprovadas", len(df[df['Status'] == 'APROVADO']))

        st.subheader("📊 Gráficos de Auditoria")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            fig1 = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                         color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'})
            st.plotly_chart(fig1, width='stretch')
        
        with col_g2:
            fig2 = px.pie(df, names='Status', hole=0.4, title="Status das Notas")
            st.plotly_chart(fig2, width='stretch')

        st.subheader("📋 Detalhamento")
        st.dataframe(df, width='stretch')
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar CSV", csv, "auditoria_groq.csv", "text/csv")
