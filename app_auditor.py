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

# --- SISTEMA DE LOGIN SIMPLES ---
def check_password():
    """Retorna True se o usuário inseriu a senha correta."""
    def password_entered():
        if st.session_state["username"] == "admin" and st.session_state["password"] == "auditor2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # remove senha do estado
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Acesso Restrito")
        st.text_input("Usuário", on_change=password_entered, key="username")
        st.text_input("Senha", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Usuário", on_change=password_entered, key="username")
        st.text_input("Senha", type="password", on_change=password_entered, key="password")
        st.error("😕 Usuário ou senha incorretos.")
        return False
    else:
        return True

if check_password():
    # --- INTERFACE PRINCIPAL (SÓ APARECE APÓS LOGIN) ---
    st.title("🛡️ AI Auditor Pro: Inteligência Fiscal")
    st.markdown("---")

    # CSS para melhorar visual
    st.markdown("""
        <style>
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        </style>
        """, unsafe_allow_html=True)

    # --- SEGURANÇA: SECRETS ---
    if "GEMINI_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_KEY"]
    else:
        api_key = st.sidebar.text_input("Gemini API Key", type="password")

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

                # --- MECANISMO DE RETRY (TRATAMENTO DE FALHA API) ---
                sucesso_nota = False
                for tentativa in range(3): # Tenta até 3 vezes
                    try:
                        response = requests.post(url, json=payload, timeout=40)
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
                                break # Sucesso! Sai do loop de retry
                        
                        # Se chegou aqui, a API respondeu mas sem conteúdo (ex: bloqueio ou erro de cota)
                        time.sleep(2) # Espera antes de tentar de novo
                        
                    except Exception as e:
                        time.sleep(2) # Espera em caso de erro de conexão
                
                if not sucesso_nota:
                    resultados.append({"Arquivo": arq.name, "Status": "FALHA API", "Valor (R$)": 0.0, "Justificativa": "Sem resposta após 3 tentativas"})
                
                progresso.progress((i + 1) / len(arquivos))

            status_msg.empty()

            if resultados:
                df = pd.DataFrame(resultados)
                st.markdown("---")
                
                # DASHBOARD
                c1, c2, c3 = st.columns(3)
                c1.metric("Notas", len(df))
                c2.metric("Aprovado", f"R$ {df[df['Status']=='APROVADO']['Valor (R$)'].sum():,.2f}")
                c3.metric("Economia", f"R$ {df[df['Status']!='APROVADO']['Valor (R$)'].sum():,.2f}")

                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', barmode='group'), use_container_width=True)
                with col2:
                    st.plotly_chart(px.pie(df, names='Status', values='Valor (R$)', hole=0.4), use_container_width=True)

                st.dataframe(df, use_container_width=True)
                st.download_button("📥 Baixar Excel", df.to_csv(index=False, sep=';').encode('utf-8-sig'), "relatorio.csv")



# --- ADICIONE ESTE BLOCO LOGO APÓS A CRIAÇÃO DO DATAFRAME (df) ---

if resultados:
    # ... (Seus gráficos e métricas existentes continuam aqui) ...

    st.markdown("---")
    st.subheader("🤖 Diagnóstico do Auditor (IA)")
    
    with st.spinner("Gerando análise estratégica..."):
        # Preparamos um resumo textual para a IA analisar
        resumo_texto = df[['Categoria', 'Valor (R$)', 'Status', 'Justificativa']].to_string()
        
        prompt_analise = (
            f"Com base nos dados desta auditoria:\n{resumo_texto}\n\n"
            "Escreva um diagnóstico rápido para o dono da empresa. "
            "1. Aponte a categoria mais cara. "
            "2. Cite o principal motivo de reprovação. "
            "3. Dê uma dica de economia baseada nos dados. "
            "Seja profissional e direto (máximo 4 frases)."
        )

        # Reutilizamos a API para gerar o texto
        url_text = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={api_key}"
        payload_analise = {"contents": [{"parts": [{"text": prompt_analise}]}]}
        
        try:
            res_ia = requests.post(url_text, json=payload_analise, timeout=30).json()
            analise_narrativa = res_ia['candidates'][0]['content']['parts'][0]['text']
            st.info(analise_narrativa)
        except:
            st.warning("Não foi possível gerar o diagnóstico automático no momento.")

    # ... (O restante do seu código: Tabela e Download) ...
