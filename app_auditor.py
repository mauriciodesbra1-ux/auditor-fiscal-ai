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

    # --- SEGURANÇA: SECRETS ---
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
            st.error("⚠️ Chave de API não configurada.")
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
                        {"text": f"Extraia em uma única linha: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Limite R$ {valor_max}. Categorias: Alimentação, Transporte, Hospedagem, Outros."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "generationConfig": {"temperature": 0.1},
                    "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
                }

                sucesso_nota = False
                for tentativa in range(3):
                    try:
                        response = requests.post(url, json=payload, timeout=50)
                        res_json = response.json()
                        if 'candidates' in res_json:
                            texto = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            cols = texto.replace('`', '').replace('markdown', '').strip().split("|")
                            
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
                        time.sleep(2)
                    except:
                        time.sleep(2)
                
                if not sucesso_nota:
                    # Se falhar, preenchemos com valores padrão para não quebrar o gráfico
                    resultados.append({
                        "Arquivo": arq.name, "Valor (R$)": 0.0, "Local": "Erro", "CNPJ": "0", 
                        "Data": "0", "Categoria": "Outros", "Status": "FALHA API", "Justificativa": "Sem resposta"
                    })
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # --- LIMPEZA CRÍTICA PARA O PLOTLY ---
                df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0.0)
                df['Status'] = df['Status'].fillna('FALHA API').str.upper()
                df['Categoria'] = df['Categoria'].fillna('Outros')

                st.markdown("### 📊 Dashboard de Auditoria")
                
                # Gráficos protegidos por try/except
                col1, col2 = st.columns(2)
                
                with col1:
                    try:
                        fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                       title="Gastos por Categoria", barmode='group')
                        st.plotly_chart(fig_bar, use_container_width=True)
                    except Exception:
                        st.warning("⚠️ Dados insuficientes para o gráfico de barras.")

                with col2:
                    try:
                        fig_pie = px.pie(df, names='Status', values='Valor (R$)', 
                                       title="Distribuição de Status", hole=0.4)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    except Exception:
                        st.warning("⚠️ Dados insuficientes para o gráfico de pizza.")

                st.markdown("---")
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Baixar Planilha", csv, "auditoria.csv", "text/csv")
