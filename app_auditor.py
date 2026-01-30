import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor AI Pro 2026", layout="wide", page_icon="🛡️")

# --- ESTILO ---
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stMetric { border: 1px solid #d1d8e0; padding: 15px; border-radius: 12px; background-color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Portal de Auditoria Fiscal")
    with st.form("login_area"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Acessar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciais Inválidas")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("🛡️ Auditoria Inteligente de Notas")
st.caption("Conectado ao Engine Gemini 1.5 Flash (v2026.1)")

# Gerenciamento de Chave
api_key = st.secrets.get("GEMINI_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Google API Key", type="password")

with st.sidebar:
    st.header("⚙️ Parâmetros de Auditoria")
    limite_reembolso = st.number_input("Teto de Reembolso (R$)", value=250.0)
    st.divider()
    st.write("📌 **Dica:** Se o erro 404 persistir, verifique se o faturamento está ativo no Google AI Studio.")

arquivos = st.file_uploader("Selecione as fotos das notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- ENGINE DE PROCESSAMENTO ---
def realizar_chamada_api(chave, payload):
    """Tenta múltiplos endpoints para contornar erros 404 de depreciação."""
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={chave}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={chave}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={chave}"
    ]
    
    ultimo_erro = 404
    for url in endpoints:
        try:
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                return res, None
            ultimo_erro = res.status_code
        except Exception as e:
            return None, str(e)
    return None, f"Erro HTTP {ultimo_erro}"

if st.button("🔍 Iniciar Varredura") and arquivos:
    if not api_key:
        st.warning("⚠️ Insira sua API Key no menu lateral.")
        st.stop()

    lista_resultados = []
    barra_progresso = st.progress(0)
    container_status = st.empty()

    for idx, arq in enumerate(arquivos):
        container_status.info(f"Analisando documento {idx+1}/{len(arquivos)}: {arq.name}")
        
        try:
            # Codificação da Imagem
            img_b64 = base64.b64encode(arq.read()).decode('utf-8')
            
            # Construção do Payload
            prompt_auditoria = (
                f"Extraia estritamente: VALOR_TOTAL|ESTABELECIMENTO|CATEGORIA|AUDITORIA. "
                f"Regra de AUDITORIA: Se VALOR_TOTAL > {limite_reembolso}, retorne REPROVADO, senão APROVADO. "
                "Use ponto para decimais. Responda apenas os dados separados por pipe."
            )
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_auditoria},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]
                }]
            }

            # Chamada com Fallback
            response, erro_msg = realizar_chamada_api(api_key, payload)

            if response:
                data = response.json()
                raw_text = data['candidates'][0]['content']['parts'][0]['text']
                partes = raw_text.split('|')
                
                # Parsing Seguro
                v_str = re.sub(r'[^\d.]', '', partes[0].replace(',', '.')) if len(partes) > 0 else "0"
                valor = float(v_str) if v_str else 0.0
                
                lista_resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": valor,
                    "Local": partes[1].strip() if len(partes) > 1 else "Não identificado",
                    "Categoria": partes[2].strip() if len(partes) > 2 else "Outros",
                    "Status": partes[3].strip().upper() if len(partes) > 3 else "ERRO"
                })
            else:
                st.error(f"❌ Falha no arquivo {arq.name}: {erro_msg}")
        
        except Exception as e:
            st.error(f"⚠️ Erro inesperado em {arq.name}: {str(e)}")
        
        barra_progresso.progress((idx + 1) / len(arquivos))

    container_status.empty()

    # --- DASHBOARD DE RESULTADOS ---
    if lista_resultados:
        df = pd.DataFrame(lista_resultados)
        
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Processados", len(df))
        col2.metric("Aprovados", len(df[df['Status'] == 'APROVADO']))
        col3.metric("Reprovados", len(df[df['Status'] == 'REPROVADO']))
        col4.metric("Total Gasto", f"R$ {df['Valor (R$)'].sum():.2f}")

        # Gráficos de 2026
        st.subheader("📊 Visão Analítica")
        c_esq, c_dir = st.columns(2)
        
        with c_esq:
            fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status',
                            title="Distribuição por Categoria",
                            color_discrete_map={'APROVADO': '#27ae60', 'REPROVADO': '#e74c3c', 'ERRO': '#95a5a6'})
            st.plotly_chart(fig_bar, width='stretch')
            
        with c_dir:
            fig_pie = px.pie(df, names='Status', title="Proporção de Status", hole=0.4,
                            color='Status', color_discrete_map={'APROVADO': '#27ae60', 'REPROVADO': '#e74c3c'})
            st.plotly_chart(fig_pie, width='stretch')

        st.subheader("📋 Relatório Detalhado")
        st.dataframe(df, width='stretch')
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha de Auditoria", csv_data, "relatorio_fiscal.csv", "text/csv")
