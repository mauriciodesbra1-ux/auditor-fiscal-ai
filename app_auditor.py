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

# Recupera a chave dos Secrets do Streamlit ou permite entrada manual
api_key = st.secrets.get("GEMINI_KEY", "")

with st.sidebar:
    st.header("⚙️ Definições")
    limite_reembolso = st.number_input("Limite de Reembolso (R$)", value=250.0, step=10.0)
    st.divider()
    if not api_key:
        api_key = st.text_input("Insira a Gemini API Key:", type="password")
    st.info("Este auditor utiliza o modelo Gemini 1.5 Flash para análise de comprovativos.")

# Upload de arquivos
arquivos_carregados = st.file_uploader("Carregar Notas Fiscais / Recibos", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- LÓGICA DE PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria") and arquivos_carregados:
    if not api_key:
        st.error("Erro: API Key não configurada.")
    else:
        resultados = []
        progresso = st.progress(0)
        status_msg = st.empty()
        
        for idx, arquivo in enumerate(arquivos_carregados):
            status_msg.text(f"A analisar: {arquivo.name}...")
            
            # Converter imagem para Base64
            img_bytes = arquivo.read()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # Endpoint v1 (Estável) para evitar erro 404
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"Atue como um auditor fiscal. Analise a imagem e retorne APENAS os dados neste formato: VALOR|LOCAL|CATEGORIA|STATUS. Regras: Se o valor for maior que {limite_reembolso}, o STATUS deve ser 'REPROVADO', caso contrário 'APROVADO'. Se não encontrar a categoria, use 'Outros'."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_base64}}
                    ]
                }]
            }
            
            try:
                resposta = requests.post(url, json=payload, timeout=30)
                
                if resposta.status_code == 200:
                    dados_ia = resposta.json()['candidates'][0]['content']['parts'][0]['text']
                    # Split com segurança
                    partes = dados_ia.split("|")
                    
                    valor_str = partes[0].strip() if len(partes) > 0 else "0"
                    local = partes[1].strip() if len(partes) > 1 else "Não identificado"
                    categoria = partes[2].strip() if len(partes) > 2 else "Outros"
                    status_ia = partes[3].strip() if len(partes) > 3 else "ERRO"
                    
                    # Limpeza de valor numérico
                    valor_num = re.sub(r'[^\d,.]', '', valor_str).replace(',', '.')
                    valor_final = float(valor_num) if valor_num else 0.0
                    
                    resultados.append({
                        "Arquivo": arquivo.name,
                        "Valor (R$)": valor_final,
                        "Local": local,
                        "Categoria": categoria,
                        "Status": status_ia.upper()
                    })
                else:
                    st.error(f"Erro na nota {arquivo.name}: Status HTTP {resposta.status_code}")
            
            except Exception as e:
                st.error(f"Erro técnico no processamento de {arquivo.name}: {e}")
            
            progresso.progress((idx + 1) / len(arquivos_carregados))
        
        status_msg.empty()

        # --- EXIBIÇÃO DOS RESULTADOS ---
        if resultados:
            df = pd.DataFrame(resultados)
            
            st.divider()
            # Dashboard de métricas
            c1, c2, c3 = st.columns(3)
            c1.metric("Notas Processadas", len(df))
            c2.metric("Total Aprovado", f"R$ {df[df['Status'].str.contains('APROVADO')]['Valor (R$)'].sum():.2f}")
            c3.metric("Total Reprovado", f"R$ {df[df['Status'].str.contains('REPROVADO')]['Valor (R$)'].sum():.2f}")

            # Gráficos com tratamento de erro para colunas ausentes
            st.subheader("📊 Análise Visual")
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                if 'Categoria' in df.columns:
                    fig_bar = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', title="Gastos por Categoria", barmode='group')
                    st.plotly_chart(fig_bar, width='stretch')
            
            with col_g2:
                if 'Status' in df.columns:
                    fig_pie = px.pie(df, names='Status', values='Valor (R$)', title="Distribuição de Status", hole=0.4)
                    st.plotly_chart(fig_pie, width='stretch')

            st.subheader("📋 Tabela Detalhada")
            st.dataframe(df, width='stretch')
            
            # Opção de Download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descarregar Relatório CSV", csv, "relatorio_auditoria.csv", "text/csv")
        else:
            st.warning("Nenhum dado pôde ser extraído das notas.")
