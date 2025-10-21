import streamlit as st
from google import genai 
from google.genai.errors import APIError

st.set_page_config(page_title="Assistente de Consulta Gemini", layout="wide")

st.title("🩺 Assistente de Consulta Gemini")

# Inicializa o cliente Gemini
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

# --- Funções de Callback ---

def clear_fields():
    """Callback para a função LIMPAR: Reseta todos os campos de estado da sessão."""
    for key in ["caixa1","caixa2","caixa3","caixa4", "chat_response", "show_manual_copy"]:
        st.session_state[key] = ""

def apply_pec1():
    """Callback para a Etapa 2: Aplica Prompt PEC1 e atualiza Caixa 2."""
    if not st.session_state.get("caixa1"):
        st.warning("A Caixa 1 está vazia. Insira a informação crua primeiro.")
        return

    # Limpa a flag de cópia para não mostrar a caixa de código antiga
    st.session_state["show_manual_copy"] = False

    with st.spinner("Aplicando Prompt PEC1..."):
        system_role_pec1 = "Você é um assistente de processamento de texto. Sua tarefa é aplicar o 'Prompt PEC1 atualizado' ao texto de entrada, formatando e estruturando-lo conforme as diretrizes do PEC1."
        
        st.session_state["caixa2"] = gemini_reply(
            system_role_pec1,
            st.session_state["caixa1"]
        )
        st.success("✅ Prompt aplicado!")

def generate_suggestions():
    """Callback para a Etapa 3: Gerar Sugestões e atualizar Caixa 3."""
    if not st.session_state.get("caixa2"):
        st.warning("A Caixa 2 está vazia. Aplique o Prompt PEC1 (Etapa 2) primeiro.")
        return

    # Limpa a flag de cópia
    st.session_state["show_manual_copy"] = False

    with st.spinner("Analisando diagnóstico..."):
        system_role_sugestoes = "Você é um assistente médico de IA. Analise cuidadosamente o texto processado, que já está formatado com o Prompt PEC1, e gere sugestões de diagnósticos diferenciais e condutas médicas apropriadas. Seja claro, conciso e use linguagem médica profissional."
        
        st.session_state["caixa3"] = gemini_reply(
            system_role_sugestoes,
            st.session_state["caixa2"]
        )
        st.success("✅ Sugestões geradas!")

def send_chat():
    """Callback para a Etapa 4: Chat Livre e exibe resposta no Markdown."""
    if not st.session_state.get("caixa4"):
        st.warning("A Caixa 4 está vazia. Digite sua pergunta.")
        return

    # Limpa a flag de cópia
    st.session_state["show_manual_copy"] = False

    with st.spinner("Respondendo..."):
        system_role_chat = "Você é um assistente de chat geral e prestativo. Responda à pergunta do usuário. Mantenha o contexto de ser um assistente, mas responda de forma livre."
        
        resposta = gemini_reply(system_role_chat, st.session_state["caixa4"])
        st.session_state["chat_response"] = resposta
        
# Novo callback para o botão COPIAR
def copy_caixa2_content():
    """Define a flag para exibir o conteúdo da Caixa 2 para cópia manual."""
    # Apenas inverte o estado para exibir/ocultar a caixa de código
    st.session_state["show_manual_copy"] = not st.session_state.get("show_manual_copy", False)
        
# --- Inicializa o estado de exibição (IMPORTANTE) ---
if "caixa1" not in st.session_state: st.session_state["caixa1"] = ""
if "caixa2" not in st.session_state: st.session_state["caixa2"] = ""
if "caixa3" not in st.session_state: st.session_state["caixa3"] = ""
if "caixa4" not in st.session_state: st.session_state["caixa4"] = ""
if "chat_response" not in st.session_state: st.session_state["chat_response"] = ""
if "show_manual_copy" not in st.session_state: st.session_state["show_manual_copy"] = False


# --- Layout das Caixas de Texto (Todas Editáveis) ---
col1, col2, col3 = st.columns(3)

with col1:
    st.text_area("CAIXA 1 - Informação Crua", height=250, key="caixa1")

with col2:
    st.text_area("CAIXA 2 - Prompt PEC1 Atualizado", height=250, key="caixa2")

with col3:
    st.text_area("CAIXA 3 - Sugestões e Discussão", height=250, key="caixa3")

st.text_input("CAIXA 4 - Chat com Gemini", key="caixa4")

# Determina se a Caixa 2 tem conteúdo
caixa2_content = st.session_state.get("caixa2", "").strip()
caixa2_has_content = bool(caixa2_content)

# --- Layout dos Botões ---
colA, colB, colC = st.columns([1, 1, 2])

with colA:
    st.button("🧹 LIMPAR", on_click=clear_fields) 

with colB:
    # Botão COPIAR usa o novo callback e é desabilitado se a Caixa 2 estiver vazia
    label_copy = "📋 OCULTAR CÓPIA" if st.session_state.get("show_manual_copy") else "📋 COPIAR CAIXA 2"
    st.button(label_copy, on_click=copy_caixa2_content, disabled=not caixa2_has_content) 

with colC:
    st.button("⚙️ Aplicar Prompt PEC1", on_click=apply_pec1)

# --- Exibição do Bloco de Cópia Manual (Novo elemento) ---
if st.session_state.get("show_manual_copy") and caixa2_has_content:
    st.info("O conteúdo da Caixa 2 foi exibido abaixo. **Use o botão de cópia nativo** do Streamlit dentro do bloco para copiá-lo.")
    st.code(caixa2_content)
elif st.session_state.get("show_manual_copy") and not caixa2_has_content:
    # Se o botão foi clicado, mas o conteúdo foi removido manualmente, ou houve race condition
    st.warning("A Caixa 2 está vazia. Não há conteúdo para copiar.")
    st.session_state["show_manual_copy"] = False # Limpa a flag
    
# --- Botão Etapa 3 (Também usando Callback) ---
if caixa2_has_content:
    st.button("💬 Gerar Sugestões (Caixa 3)", on_click=generate_suggestions)

# --- Botão Etapa 4 (Também usando Callback) ---
if st.session_state.get("caixa4"):
    st.button("💭 Enviar Chat (Caixa 4)", on_click=send_chat)

# --- Exibição do Resultado do Chat (Etapa 4) ---
if st.session_state.get("chat_response"):
    st.markdown("---")
    st.markdown(f"**Gemini:** {st.session_state['chat_response']}")
    st.markdown("---")
