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
            # Podes alterar o utilizador e senha aqui
            if user == "admin" and pw == "auditor2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return False
    return True

if check_password():
    # --- INTERFACE PRINCIPAL ---
    st.title("🛡️ AI Auditor Pro: Inteligência Fiscal")
    st.markdown("---")

    # Estilização CSS
    st.markdown("""
        <style>
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stInfo { border-left: 5px solid #007bff; background-color: #e7f3ff; }
        </style>
        """, unsafe_allow_html=True)

    # --- SEGURANÇA: SECRETS ---
    if "GEMINI_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_KEY"]
    else:
        api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Chave não detetada nos Secrets.")

    # Configurações na Sidebar
    valor_max = st.sidebar.number_input("Limite de Reembolso (R$)", value=250.0)
    arquivos = st.file_uploader("📂 Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    def codificar_imagem(arquivo):
        return base64.b64encode(arquivo.read()).decode('utf-8')

    if st.button("🚀 Iniciar Auditoria Estratégica") and arquivos:
        if not api_key:
            st.error("⚠️ Configure a API Key nos Secrets do Streamlit!")
        else:
            resultados = []
            progresso = st.progress(0)
            status_msg = st.empty()
            
            MODELO = "gemini-3-flash-preview"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"

        for i, arq in enumerate(arquivos):
                status_msg.info(f"Analisando: {arq.name}...")
                img_b64 = codificar_imagem(arq)
                
                # Payload otimizado para evitar bloqueios
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"Extraia os dados desta nota fiscal no formato exato: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Regras: Limite R$ {valor_max}, categorizar em Alimentação, Transporte, Hospedagem ou Outros. Se o valor for maior que o limite, STATUS é REPROVADO."},
                            {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,  # Menos criatividade, mais precisão
                        "topP": 1,
                        "maxOutputTokens": 256
                    },
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
                        
                        # LOG DE DEBUG (Apenas para o programador ver no terminal do Streamlit)
                        if 'error' in res_json:
                             print(f"Erro na tentativa {tentativa}: {res_json['error']}")

                        if 'candidates' in res_json and len(res_json['candidates']) > 0:
                            part = res_json['candidates'][0]['content']['parts'][0]
                            if 'text' in part:
                                texto = part['text'].strip()
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
                        time.sleep(3) # Aumentado o tempo de espera entre tentativas
                    except Exception as e:
                        print(f"Erro de conexão: {e}")
                        time.sleep(3)
                
                if not sucesso_nota:
                    resultados.append({"Arquivo": arq.name, "Status": "FALHA API", "Valor (R$)": 0.0, "Justificativa": "Sem resposta após 3 tentativas"})
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # --- LIMPEZA E VALIDAÇÃO PARA GRÁFICOS ---
                df['Valor (R$)'] = pd.to_numeric(df['Valor (R$)'], errors='coerce').fillna(0.0)
                for col in ['Categoria', 'Status']:
                    if col not in df.columns: df[col] = "Não Informado"
                df['Status'] = df['Status'].str.upper().str.strip()

                # --- MÉTRICAS ---
                st.markdown("### 📊 Visão Geral")
                c1, c2, c3 = st.columns(3)
                total_val = df['Valor (R$)'].sum()
                val_aprovado = df[df['Status'] == 'APROVADO']['Valor (R$)'].sum()
                val_recusado = total_val - val_aprovado

                c1.metric("Notas Processadas", len(df))
                c2.metric("Total Aprovado", f"R$ {val_aprovado:,.2f}")
                c3.metric("Economia Gerada", f"R$ {val_recusado:,.2f}")

                # --- GRÁFICOS PROTEGIDOS ---
                st.markdown("---")
                col_g1, col_g2 = st.columns(2)
                
                cores_map = {'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c', 'FALHA API': '#95a5a6'}

                with col_g1:
                    try:
                        fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                       title="Gastos por Categoria", barmode='group',
                                       color_discrete_map=cores_map)
                        st.plotly_chart(fig_bar, use_container_width=True)
                    except:
                        st.error("Erro ao gerar gráfico de barras.")

                with col_g2:
                    try:
                        fig_pie = px.pie(df, names='Status', values='Valor (R$)', hole=0.4, 
                                       title="Percentual por Status",
                                       color='Status', color_discrete_map=cores_map)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    except:
                        st.error("Erro ao gerar gráfico de pizza.")

                # --- ANÁLISE NARRATIVA IA ---
                st.markdown("---")
                st.subheader("🤖 Diagnóstico Estratégico do Auditor")
                with st.spinner("IA analisando tendências..."):
                    resumo_ia = df[['Categoria', 'Valor (R$)', 'Status', 'Justificativa']].to_string()
                    prompt_narrativa = (
                        f"Aja como um auditor sênior. Analise estes dados de reembolsos:\n{resumo_ia}\n\n"
                        "Escreva um diagnóstico curto (3 frases) para o gerente financeiro. "
                        "Identifique o maior gasto, o motivo principal das reprovações e dê uma recomendação."
                    )
                    
                    try:
                        payload_an = {"contents": [{"parts": [{"text": prompt_narrativa}]}]}
                        res_narrativa = requests.post(url, json=payload_an, timeout=30).json()
                        texto_analise = res_narrativa['candidates'][0]['content']['parts'][0]['text']
                        st.info(texto_analise)
                    except:
                        st.warning("O diagnóstico automático não pôde ser gerado.")

                # --- TABELA E DOWNLOAD ---
                st.markdown("### 📋 Detalhes da Auditoria")
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Baixar Relatório Completo", csv, f"auditoria_{datetime.now().strftime('%d%m%Y')}.csv", "text/csv")

