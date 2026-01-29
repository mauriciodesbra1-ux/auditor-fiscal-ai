import streamlit as st
import requests
import base64
import pandas as pd
import re
import time
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Auditor Pro: BI Edition", layout="wide", page_icon="📊")
st.title("📊 Auditoria & Inteligência de Gastos")
st.markdown("---")

# Sidebar
api_key = st.sidebar.text_input("API Key", type="password")
valor_max = st.sidebar.number_input("Limite de Valor (R$)", value=250.0)
arquivos = st.file_uploader("Upload das Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

def codificar_imagem(arquivo):
    return base64.b64encode(arquivo.read()).decode('utf-8')

if st.button("🚀 Iniciar Auditoria Estratégica") and arquivos:
    if not api_key:
        st.error("Insira a API Key")
    else:
        resultados = []
        progresso = st.progress(0)
        MODELO = "gemini-3-flash-preview"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"

        for i, arq in enumerate(arquivos):
            st.write(f"🔍 Processando: {arq.name}...")
            
            # PROMPT EVOLUÍDO PARA BI
            prompt = (
                f"Extraia os dados no formato exato: VALOR|LOCAL|CNPJ|DATA|CATEGORIA|STATUS|MOTIVO. "
                f"Regras: Máximo R$ {valor_max}, sem álcool, máximo 90 dias. "
                f"Categorias possíveis: Alimentação, Transporte, Hospedagem, Suprimentos, Saúde ou Outros. "
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
                    resultados.append({"Arquivo": arq.name, "Status": "FALHA API", "Valor (R$)": 0.0})
            
            except Exception as e:
                resultados.append({"Arquivo": arq.name, "Status": "ERRO", "Justificativa": str(e)})
            
            progresso.progress((i + 1) / len(arquivos))
            time.sleep(2)

        if resultados:
            df = pd.DataFrame(resultados)
            st.markdown("---")
            
            # --- DASHBOARD DE MÉTRICAS ---
            m1, m2, m3, m4 = st.columns(4)
            val_aprovado = df[df['Status']=='APROVADO']['Valor (R$)'].sum()
            val_recusado = df[df['Status'].str.contains('REPROVADO|RECUSADO', na=False)]['Valor (R$)'].sum()
            
            m1.metric("Notas", len(df))
            m2.metric("Aprovado", f"R$ {val_aprovado:,.2f}")
            m3.metric("Economia", f"R$ {val_recusado:,.2f}", delta="Reprovados")
            m4.metric("Principais Gastos", df['Categoria'].mode()[0] if not df.empty else "N/A")

            # --- VISUALIZAÇÃO BI ---
            col_esq, col_dir = st.columns(2)
            
            with col_esq:
                st.subheader("📌 Gastos por Categoria")
                fig_cat = px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                 barmode='group', color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c'})
                st.plotly_chart(fig_cat, use_container_width=True)

            with col_dir:
                st.subheader("🎯 Veredito Geral")
                fig_pie = px.pie(df, names='Status', values='Valor (R$)', hole=.4,
                                 color='Status', color_discrete_map={'APROVADO': '#2ecc71', 'REPROVADO': '#e74c3c'})
                st.plotly_chart(fig_pie, use_container_width=True)

            st.subheader("📋 Relatório Detalhado")
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Baixar Relatório BI", csv, "auditoria_estratégica.csv", "text/csv")