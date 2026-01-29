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
    # --- INTERFACE PRINCIPAL ---
    st.title("🛡️ AI Auditor Pro: Inteligência Fiscal")
    st.markdown("---")

    # CSS para Estilização
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
        api_key = st.sidebar.text_input("Gemini API Key", type="password")

    # Configurações na Sidebar
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
                        {"text": f"Extraia em uma linha: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. Limite R$ {valor_max}, 90 dias. Categorias: Alimentação, Transporte, Hospedagem, Suprimentos, Outros."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]}],
                    "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
                }

                # --- MECANISMO DE RETRY ---
                sucesso_nota = False
                for tentativa in range(3):
                    try:
                        response = requests.post(url, json=payload, timeout=45)
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
                        time.sleep(2)
                    except Exception:
                        time.sleep(2)
                
                if not sucesso_nota:
                    resultados.append({"Arquivo": arq.name, "Status": "FALHA API", "Valor (R$)": 0.0, "Justificativa": "Sem resposta após 3 tentativas"})
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                
                # --- MÉTRICAS ---
                st.markdown("### 📊 Visão Geral")
                c1, c2, c3 = st.columns(3)
                total_val = df['Valor (R$)'].sum()
                val_aprovado = df[df['Status']=='APROVADO']['Valor (R$)'].sum()
                val_recusado = total_val - val_aprovado

                c1.metric("Notas Processadas", len(df))
                c2.metric("Total Aprovado", f"R$ {val_aprovado:,.2f}")
                c3.metric("Economia Estimada", f"R$ {val_recusado:,.2f}", delta_color="normal")

                # --- GRÁFICOS ---
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', title="Gastos por Categoria", 
                                         color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c'}), use_container_width=True)
                with col_g2:
                    st.plotly_chart(px.pie(df, names='Status', values='Valor (R$)', hole=0.4, title="Distribuição de Status",
                                         color='Status', color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c'}), use_container_width=True)

                # --- NOVA SEÇÃO: ANÁLISE NARRATIVA IA ---
                st.markdown("---")
                st.subheader("🤖 Diagnóstico Estratégico do Auditor")
                with st.spinner("IA analisando tendências..."):
                    resumo_ia = df[['Categoria', 'Valor (R$)', 'Status', 'Justificativa']].to_string()
                    prompt_narrativa = (
                        f"Aja como um auditor sênior. Analise estes dados:\n{resumo_ia}\n\n"
                        "Escreva um diagnóstico curto (3-4 frases) para o gerente financeiro. "
                        "Destaque a categoria com mais gastos, o principal motivo de reprovação e uma recomendação prática."
                    )
                    
                    try:
                        res_narrativa = requests.post(url, json={"contents": [{"parts": [{"text": prompt_narrativa}]}]}).json()
                        texto_analise = res_narrativa['candidates'][0]['content']['parts'][0]['text']
                        st.info(texto_analise)
                    except:
                        st.warning("O diagnóstico automático não pôde ser gerado.")

                # --- TABELA E DOWNLOAD ---
                st.markdown("### 📋 Detalhamento das Notas")
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Baixar Relatório Excel/CSV", csv, f"auditoria_{datetime.now().strftime('%d%m%Y')}.csv", "text/csv")
