import streamlit as st
from google import genai # Importar a biblioteca do Google GenAI
from google.genai.errors import APIError

st.set_page_config(page_title="Assistente de Consulta Gemini", layout="wide")

st.title("🩺 Assistente de Consulta Gemini")

# Inicializa o cliente Gemini
# A chave de API deve ser configurada em .streamlit/secrets.toml como
# GOOGLE_API_KEY="SUA_CHAVE_AQUI"
try:
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("ERRO: Chave 'GOOGLE_API_KEY' não encontrada nos segredos do Streamlit. Por favor, adicione sua chave de API do Gemini em .streamlit/secrets.toml.")
    st.stop()
except Exception as e:
    st.error(f"ERRO ao inicializar o cliente Gemini: {e}")
    st.stop()

# Usaremos o modelo 'gemini-2.5-flash' ou outro modelo de chat/texto adequado.
GEMINI_MODEL = "gemini-2.5-flash" 

st.markdown("""
O assistente trabalha em 4 etapas:
1️⃣ **Caixa 1** – Informação crua  
2️⃣ **Caixa 2** – Aplica Prompt PEC1 atualizado  
3️⃣ **Caixa 3** – Sugestões e condutas  
4️⃣ **Caixa 4** – Chat livre com Gemini  
---
""")

# --- Layout das Caixas de Texto ---
col1, col2, col3 = st.columns(3)

with col1:
    caixa1 = st.text_area("CAIXA 1 - Informação Crua", height=250, key="caixa1")

with col2:
    caixa2 = st.text_area("CAIXA 2 - Prompt PEC1 Atualizado", height=250, key="caixa2")

with col3:
    caixa3 = st.text_area("CAIXA 3 - Sugestões e Discussão", height=250, key="caixa3")

caixa4 = st.text_input("CAIXA 4 - Chat com Gemini", key="caixa4")

# --- Layout dos Botões ---
colA, colB, colC = st.columns([1, 1, 2])

with colA:
    if st.button("🧹 LIMPAR"):
        for key in ["caixa1","caixa2","caixa3","caixa4"]:
            # Limpa o valor das chaves no session_state
            st.session_state[key] = ""
        st.rerun()

with colB:
    if st.button("📋 COPIAR CAIXA 2"):
        st.write("Conteúdo da Caixa 2 copiado (copie manualmente abaixo):")
        # st.code exibe o conteúdo para que o usuário possa copiar manualmente
        st.code(st.session_state.get("caixa2", "")) 

with colC:
    aplicar = st.button("⚙️ Aplicar Prompt PEC1")

# --- Função de Chamada do Gemini ---
def gemini_reply(system_instruction, text_input):
    """Função para chamar o modelo Gemini com instruções de sistema."""
    
    # O SDK do Gemini usa 'system_instruction' no parâmetro 'config'
    config = genai.types.GenerateContentConfig(
        system_instruction=system_instruction
    )
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=text_input, # O conteúdo a ser processado pelo modelo
            config=config 
        )
        return response.text.strip()
    except APIError as e:
        st.error(f"Erro da API do Gemini: {e}")
        return f"ERRO NA API: {e}"
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
        return f"ERRO INESPERADO: {e}"

# --- Etapa 2: Aplicar Prompt PEC1 ---
if aplicar and caixa1:
    with st.spinner("Aplicando Prompt PEC1..."):
        # Role do sistema para a Etapa 2
        system_role_pec1 = "Você é um assistente de processamento de texto. Sua tarefa é aplicar o 'Prompt PEC1 atualizado' ao texto de entrada, formatando e estruturando-o conforme as diretrizes do PEC1."
        
        st.session_state["caixa2"] = gemini_reply(
            system_role_pec1,
            caixa1
        )
        st.success("✅ Prompt aplicado!")

# --- Etapa 3: Gerar Sugestões ---
# Só exibe o botão se a Caixa 2 tiver conteúdo
if st.session_state.get("caixa2"):
    if st.button("💬 Gerar Sugestões (Caixa 3)"):
        with st.spinner("Analisando diagnóstico..."):
            # Role do sistema para a Etapa 3
            system_role_sugestoes = "Você é um assistente médico de IA. Analise cuidadosamente o texto processado, que já está formatado com o Prompt PEC1, e gere sugestões de diagnósticos diferenciais e condutas médicas apropriadas. Seja claro, conciso e use linguagem médica profissional."
            
            st.session_state["caixa3"] = gemini_reply(
                system_role_sugestoes,
                st.session_state["caixa2"]
            )
            st.success("✅ Sugestões geradas!")

# --- Etapa 4: Chat Livre ---
if caixa4:
    if st.button("💭 Enviar Chat (Caixa 4)"):
        with st.spinner("Respondendo..."):
            # Role do sistema para a Etapa 4
            system_role_chat = "Você é um assistente de chat geral e prestativo. Responda à pergunta do usuário. Mantenha o contexto de ser um assistente, mas responda de forma livre."
            
            resposta = gemini_reply(system_role_chat, caixa4)
            st.markdown(f"**Gemini:** {resposta}")

# --- ANOTAÇÕES HISTÓRICAS (MANTIDAS COMO COMENTÁRIOS) ---
# O bloco de código abaixo estava causando um erro de sintaxe (duplicação de função e texto solto).
# Ele foi removido e a função gemini_reply original (definida acima) foi mantida.
#
# # Modelo:
# # Defini um modelo Gemini: GEMINI_MODEL = "gemini-2.5-flash". Você pode usar outro modelo, como gemini-2.5-pro, se precisar de raciocínio mais complexo.
# # Função de Chamada (gemini_reply):
# # Substituímos a chamada client.chat.completions.create(...) pela chamada client.models.generate_content(...).
# # O papel do sistema (o role: "system") no Gemini é passado através do parâmetro config como system_instruction. Isso é crucial para as etapas 2 e 3.
#
# # A redefinição de gemini_reply abaixo foi removida:
# # def gemini_reply(system_instruction, text_input):
# #     config = genai.types.GenerateContentConfig(
# #         system_instruction=system_instruction
# #     )
# #     response = client.models.generate_content(
# #         model=GEMINI_MODEL,
# #         contents=text_input,
# #         config=config 
# #     )
# #     return response.text.strip()
