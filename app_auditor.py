import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor AI Pro 2026", layout="wide", page_icon="🛡️")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE LOGIN ---
if "autenticado" not in st.session_state:
    st.title("🔒 Acesso Restrito - Auditoria")
    with st.container():
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Aceder"):
            if user == "admin" and senha == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciais inválidas.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("🛡️ Auditor Fiscal AI - Analisador de Despesas")

# Recupera a chave dos Secrets ou Sidebar
api_key = st.secrets.get("GEMINI_KEY", "")

with st.sidebar:
    st.header("⚙️ Definições")
    limite_reembolso = st.number_input("Limite de Reembolso (R$)", value=250.0, step=10.0)
    st.divider()
    if not api_key:
        api_key = st.text_input("Insira a Gemini API Key:", type="password")
    st.info("Utilizando Gemini 1.5 Flash (v1 Estável)")

# Upload de arquivos
arquivos_carregados = st.file_uploader("Carregar Notas Fiscais", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

if st.button("🚀 Iniciar Auditoria") and arquivos_carregados:
    if not api_key:
        st.error("Erro: API Key não configurada.")
    else:
        resultados = []
        progresso = st.progress(0)
        status_msg = st.empty()
        
        # Endpoint v1 Estável para evitar erro 404
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        for idx, arquivo in enumerate(arquivos_carregados):
            status_msg.text(f"A analisar: {arquivo.name}...")
            
            try:
                # Ler e converter imagem
                img_bytes = arquivo.read()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"Extraia os dados da nota: VALOR|LOCAL|CATEGORIA|JUSTIFICATIVA. Regra: Se o valor > {limite_reembolso}, Status REPROVADO, senão APROVADO. Formato: VALOR|LOCAL|CATEGORIA|JUSTIFICATIVA|STATUS"},
                            {"inline_data": {"mime_type": "image/jpeg", "data": img_base64}}
                        ]
                    }]
                }
                
                resposta = requests.post(url, json=payload, timeout=30)
                
                if resposta.status_code == 200:
                    raw_text = resposta.json()['candidates'][0]['content']['parts'][0]['text']
                    partes = raw_text.split("|")
                    
                    # Preenchimento seguro das colunas (evita o ValueError no Plotly)
                    v_str = partes[0].strip() if len(partes) > 0 else "0"
                    v_num = float(re.sub(r'[^\d.]', '', v_str.replace(',', '.'))) if v_str else 0.0
                    
                    resultados.append({
                        "Arquivo": arquivo.name,
                        "Valor (R$)": v_num,
                        "Local": partes[1].strip() if len(partes) > 1 else "N/D",
                        "Categoria": partes[2].strip() if len(partes) > 2 else "Outros",
                        "Justificativa": partes[3].strip() if len(partes) > 3 else "N/A",
                        "Status": partes[4].strip().upper() if len(partes) > 4 else "PENDENTE"
                    })
                else:
                    st.error(f"Erro na nota {arquivo.name}: HTTP {resposta.status_code}")
            
            except Exception as e:
                st.error(f"Falha técnica em {arquivo.name}: {e}")
            
            progresso.progress((idx + 1) / len(arquivos_carregados))
        
        status_msg.empty()

        if resultados:
            df = pd.DataFrame(resultados)
            
            st.divider()
            # DASHBOARD
            c1, c2, c3 = st.columns(3)
            c1.metric("Notas Processadas", len(df))
            c2.metric("Total Aprovado", f"R$ {df[df['Status']=='APROVADO']['Valor (R$)'].sum():.2f}")
            c3.metric("Total Reprovado", f"R$ {df[df['Status']=='REPROVADO']['Valor (R$)'].sum():.2f}")

            # GRÁFICOS (Com verificação de colunas)
            st.subheader("📊 Análise de Gastos")
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                if 'Categoria' in df.columns:
                    fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                    title="Gastos por Categoria", barmode='group',
                                    color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'})
                    st.plotly_chart(fig_bar, width='stretch')
            
            with col_g2:
                if 'Status' in df.columns:
                    fig_pie = px.pie(df, names='Status', values='Valor (R$)', title="Status Financeiro", hole=0.4)
                    st.plotly_chart(fig_pie, width='stretch')

            st.subheader("📋 Detalhes da Auditoria")
            st.dataframe(df, width='stretch')
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Relatório", csv, "auditoria_2026.csv", "text/csv")
        else:
            st.warning("Nenhum dado processado.")
