import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Auditor Fiscal AI", layout="wide", page_icon="🛡️")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login de Auditoria")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Acesso negado")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditor Fiscal AI")
st.caption("Engine: Groq Llama 3.2 Vision (Estabilizado)")

groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

with st.sidebar:
    limite = st.number_input("Limite de Reembolso (R$)", value=250.0)
    st.divider()
    st.info("Ajuste: Compressão e limpeza de Base64 ativados.")

arquivos = st.file_uploader("Enviar Notas", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- TRATAMENTO DE IMAGEM (RESOLVE ERRO 400) ---
def preparar_imagem(upload):
    """Redimensiona e limpa a imagem para o padrão aceito pela Groq."""
    img = Image.open(upload)
    # Converte para RGB para garantir compatibilidade (remove transparência de PNGs)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Redimensiona para um tamanho seguro (max 1024px)
    img.thumbnail((1024, 1024))
    
    buffer = io.BytesIO()
    # Usa JPEG com compressão para reduzir o peso do JSON enviado
    img.save(buffer, format="JPEG", quality=80)
    # Retorna apenas a string Base64 limpa
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- CHAMADA À API ---
def chamar_groq_vision(api_key, b64_img, teto):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # O erro 400 sugere que este modelo existe, mas a imagem estava "suja"
    modelo = "llama-3.2-11b-vision-preview"
    
    prompt = (
        f"Retorne apenas os dados extraídos no formato: VALOR|LOCAL|CATEGORIA|STATUS. "
        f"Regra: Se valor total > {teto}, STATUS=REPROVADO, senão APROVADO."
    )
    
    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    }
                ]
            }
        ],
        "temperature": 0
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response
    except Exception as e:
        return str(e)

# --- FLUXO PRINCIPAL ---
if st.button("🚀 Processar Notas") and arquivos:
    if not groq_key:
        st.error("Configure a API Key nos Secrets.")
        st.stop()

    resultados = []
    barra = st.progress(0)
    
    for idx, arq in enumerate(arquivos):
        try:
            img_b64 = preparar_imagem(arq)
            res = chamar_groq_vision(groq_key, img_b64, limite)
            
            if isinstance(res, requests.Response) and res.status_code == 200:
                texto = res.json()['choices'][0]['message']['content']
                p = texto.split('|')
                
                # Limpa o valor para conversão numérica
                v_limpo = re.sub(r'[^\d.]', '', p[0].replace(',', '.'))
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": float(v_limpo) if v_limpo else 0.0,
                    "Local": p[1].strip() if len(p) > 1 else "N/A",
                    "Categoria": p[2].strip() if len(p) > 2 else "Geral",
                    "Status": p[3].strip().upper() if len(p) > 3 else "ERRO"
                })
            else:
                detalhe = res.text if hasattr(res, 'text') else str(res)
                st.error(f"Erro em {arq.name}: {detalhe}")
        except Exception as e:
            st.error(f"Falha técnica: {e}")
        
        barra.progress((idx + 1) / len(arquivos))

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        st.subheader("📊 Resultados da Auditoria")
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status',
                                  color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'}), 
                            use_container_width=True)
        with col2:
            st.plotly_chart(px.pie(df, names='Status', hole=0.4), use_container_width=True)
            
        st.dataframe(df, use_container_width=True)
