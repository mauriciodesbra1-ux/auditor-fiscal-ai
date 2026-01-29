import streamlit as st
import requests
import base64
import pandas as pd
import re
import time
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor AI Pro", layout="wide", page_icon="🛡️")

# --- LOGIN ---
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
                st.error("Dados incorretos.")
        return False
    return True

if check_password():
    st.title("🛡️ AI Auditor Pro")
    st.markdown("---")

    # Tenta ler do Secrets, senão pede no sidebar
    api_key = st.secrets.get("GEMINI_KEY", st.sidebar.text_input("Gemini API Key", type="password"))
    valor_max = st.sidebar.number_input("Limite de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("📂 Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    def codificar_imagem(arquivo):
        return base64.b64encode(arquivo.read()).decode('utf-8')

    if st.button("🚀 Iniciar Auditoria") and arquivos:
        if not api_key:
            st.error("Chave API necessária.")
        else:
            resultados = []
            progresso = st.progress(0)
            status_msg = st.empty()
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"

            for i, arq in enumerate(arquivos):
                status_msg.info(f"Analisando: {arq.name}...")
                img_b64 = codificar_imagem(arq)
                
                payload = {
                    "contents": [{"parts": [
                        {"text": f"Extraia os dados no formato: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Use categorias: Alimentação, Transporte, Hospedagem ou Outros. Limite: R$ {valor_max}."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "generationConfig": {"temperature": 0.1},
                    "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
                }

                sucesso_nota = False
                for _ in range(2):
                    try:
                        response = requests.post(url, json=payload, timeout=40)
                        res_json = response.json()
                        if 'candidates' in res_json:
                            texto = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            cols = texto.replace('`', '').replace('markdown', '').strip().split("|")
                            
                            # Validação rigorosa de fatiamento
                            v_str = re.sub(r'[^\d,.]', '', cols[0]).replace(',', '.') if len(cols) > 0 else "0.0"
                            resultados.append({
                                "Arquivo": arq.name,
                                "Valor (R$)": float(v_str) if v_str else 0.0,
                                "Local": cols[1].strip() if len(cols) > 1 else "N/A",
                                "CNPJ": cols[2].strip() if len(cols) > 2 else "N/A",
                                "Data": cols[3].strip() if len(cols) > 3 else "N/A",
                                "Categoria": cols[4].strip() if len(cols) > 4 else "Outros",
                                "Status": cols[5].strip().upper() if len(cols) > 5 else "FALHA",
                                "Justificativa": cols[6].strip() if len(cols) > 6 else "Erro de parsing"
                            })
                            sucesso_nota = True
                            break
                        time.sleep(2)
                    except:
                        time.sleep(2)
                
                if not sucesso_nota:
                    resultados.append({
                        "Arquivo": arq.name, "Valor (R$)": 0.0, "Local": "Erro", "CNPJ": "N/A",
                        "Data": "N/A", "Categoria": "Outros", "Status": "FALHA", "Justificativa": "Sem resposta"
                    })
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # --- HIGIENIZAÇÃO PÓS-PROCESSAMENTO ---
                # Garante que as colunas existam para o Plotly não explodir
                for col in ["Categoria", "Status", "Valor (R$)"]:
                    if col not in df.columns:
                        df[col] = "Outros" if col != "Valor (R$)" else 0.0
                
                df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0.0)
                df['Status'] = df['Status'].fillna('FALHA').astype(str).str.upper()
                df['Categoria'] = df['Categoria'].fillna('Outros').astype(str)

                st.markdown("### 📊 Dashboard")
                
                col1, col2 = st.columns(2)
                with col1:
                    try:
                        st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                       title="Gastos por Categoria"), width='stretch')
                    except:
                        st.warning("Falha ao gerar gráfico de barras.")

                with col2:
                    try:
                        st.plotly_chart(px.pie(df, names='Status', values='Valor (R$)', 
                                       title="Distribuição de Status"), width='stretch')
                    except:
                        st.warning("Falha ao gerar gráfico de pizza.")

                st.dataframe(df, width='stretch')
                st.download_button("📥 Baixar Excel", df.to_csv(index=False, sep=';').encode('utf-8-sig'), "relatorio.csv")
