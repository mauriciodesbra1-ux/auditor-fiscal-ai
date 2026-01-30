# --------------------------------------------------------------
# auditor_fiscal_ai.py
# --------------------------------------------------------------

import streamlit as st
import requests
import base64
import pandas as pd
import re
import plotly.express as px
from PIL import Image
import io

# --------------------------------------------------------------
# 1️⃣ CONFIGURAÇÃO DA PÁGINA
# --------------------------------------------------------------
st.set_page_config(
    page_title="Auditor Fiscal AI 2026",
    layout="wide",
    page_icon="🛡️"
)

# --------------------------------------------------------------
# 2️⃣ LOGIN SIMPLES (mantido em sessão)
# --------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login de Auditoria")
    with st.form("login"):
        usuario = st.text_input("Usuário")
        senha   = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if usuario == "admin" and senha == "auditor2026":
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")
    st.stop()          # impede a execução do restante até logar

# --------------------------------------------------------------
# 3️⃣ INTERFACE PRINCIPAL
# --------------------------------------------------------------
st.title("🛡️ Sistema de Auditoria Fiscal")
st.caption("Conectado via Groq LPU – Modelos Llama 3.2 Produção (2026)")

# -----------------------------------------------------------------
# 3.1 Chave da API (primeiro tenta nos Secrets, depois no sidebar)
# -----------------------------------------------------------------
groq_key = st.secrets.get("GROQ_API_KEY", "")
if not groq_key:
    groq_key = st.sidebar.text_input("Groq API Key", type="password")

# -----------------------------------------------------------------
# 3.2 Configurações da auditoria (sidebar)
# -----------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações")
    limite = st.number_input(
        "Limite de Reembolso (R$)",
        min_value=0.0,
        value=250.0,
        step=10.0,
        format="%.2f"
    )
    st.divider()
    st.info("Modelo em uso: **llama-3.2-11b-vision (Stable)**")

# -----------------------------------------------------------------
# 3.3 Upload das notas fiscais (imagens)
# -----------------------------------------------------------------
arquivos = st.file_uploader(
    "Carregar fotos das notas",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=True
)

# --------------------------------------------------------------
# 4️⃣ FUNÇÕES AUXILIARES
# --------------------------------------------------------------

