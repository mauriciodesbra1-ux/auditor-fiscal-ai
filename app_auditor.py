import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Fiscal Gemini 2.5", layout="wide", page_icon="🛡️")

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
st.title("🛡️ Auditoria Fiscal Inteligente")
st.caption("Engine: Gemini 2.5 Flash | Status: Conectado")

api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Google API Key", type="password")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("⚠️ API Key não configurada.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Regras de Compliance")
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.success("Modelo: Gemini 2.5 Flash")

arquivos = st.file_uploader("Carregar Notas Fiscais", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria Completa") and arquivos:
    model = genai.GenerativeModel('gemini-2.5-flash')
    resultados = []
    barra = st.progress(0)
    status_msg = st.empty()

    for i, arq in enumerate(arquivos):
        status_msg.info(f"Analisando detalhadamente: {arq.name}")
        try:
            img = Image.open(arq)
            
            # PROMPT EVOLUÍDO PARA EXTRAÇÃO COMPLETA
            prompt = (
                f"Analise esta imagem de nota fiscal e extraia os dados rigorosamente no formato: "
                f"DATA|EMPRESA|VALOR|CATEGORIA|STATUS|JUSTIFICATIVA. "
                f"Regras: "
                f"1. Se o VALOR for maior que {limite}, o STATUS é REPROVADO. "
                f"2. Na JUSTIFICATIVA, explique brevemente o motivo do status (ex: 'Valor acima do permitido' ou 'Gasto dentro da política'). "
                f"3. Responda APENAS a linha com os dados separados por pipe (|)."
            )
            
            response = model.generate_content([prompt, img])
            texto = response.text.strip()
            
            # Divide a resposta em partes
            partes = texto.split('|')
            
            if len(partes) >= 6:
                # Limpeza do Valor
                v_str = re.sub(r'[^\d.]', '', partes[2].replace(',', '.'))
                valor_final = float(v_str) if v_str else 0.0
                
                resultados.append({
                    "Data": partes[0].strip(),
                    "Empresa": partes[1].strip(),
                    "Valor (R$)": valor_final,
                    "Categoria": partes[3].strip(),
                    "Status": partes[4].strip().upper(),
                    "Justificativa": partes[5].strip(),
                    "Arquivo": arq.name
                })
            else:
                st.warning(f"Formato inesperado em {arq.name}. Resposta da IA: {texto}")

        except Exception as e:
            st.error(f"Erro no arquivo {arq.name}: {str(e)}")
        
        barra.progress((i + 1) / len(arquivos))

    status_msg.empty()

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        
        # --- DASHBOARD ---
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            total_auditado = df['Valor (R$)'].sum()
            st.metric("Total Auditado", f"R$ {total_auditado:.2f}")
        with col2:
            aprovados = len(df[df['Status'] == 'APROVADO'])
            st.metric("Notas Aprovadas", aprovados)
        with col3:
            reprovados = len(df[df['Status'] == 'REPROVADO'])
            st.metric("Notas Reprovadas", reprovados)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                  title="Gastos por Categoria",
                                  color_discrete_map={'APROVADO':'#00cc96', 'REPROVADO':'#ef553b'}), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, names='Status', title="Distribuição de Status", hole=0.4), use_container_width=True)
            
        st.subheader("📋 Relatório Detalhado de Compliance")
        # Reordenando colunas para o relatório ficar bonito
        df_display = df[["Data", "Empresa", "Categoria", "Valor (R$)", "Status", "Justificativa", "Arquivo"]]
        st.dataframe(df_display, use_container_width=True)
        
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar Planilha de Auditoria", csv, "auditoria_final.csv", "text/csv")
