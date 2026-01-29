import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor AI 2026", layout="wide", page_icon="🛡️")

# --- ESTILO ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { border: 1px solid #ddd; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN (SIMPLIFICADO PARA O EXEMPLO) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login do Auditor")
    user = st.text_input("Usuário")
    pw = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if user == "admin" and pw == "auditor2026":
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Acesso Negado")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Sistema de Auditoria de Notas Fiscais")

# Chave API via Secrets ou Sidebar
api_key = st.secrets.get("GEMINI_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key", type="password")

with st.sidebar:
    st.header("⚙️ Parâmetros")
    limite = st.number_input("Limite de Reembolso (R$)", value=200.0)
    st.info("O modelo v1 estável será utilizado para evitar erros 404.")

arquivos = st.file_uploader("Carregar notas (JPG/PNG)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- PROCESSAMENTO ---
if st.button("🚀 Processar Notas") and arquivos:
    if not api_key:
        st.error("Por favor, insira a API Key.")
        st.stop()

    resultados = []
    progresso = st.progress(0)
    
    # Endpoint v1 estável (evita o 404 da v1beta antiga)
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"

    for i, arq in enumerate(arquivos):
        try:
            # Codificar imagem
            img_data = base64.b64encode(arq.read()).decode('utf-8')
            
            # Montar payload
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"Extraia da nota fiscal: VALOR|LOCAL|CATEGORIA. Se o valor for maior que {limite}, defina STATUS como REPROVADO, caso contrário APROVADO. Formato: VALOR|LOCAL|CATEGORIA|STATUS"},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_data}}
                    ]
                }]
            }

            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                texto = response.json()['candidates'][0]['content']['parts'][0]['text']
                partes = texto.split('|')
                
                # Tratamento de segurança para colunas faltantes
                valor_raw = partes[0] if len(partes) > 0 else "0"
                valor_clean = float(re.sub(r'[^\d.]', '', valor_raw.replace(',', '.')))
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor": valor_clean,
                    "Local": partes[1] if len(partes) > 1 else "N/A",
                    "Categoria": partes[2] if len(partes) > 2 else "Outros",
                    "Status": partes[3].strip().upper() if len(partes) > 3 else "ERRO"
                })
            else:
                st.error(f"Erro na nota {arq.name}: Status HTTP {response.status_code}")
        
        except Exception as e:
            st.error(f"Falha ao processar {arq.name}: {str(e)}")
        
        progresso.progress((i + 1) / len(arquivos))

    # --- EXIBIÇÃO ---
    if resultados:
        df = pd.DataFrame(resultados)
        
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Analisado", len(df))
        col2.metric("Aprovados", len(df[df['Status'] == 'APROVADO']))
        col3.metric("Total (R$)", f"R$ {df['Valor'].sum():.2f}")

        st.subheader("📋 Relatório Final")
        st.dataframe(df, use_container_width=True)

        st.subheader("📊 Gráficos de Auditoria")
        c_alt1, c_alt2 = st.columns(2)
        with c_alt1:
            fig1 = px.pie(df, names='Status', title="Proporção de Aprovação", color='Status',
                          color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'})
            st.plotly_chart(fig1)
        with c_alt2:
            fig2 = px.bar(df, x='Categoria', y='Valor', color='Status', title="Gastos por Categoria")
            st.plotly_chart(fig2)

        # Download CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha CSV", csv, "auditoria.csv", "text/csv")
