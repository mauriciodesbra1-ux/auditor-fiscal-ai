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

# --- ESTILO CSS PARA MELHORAR O VISUAL ---
# --- ESTILO CSS PARA MELHORAR O VISUAL ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ AI Auditor Pro: Dashboard de Inteligência")
st.markdown("---")

# --- SISTEMA DE SEGURANÇA (SECRETS) ---
# Se você configurar 'GEMINI_KEY' no painel do Streamlit, ele usará automaticamente.
# Caso contrário, ele pedirá na barra lateral para testes locais.
if "GEMINI_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_KEY"]
    st.sidebar.success("✅ Chave de API carregada via Secrets")
else:
    api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Configure 'GEMINI_KEY' nos Secrets do Streamlit Cloud para produção.")

# --- CONFIGURAÇÕES DE AUDITORIA ---
valor_max = st.sidebar.number_input("Limite de Reembolso (R$)", value=250.0)
st.sidebar.markdown("---")
arquivos = st.file_uploader("📂 Arraste as notas fiscais aqui", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

def codificar_imagem(arquivo):
    return base64.b64encode(arquivo.read()).decode('utf-8')

# --- PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria Estratégica") and arquivos:
    if not api_key:
        st.error("⚠️ Erro: Nenhuma API Key configurada. Verifique os Secrets ou a barra lateral.")
    else:
        resultados = []
        progresso = st.progress(0)
        status_msg = st.empty()
        
        # Modelo verificado na sua chave (Gemini 3 Flash)
        MODELO = "gemini-3-flash-preview"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"

        for i, arq in enumerate(arquivos):
            status_msg.info(f"Analisando: {arq.name}...")
            
            prompt = (
                f"Extraia os dados no formato exato: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. "
                f"Regras: Máximo R$ {valor_max}, sem álcool, máximo 90 dias. "
                f"Categorias: Alimentação, Transporte, Hospedagem, Suprimentos ou Outros. "
                f"Responda em uma única linha."
            )

            payload = {
                "contents": [{"parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": codificar_imagem(arq)}}
                ]}],
                "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
            }

            try:
                response = requests.post(url, json=payload, timeout=40)
                res_json = response.json()
                
                if 'candidates' in res_json:
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
                else:
                    resultados.append({"Arquivo": arq.name, "Status": "FALHA API", "Valor (R$)": 0.0, "Justificativa": "Sem resposta"})
            
            except Exception as e:
                resultados.append({"Arquivo": arq.name, "Status": "ERRO TÉCNICO", "Valor (R$)": 0.0, "Justificativa": str(e)})
            
            progresso.progress((i + 1) / len(arquivos))
            time.sleep(2)

        status_msg.empty()

        # --- EXIBIÇÃO DO DASHBOARD BI ---
        if resultados:
            df = pd.DataFrame(resultados)
            
            # Cards de Resumo
            m1, m2, m3, m4 = st.columns(4)
            val_aprovado = df[df['Status']=='APROVADO']['Valor (R$)'].sum()
            val_recusado = df[df['Status'].str.contains('REPROVADO|RECUSADO', na=False)]['Valor (R$)'].sum()
            
            m1.metric("Notas Processadas", len(df))
            m2.metric("Total Aprovado", f"R$ {val_aprovado:,.2f}")
            m3.metric("Economia Gerada", f"R$ {val_recusado:,.2f}", delta="Reprovados")
            m4.metric("Categoria Principal", df['Categoria'].mode()[0] if not df.empty else "N/A")

            st.markdown("---")
            
            # Gráficos
            col_graf1, col_graf2 = st.columns(2)
            
            with col_graf1:
                st.subheader("📌 Gastos por Categoria")
                fig_cat = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                 color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c'})
                st.plotly_chart(fig_cat, use_container_width=True)

            with col_graf2:
                st.subheader("🎯 Veredito de Auditoria")
                fig_pie = px.pie(df, names='Status', values='Valor (R$)', hole=.4,
                                 color='Status', color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c'})
                st.plotly_chart(fig_pie, use_container_width=True)

            # Tabela de Dados
            st.subheader("📋 Relatório Detalhado")
            st.dataframe(df.style.highlight_max(axis=0, subset=['Valor (R$)'], color='#f8d7da'), use_container_width=True)
            
            # Download
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Baixar Planilha para Excel", csv, f"auditoria_{datetime.now().strftime('%d%m%y')}.csv", "text/csv")

