import streamlit as st
import requests
import base64
import pandas as pd
import re
import time
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor AI Pro", layout="wide", page_icon="🛡️")

# --- SISTEMA DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Acesso Restrito")
        user = st.text_input("Usuário")
        pw = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if user == "admin" and pw == "auditor2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return False
    return True

if check_password():
    st.title("🛡️ AI Auditor Pro: Inteligência Fiscal")
    st.markdown("---")

    st.markdown("""
        <style>
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stInfo { border-left: 5px solid #007bff; background-color: #e7f3ff; }
        </style>
        """, unsafe_allow_html=True)

    if "GEMINI_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_KEY"]
    else:
        api_key = st.sidebar.text_input("Gemini API Key", type="password")

    valor_max = st.sidebar.number_input("Limite de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("📂 Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    def codificar_imagem(arquivo):
        return base64.b64encode(arquivo.read()).decode('utf-8')

    if st.button("🚀 Iniciar Auditoria Estratégica") and arquivos:
        if not api_key:
            st.error("⚠️ Configure a API Key!")
        else:
            resultados = []
            progresso = st.progress(0)
            status_msg = st.empty()
            
            MODELO = "gemini-3-flash-preview"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"

            for i, arq in enumerate(arquivos):
                status_msg.info(f"Analisando: {arq.name}...")
                img_b64 = codificar_imagem(arq)
                
                payload = {
                    "contents": [{"parts": [
                        {"text": f"Extraia em uma linha: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Limite R$ {valor_max}. Categorias: Alimentação, Transporte, Hospedagem, Outros."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "generationConfig": {"temperature": 0.1},
                    "safetySettings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                    ]
                }

                sucesso_nota = False
                for tentativa in range(3):
                    try:
                        response = requests.post(url, json=payload, timeout=50)
                        res_json = response.json()
                        
                        if 'candidates' in res_json and len(res_json['candidates']) > 0:
                            texto = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            texto = texto.replace('`', '').replace('markdown', '').strip()
                            cols = texto.split("|")
                            
                            if len(cols) >= 6:
                                v_str = re.sub(r'[^\d,.]', '', cols[0]).replace(',', '.')
                                resultados.append({
                                    "Arquivo": arq.name,
                                    "Valor (R$)": float(v_str) if v_str else 0.0,
                                    "Local": cols[1].strip(),
                                    "CNPJ": cols[2].strip(),
                                    "Data": cols[3].strip(),
                                    "Categoria": cols[4].strip(),
                                    "Status": cols[5].strip().upper(),
                                    "Justificativa": cols[6].strip() if len(cols) > 6 else ""
                                })
                                sucesso_nota = True
                                break
                        time.sleep(3)
                    except Exception:
                        time.sleep(3)
                
                if not sucesso_nota:
                    resultados.append({"Arquivo": arq.name, "Status": "FALHA API", "Valor (R$)": 0.0, "Justificativa": "Sem resposta após 3 tentativas"})
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0.0)
                df['Status'] = df['Status'].str.upper().str.strip()

                st.markdown("### 📊 Visão Geral")
                c1, c2, c3 = st.columns(3)
                val_aprovado = df[df['Status']=='APROVADO']['Valor (R$)'].sum()
                
                c1.metric("Notas", len(df))
                c2.metric("Aprovado", f"R$ {val_aprovado:,.2f}")
                c3.metric("Recusado", f"R$ {df['Valor (R$)'].sum() - val_aprovado:,.2f}")

                col1, col2 = st.columns(2)
                cores = {'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c', 'FALHA API': '#95a5a6'}
                with col1:
                    st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', color_discrete_map=cores), use_container_width=True)
                with col2:
                    st.plotly_chart(px.pie(df, names='Status', values='Valor (R$)', hole=0.4, color='Status', color_discrete_map=cores), use_container_width=True)

                st.markdown("---")
                st.subheader("🤖 Diagnóstico Estratégico")
                try:
                    resumo_ia = df[['Categoria', 'Valor (R$)', 'Status']].to_string()
                    prompt_an = f"Analise brevemente estes dados de auditoria e dê uma dica financeira: {resumo_ia}"
                    res_an = requests.post(url, json={"contents": [{"parts": [{"text": prompt_an}]}]}).json()
                    st.info(res_an['candidates'][0]['content']['parts'][0]['text'])
                except:
                    st.warning("Diagnóstico indisponível.")

                st.dataframe(df, use_container_width=True)
                st.download_button("📥 Baixar Excel", df.to_csv(index=False, sep=';').encode('utf-8-sig'), "relatorio.csv")