def preparar_imagem(upload):
    """
    Recebe um UploadedFile do Streamlit, converte para RGB,
    redimensiona para no máximo 1024 px (economia de tokens)
    e devolve a string base64 pronta para a API.
    """
    img = Image.open(upload)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def chamar_groq_vision(api_key: str, b64_img: str, teto: float):
    """
    Envia a imagem para o endpoint de *vision* da Groq.
    Retorna a resposta `requests.Response` e, em caso de exceção,
    a mensagem de erro.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    modelo = "llama-3.2-11b-vision"   # modelo de produção (sem -preview)

    prompt = (
        f"Extraia rigorosamente: VALOR|LOCAL|CATEGORIA|STATUS. "
        f"Regra: Se valor total > {teto}, STATUS=REPROVADO, senão APROVADO. "
        "Retorne apenas a string separada por pipe."
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
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        return resp, None
    except Exception as exc:
        return None, str(exc)


# --------------------------------------------------------------
# 5️⃣ FLUXO PRINCIPAL (executa quando o usuário clica no botão)
# --------------------------------------------------------------
if st.button("🔍 Iniciar Auditoria") and arquivos:
    # ----------------------------------------------------------
    # 5.1 Verifica se a chave da API está disponível
    # ----------------------------------------------------------
    if not groq_key:
        st.error("⚠️ GROQ_API_KEY não configurada nos Secrets.")
        st.stop()

    resultados = []
    barra = st.progress(0)          # barra de progresso
    status_placeholder = st.empty() # placeholder para mensagens de status

    # ----------------------------------------------------------
    # 5.2 Processa cada imagem enviada
    # ----------------------------------------------------------
    for i, arq in enumerate(arquivos):
        status_placeholder.text(f"🔎 Analisando: {arq.name}")

        try:
            # 5.2.1 Prepara a imagem em base64
            img_b64 = preparar_imagem(arq)

            # 5.2.2 Chama a API Groq
            resp, erro_tecnico = chamar_groq_vision(groq_key, img_b64, limite)

            # ------------------------------------------------------
            # 5.2.3 Trata a resposta da API
            # ------------------------------------------------------
            if resp and resp.status_code == 200:
                # Exemplo de retorno esperado: "123,45|Supermercado XYZ|Alimentação|APROVADO"
                texto = resp.json()["choices"][0]["message"]["content"]
                partes = texto.split("|")

                # ---------- Parsing seguro ----------
                # 1) Valor (converte vírgula → ponto, remove tudo que não seja número)
                v_raw = re.sub(r"[^\d.]", "", partes[0].replace(",", "."))
                v_num = float(v_raw) if v_raw else 0.0

                # 2) Campos opcionais (evita IndexError)
                local     = partes[1].strip() if len(partes) > 1 else "Desconhecido"
                categoria = partes[2].strip() if len(partes) > 2 else "Geral"
                status    = partes[3].strip().upper() if len(partes) > 3 else "ERRO"

                resultados.append({
                    "Arquivo": arq.name,
                    "Valor (R$)": v_num,
                    "Local": local,
                    "Categoria": categoria,
                    "Status": status
                })

            elif resp:  # API respondeu, mas com código de erro
                detalhe = resp.json().get("error", {}).get("message", "Erro na API")
                st.error(f"❌ Erro em {arq.name}: {detalhe}")

            else:       # Falha de conexão / exceção
                st.error(f"⚠️ Erro de conexão em {arq.name}: {erro_tecnico}")

        except Exception as exc:
            st.error(f"⚠️ Falha inesperada ao processar {arq.name}: {exc}")

        # Atualiza a barra de progresso
        barra.progress((i + 1) / len(arquivos))

    # ----------------------------------------------------------
    # 5.3 Limpa o placeholder de status
    # ----------------------------------------------------------
    status_placeholder.empty()

    # ----------------------------------------------------------
    # 5.4 Exibe resultados (se houver)
    # ----------------------------------------------------------
    if resultados:
        df = pd.DataFrame(resultados)

        st.divider()
        # ---- Métricas rápidas ----
        col1, col2, col3 = st.columns(3)
        col1.metric("Processados", len(df))
        col2.metric("Total (R$)", f"R$ {df['Valor (R$)'].sum():.2f}")
        col3.metric("Aprovados", len(df[df["Status"] == "APROVADO"]))

        # ---- Visualizações ----
        st.subheader("📊 Análise de Dados")
        c_bar, c_pie = st.columns(2)

        with c_bar:
            fig_bar = px.bar(
                df,
                x="Categoria",
                y="Valor (R$)",
                color="Status",
                color_discrete_map={
                    "APROVADO": "#2ecc71",
                    "REPROVADO": "#e74c3c",
                    "ERRO": "#f1c40f"
                },
                title="Valor por Categoria"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with c_pie:
            fig_pie = px.pie(
                df,
                names="Status",
                title="Resumo de Status",
                color="Status",
                color_discrete_map={
                    "APROVADO": "#2ecc71",
                    "REPROVADO": "#e74c3c",
                    "ERRO": "#f1c40f"
                }
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # ---- Tabela e exportação ----
        st.subheader("📄 Relatório")
        st.dataframe(df, use_container_width=True)

        csv_bytes = df.to_csv(index=False, encoding="utf-8").encode()
        st.download_button(
            label="📥 Exportar Relatório (CSV)",
            data=csv_bytes,
            file_name="auditoria.csv",
            mime="text/csv"
        )
    else:
        st.warning("⚠️ Nenhum resultado foi obtido.")
