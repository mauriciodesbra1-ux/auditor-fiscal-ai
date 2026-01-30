import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Gemini 2.5", layout="wide", page_icon="🛡️")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login Auditoria")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")
    st.stop()

# --- CONFIGURAÇÃO GEMINI ---
st.title("🛡️ Auditoria Fiscal AI")
st.caption("Engine: Gemini 2.5 Flash (Identificado via Scanner)")

# Chave API via Secrets
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Google API Key", type="password")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("⚠️ Configure a GEMINI_API_KEY nos Secrets ou Sidebar.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Parâmetros")
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.success("Conectado ao Gemini 2.5")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria") and arquivos:
    # Usando o nome exato que o seu scanner validou
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"Erro ao inicializar o modelo: {e}")
        st.stop()

    resultados = []
    barra = st.progress(0)
    status_msg = st.empty()

    for i, arq in enumerate(arquivos):
        status_msg.info(f"Analisando: {arq.name}")
        try:
            # Preparar imagem para o Gemini
            img = Image.open(arq)
            
            prompt = (
                f"Extraia estritamente os dados desta nota no formato: VALOR|LOCAL|CATEGORIA|STATUS. "
                f"Regra: Se valor total > {limite}, STATUS=REPROVADO, senão APROVADO. "
                "Retorne apenas a string separada por pipe."
            )
            
            # Chamada da API
            response = model.generate_content([prompt, img])
            
            # Tratamento da resposta
            texto = response.text.strip()
            partes = texto.split('|')
            
            if len(partes) >= 1:
                # Limpeza numérica (substitui vírgula por ponto e remove símbolos)
                v_str = re.sub(r'[^\d.]', '', partes[0].replace(',', '.'))
                valor_final = float(v_str) if v_str else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": valor_final,
                    "Local": partes[1].strip() if len(partes) > 1 else "N/D",
                    "Categoria": partes[2].strip() if len(partes) > 2 else "Geral",
                    "Status": partes[3].strip().upper() if len(partes) > 3 else "ERRO"
                })
        except Exception as e:
            st.error(f"Erro no arquivo {arq.name}: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    status_msg.empty()

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        
        # Dashboard
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status',
                                  color_discrete_map={'APROVADO':'#00cc96', 'REPROVADO':'#ef553b'}), 
                            use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, names='Status', hole=0.4), use_container_width=True)
            
        st.subheader("📋 Relatório Final")
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar CSV", csv, "auditoria_fiscal.csv", "text/csv")
