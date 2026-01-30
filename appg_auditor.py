import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Auditor Fiscal AI 2026", layout="wide", page_icon="🛡️")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Acesso Restrito")
    with st.form("login"):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u == "admin" and p == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciais incorretas")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Auditoria Fiscal AI (Modo Contorno)")
st.caption("Utilizando infraestrutura Groq LPU para evitar custos e erros de billing.")

# Chave API vinda dos Secrets do Streamlit
groq_key = st.secrets.get("GROQ_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configurações")
    limite_valor = st.number_input("Limite para Reprovação (R$)", value=250.0)
    st.divider()
    if not groq_key:
        st.error("⚠️ GROQ_API_KEY não encontrada nos Secrets!")
    else:
        st.success("✅ API Groq Conectada")

arquivos = st.file_uploader("Enviar Notas Fiscais", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

# --- FUNÇÕES TÉCNICAS ---
def preparar_imagem(upload):
    """Redimensiona e converte para B64 para evitar erro 413 (Payload Too Large)"""
    img = Image.open(upload)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def chamar_groq(api_key, b64_img, teto):
    """Chama o modelo Vision da Groq (Llama 3.2 11B)"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Modelo estável para Janeiro/2026
    payload = {
        "model": "llama-3.2-11b-vision-preview",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": f"Extraia os dados da nota: VALOR|LOCAL|CATEGORIA|STATUS. Regra: Se o valor > {teto}, STATUS=REPROVADO. Responda apenas o pipe."
                },
                {
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                }
            ]
        }],
        "temperature": 0
    }
    return requests.post(url, headers=headers, json=payload, timeout=30)

# --- FLUXO DE PROCESSAMENTO ---
if st.button("🚀 Iniciar Auditoria") and arquivos:
    if not groq_key:
        st.warning("Por favor, configure sua GROQ_API_KEY.")
        st.stop()

    resultados = []
    progresso = st.progress(0)
    
    for idx, arq in enumerate(arquivos):
        try:
            img_b64 = preparar_imagem(arq)
            response = chamar_groq(groq_key, img_b64, limite_valor)
            
            if response.status_code == 200:
                texto = response.json()['choices'][0]['message']['content']
                colunas = texto.split('|')
                
                # Limpeza do valor (remove R$, espaços, troca vírgula por ponto)
                v_limpo = re.sub(r'[^\d.]', '', colunas[0].replace(',', '.'))
                valor_final = float(v_limpo) if v_limpo else 0.0
                
                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": valor_final,
                    "Estabelecimento": colunas[1].strip() if len(colunas) > 1 else "N/A",
                    "Categoria": colunas[2].strip() if len(colunas) > 2 else "Geral",
                    "Status": colunas[3].strip().upper() if len(colunas) > 3 else "ERRO"
                })
            else:
                st.error(f"Erro no arquivo {arq.name}: {response.text}")
        except Exception as e:
            st.error(f"Falha técnica em {arq.name}: {e}")
        
        progresso.progress((idx + 1) / len(arquivos))

    if resultados:
        df = pd.DataFrame(resultados)
        st.divider()
        
        # Dashboard Visual
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(df, x='Categoria', y='Valor (R$)', color='Status', 
                                  color_discrete_map={'APROVADO':'#2ecc71', 'REPROVADO':'#e74c3c'}), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, names='Status', hole=0.4, title="Resumo do Status"), use_container_width=True)
            
        st.subheader("📋 Detalhamento")
        st.dataframe(df, use_container_width=True)
