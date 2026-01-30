import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Fiscal Gemini", layout="wide", page_icon="🛡️")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login")
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
st.title("🛡️ Auditoria Fiscal AI (Gemini)")
st.caption("Conectado via Google AI Studio")

# Tenta pegar a chave dos Secrets do Streamlit
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Google API Key", type="password")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("⚠️ Insira sua API Key para continuar.")
    st.stop()

with st.sidebar:
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.info("Dica: Se der 404, verifique o Billing no Google AI Studio.")

arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria") and arquivos:
    # 1. Definindo o modelo (Flash é o mais resiliente ao erro 404)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Erro ao carregar modelo: {e}")
        st.stop()

    resultados = []
    barra = st.progress(0)
    
    for i, arq in enumerate(arquivos):
        try:
            # Converter arquivo para imagem PIL
            img = Image.open(arq)
            
            prompt = (
                f"Analise esta nota fiscal e retorne APENAS: VALOR|LOCAL|CATEGORIA|STATUS. "
                f"Regra: Se o valor for maior que {limite}, o STATUS deve ser REPROVADO. "
                "Use ponto para decimais."
            )
            
            # Chamada da API Gemini
            response = model.generate_content([prompt, img])
            texto = response.text
            
            # Parsing dos dados
            partes = texto.split('|')
            if len(partes) >= 1:
                # Limpeza de valor (extração numérica)
                v_str = re.sub(r'[^\d.]', '', partes[0].replace(',', '.'))
                valor = float(v_str) if v_str else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": valor,
                    "Local": partes[1].strip() if len(partes) > 1 else "N/A",
                    "Categoria": partes[2].strip() if len(partes) > 2 else "Geral",
                    "Status": partes[3].strip().upper() if len(partes) > 3 else "ERRO"
                })
        except Exception as e:
            st.error(f"Erro no arquivo {arq.name}: {e}")
            # Dica de especialista para erro 404
            if "404" in str(e):
                st.info("💡 **Dica de Contorno:** Vá no Google AI Studio, clique em 'Settings' -> 'Billing' e verifique se há um projeto ativo. O Gemini bloqueia modelos Vision para contas não verificadas em algumas regiões.")
        
        barra.progress((i + 1) / len(arquivos))

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.subheader("📊 Resultados")
        st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', barmode='group'), use_container_width=True)
        st.dataframe(df, use_container_width=True)
