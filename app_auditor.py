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

    # Recuperação da chave via Secrets ou Sidebar
    api_key = st.secrets.get("GEMINI_KEY", st.sidebar.text_input("Gemini API Key", type="password"))

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
                        {"text": "Extraia EXATAMENTE neste formato: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "generationConfig": {"temperature": 0.1},
                    "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
                }

                sucesso_nota = False
                for tentativa in range(2):
                    try:
                        response = requests.post(url, json=payload, timeout=40)
                        res_json = response.json()
                        if 'candidates' in res_json:
                            texto = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            # Limpeza de markdown caso a IA envie
                            texto = texto.replace('`', '').replace('markdown', '').strip()
                            cols = texto.split("|")
                            
                            # --- PREENCHIMENTO DE SEGURANÇA (Se faltar coluna, a gente cria) ---
                            valor_extraido = re.sub(r'[^\d,.]', '', cols[0]).replace(',', '.') if len(cols) > 0 else "0.0"
                            local_extraido = cols[1].strip() if len(cols) > 1 else "Não Identificado"
                            cnpj_extraido = cols[2].strip() if len(cols) > 2 else "00.000.000/0001-00"
                            data_extraida = cols[3].strip() if len(cols) > 3 else "00/00/0000"
                            cat_extraida = cols[4].strip() if len(cols) > 4 else "Outros"
                            status_extraido = cols[5].strip().upper() if len(cols) > 5 else "FALHA"
                            motivo_extraido = cols[6].strip() if len(cols) > 6 else "Erro na extração"

                            resultados.append({
                                "Arquivo": arq.name,
                                "Valor (R$)": float(valor_extraido) if valor_extraido else 0.0,
                                "Local": local_extraido,
                                "CNPJ": cnpj_extraido,
                                "Data": data_extraida,
                                "Categoria": cat_extraida,
                                "Status": status_extraido,
                                "Justificativa": motivo_extraido
                            })
                            sucesso_nota = True
                            break
                        time.sleep(1)
                    except:
                        time.sleep(1)
                
                if not sucesso_nota:
                    resultados.append({
                        "Arquivo": arq.name, "Valor (R$)": 0.0, "Local": "Erro de API", 
                        "CNPJ": "0", "Data": "0", "Categoria": "Outros", 
                        "Status": "FALHA", "Justificativa": "Sem resposta"
                    })
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # Garante que as colunas críticas existam mesmo se o DataFrame estiver estranho
                for c in ["Categoria", "Status", "Valor (R$)"]:
                    if c not in df.columns: df[c] = "Indefinido" if c != "Valor (R$)" else 0.0

                st.markdown("### 📊 Dashboard")
                
                col1, col2 = st.columns(2)
                cores_map = {'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c', 'FALHA': '#95a5a6'}
                
                with col1:
                    try:
                        fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                       color_discrete_map=cores_map, title="Gastos por Categoria")
                        st.plotly_chart(fig_bar, width='stretch')
                    except Exception:
                        st.warning("Gráfico de barras indisponível.")

                with col2:
                    try:
                        fig_pie = px.pie(df, names='Status', values='Valor (R$)', 
                                       color='Status', color_discrete_map=cores_map, title="Status Geral")
                        st.plotly_chart(fig_pie, width='stretch')
                    except Exception:
                        st.warning("Gráfico de pizza indisponível.")

                st.dataframe(df, width='stretch')
                st.download_button("📥 Baixar Planilha", df.to_csv(index=False, sep=';').encode('utf-8-sig'), "relatorio.csv")
