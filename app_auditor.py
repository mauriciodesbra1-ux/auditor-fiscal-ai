import streamlit as st
import requests
import base64
import pandas as pd
import re
import time
import plotly.express as px

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditor AI", layout="wide")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.title("🔒 Login")
    user = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if user == "admin" and senha == "auditor2026":
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Incorreto")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditor Fiscal AI")

# Chave vinda dos Secrets do Streamlit
api_key = st.secrets.get("GEMINI_KEY", "")

with st.sidebar:
    st.header("Configurações")
    limite = st.number_input("Limite Reembolso (R$)", value=250.0)
    if not api_key:
        api_key = st.text_input("API Key manual", type="password")

arquivos = st.file_uploader("Subir Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- PROCESSAMENTO ---
if st.button("Analisar Notas") and arquivos:
    if not api_key:
        st.error("Falta API Key")
    else:
        resultados = []
        barra = st.progress(0)
        
        for idx, arq in enumerate(arquivos):
            # Encode imagem
            img_data = base64.b64encode(arq.read()).decode('utf-8')
            
            # Payload Simplificado para evitar erros de parser
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"Analise a imagem e retorne APENAS: VALOR|LOCAL|CATEGORIA|STATUS. Regra: Se valor > {limite} status REPROVADO, senão APROVADO."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_data}}
                    ]
                }]
            }
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            try:
                res = requests.post(url, json=payload, timeout=30)
                if res.status_code == 200:
                    raw_text = res.json()['candidates'][0]['content']['parts'][0]['text']
                    partes = raw_text.split("|")
                    
                    # Garantir que temos 4 colunas mesmo se a IA errar
                    v = partes[0].strip() if len(partes) > 0 else "0"
                    l = partes[1].strip() if len(partes) > 1 else "Desconhecido"
                    c = partes[2].strip() if len(partes) > 2 else "Outros"
                    s = partes[3].strip() if len(partes) > 3 else "ERRO"
                    
                    # Limpeza de valor
                    v_clean = re.sub(r'[^\d,.]', '', v).replace(',', '.')
                    
                    resultados.append({
                        "Arquivo": arq.name,
                        "Valor (R$)": float(v_clean) if v_clean else 0.0,
                        "Local": l,
                        "Categoria": c,
                        "Status": s.upper()
                    })
                else:
                    st.warning(f"Erro na nota {arq.name}: Status {res.status_code}")
            except Exception as e:
                st.error(f"Falha técnica: {e}")
            
            barra.progress((idx + 1) / len(arquivos))

        # --- EXIBIÇÃO ---
        if resultados:
            df = pd.DataFrame(resultados)
            
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Notas", len(df))
            col2.metric("Soma Total", f"R$ {df['Valor (R$)'].sum():.2f}")
            col3.metric("Reprovadas", len(df[df['Status'].str.contains("REPROVADO")]))

            # Gráfico Blindado (Só roda se a coluna existir)
            if 'Categoria' in df.columns:
                fig = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', width=800)
                st.plotly_chart(fig, width='stretch')

            st.dataframe(df, width='stretch')
