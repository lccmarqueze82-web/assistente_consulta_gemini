import streamlit as st
from google import genai
from google.genai.errors import APIError

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
# Define o layout wide para usar mais espaço horizontal
st.set_page_config(page_title="ASSISTENTE DE CONSULTA GEMINI", layout="wide")

# --- AJUSTE CSS PARA REDUZIR ESPAÇO SUPERIOR E MARGENS (OTIMIZAÇÃO VERTICAL) ---
# Otimização do layout para reduzir espaço entre widgets e eliminar rolagem vertical
st.markdown("""
    <style>
    /* Remove espaço padrão acima do título (principal ajuste para subir tudo) */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    /* Reduz margens de título e widgets */
    h1 {
        margin-bottom: 0.5rem !important;
    }
    .stText, .stTextArea, .stButton, .stTextInput, .stExpander {
        margin-bottom: 0.5rem !important;
    }
    /* Estilo para padronizar todos os botões (altura fixa de 48px) */
    div.stButton > button {
        width: 100%;
        height: 48px;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }
    /* Estilo para a caixa de input de chat (reduzindo altura superior) */
    .stTextInput {
        margin-top: 0.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("ASSISTENTE DE CONSULTA GEMINI")

GEMINI_MODEL = "gemini-2.5-flash"

# --- PROMPTS COMO CONSTANTES (COM REGRAS DE FORMATO FINAL DO PEC) ---

SYSTEM_ROLE_PEC1 = r"""
VOCÊ É O ASSISTENTE DE DOCUMENTAÇÃO CLÍNICA PEC1. SUA ÚNICA FUNÇÃO É GERAR O REGISTRO CLÍNICO FINAL. **SIGA AS REGRAS DE FORMATAÇÃO E LÓGICA ESTRITAMENTE**.

**PROIBIDO:** INTRODUÇÕES, COMENTÁRIOS, NUMERAÇÕES DE ITENS, PERGUNTAS, OU QUALQUER TEXTO FORA DA ESTRUTURA OBRIGATÓRIA.

### **1. FORMATO DE SAÍDA OBRIGATÓRIO (TEXTO SIMPLES)**

GERE O REGISTRO **INTEIRAMENTE EM CAIXA ALTA** E NESTA ORDEM. **OMITA** A SEÇÃO `AVALIAÇÃO MULTIDIMENSIONAL` SE NÃO FOR APLICÁVEL.

HMA:
HPP:
MUC:
EX FISICO:
AVALIAÇÃO MULTIDIMENSIONAL:
EXAMES:
HD:
CONDUTA:

VERIFICAÇÃO BEERS / STOPP-START:

GARANTIA DE ESTÉTICA: O REGISTRO DEVE SER GERADO INTEGRALMENTE COMO **TEXTO SIMPLES**. **REMOVER TODOS OS CARACTERES MARKDOWN (***, **, #, ETC)**.
**AS REGRAS DE QUEBRA DE LINHA SÃO:**
1. **RÓTULOS DE SEÇÃO** (HMA:, HPP:, MUC:, EX FISICO:, EXAMES:, HD:, CONDUTA:, VERIFICAÇÃO BEERS / STOPP-START:) DEVEM FICAR EM UNA **LINHA PRÓPRIA**.
2. O CONTEÚDO DE CADA SEÇÃO COMEÇA NA LINHA IMEDIATAMENTE ABAIXO DO RÓTULO.
3. DEVE HAVER **EXATAMENTE UMA LINHA VAZIA** APÓS A ÚLTIMA LINHA DE CONTEÚDO DE CADA SEÇÃO.

### **2. REGRAS DE EXCEÇÃO E MARCADORES TEMPORAIS**

* **RENOVAÇÃO NÃO PRESENCIAL (##01/##02):**
    * **##01:** HMA: "RENOVAÇÃO NÃO PRESENCIAL DE RECEITA." | EX FISICO: "IMPOSSÍVEL, PACIENTE NÃO PRESENTE NO MOMENTO." | CONDUTA: INCLUIR "ORIENTADA A COMPARECER À CONSULTA AGENDADA." E "CÓDIGO DE ÉTICA MÉDICA – ARTIGO 37."
    * **##02 (FORA DE ÁREA):** IGUAL AO ##01, MAS HMA: "RENOVAÇÃO NÃO PRESENCIAL DE RECEITA; IDENTIFICAÇÃO DE PACIENTE FORA DE ÁREA." | CONDUTA: ADICIONAR "ATUALIZAR ENDEREÇO DO PACIENTE NO CADASTRO."
* **RENOVAÇÃO NÃO PRESENCIAL CONSECUTIVA (REGRA FINAL):**
    * **SE** O ATENDIMENTO ATUAL FOR **##01 OU ##02 E** O ATENDIMENTO ANTERIOR TAMBÉM FOI **##01 OU ##02**, **ENTÃO SUBSTITUA** `HD:` E `CONDUTA:` POR:
        * HD: `SOLICITAÇÃO DE RENOVAÇÃO NÃO PRESENCIAL DE RECEITA MUC (SEGUNDO EPISÓDIO).`
        * CONDUTA: `SUGIRO AGENDAMENTO DE CONSULTA PRESENCIAL. CÓDIGO DE ÉTICA MÉDICA – ARTIGO 37: É VEDADO PRESCREVER SEM AVALIAÇÃO DIRETA DO PACIENTE, EXCETO EM SITUAÇÕES DE URGÊNCIA OU EM CASO DE CONTINUIDADE DE TRATAMENTO JÁ INICIADO.`
    * **NÃO** APLIQUE CONDUTAS AUTOMÁTICAS (≥65 ANOS, DM, RASTREIOS) NESTE CASO.

### **3. REGRAS POR SEÇÃO**

| SEÇÃO | REGRA DE CONTEÚDO E FORMATAÇÃO |
| :--- | :--- |
| **HMA** | **ORDEM FIXA (UMA LINHA POR ITEM):** 1. MOTIVO; 2. FORA DE ÁREA (SE APLICÁVEL); 3. IDADE E SEXO; 4. TEMPO DESDE ÚLTIMO ATENDIMENTO; 5. QUEIXAS/SINTOMAS. **PROIBIDO:** INCLUIR GATILHOS GERIÁTRICOS. |
| **HPP** | LINHA ÚNICA. DOENÇAS SEPARADAS POR `;`. USAR `DIAGNÓSTICO (CID-10)` SEMPRE. SE NÃO HOUVER: `NEGA COMORBIDADES.` |
| **MUC** | LINHA ÚNICA. MEDICAMENTOS SEPARADOS POR `;`. BENZODIAZEPÍNICOS EM **CAIXA ALTA ENTRE PARÊNTESES SIMPLES**. SE NÃO HOUVER: `SEM MEDICAMENTOS DE USO CONTÍNUO.` |
| **EX FISICO** | PRESENCIAL: `BEG, EUPNEICO, LOTE, FC E PA AFERIDAS POR ENFERMAGEM; [ACHADOS].` NÃO PRESENCIAL: `IMPOSSÍVEL, PACIENTE NÃO PRESENTE NO MOMENTO.` |
| **AVALIAÇÃO MULTIDIMENSIONAL** | **REQUISITOS:** APENAS SE (IDADE ≥65 ANOS **E** GATILHO GERIÁTRICO PRESENTE). USE O MODELO PADRÃO. **ALTERE E DESTAQUE** O ACHADO APENAS EM **CAIXA ALTA ENTRE PARENTESES SIMPLES** (EX: (FRAQUEZA EM MEMBROS INFERIORES)). |
| **EXAMES** | LINHA ÚNICA. EXAMES ALTERADOS EM **CAIXA ALTA ENTRE PARANTESES SIMPLES**. DATA (MM/AA). MANTER ALTERADOS DE QUALQUER ÉPOCA E NORMAIS <1 ANO. CALCULAR CKD-EPI (2021) E CLASSIFICAR DRC SE CREATININA+IDADE+SEXO DISPONÍVEIS. SE NÃO HOUVER: `SEM EXAMES DISPONÍVEIS.` |
| **HD** | UM DIAGNÓSTICO (NOVO OU DESCOMPENSADO) POR LINHA. DIAGNÓSTICO INCERTO: `*`. |
| **CONDUTA** | UMA AÇÃO POR LINHA. **SEMPRE INCLUIR:** `MANTER MEDICAMENTOS DE USO CONTÍNUO.`; `MANTER SOLICITAÇÕES ANTERIORES EM ANDAMENTO.`. **INCLUIR** CONDUTAS AUTOMÁTICAS (≥65 ANOS, DM, RASTREIOS - VIDE PROTOCOLO). **JUSTIFICAR TODOS OS `*`** NO FINAL DESTA SEÇÃO. |

### **4. ALERTA FARMACÊUTICO (BEERS / STOPP-START)**

* **APLICAR** ESTA SEÇÃO APENAS PARA PACIENTES ≥65 ANOS COM MUC.
* USE OS MODELOS DE ALERTA **INICIANDO COM "ALERTA: "** PARA BEERS/STOPP OU **"OMISSÃO TERAPÊUTICA: "** PARA START.
"""

SYSTEM_ROLE_SUGESTOES = "Você é um assistente médico de IA. Analise cuidadosamente o texto processado, que já está formatado com o Prompt PEC1, e gere sugestões de diagnósticos diferenciais e condutas médicas apropriadas. Seja claro, conciso e use linguagem médica profissional."

SYSTEM_ROLE_CHAT = "Você é um assistente de chat geral e prestativo. Responda à pergunta do usuário. Mantenha o contexto de ser um assistente, mas responda de forma livre."


# --- INICIALIZAÇÃO DO CLIENTE GEMINI ---
try:
    # Acessa a chave de API do Gemini a partir dos segredos do Streamlit
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("ERRO: Chave 'GOOGLE_API_KEY' não encontrada nos segredos do Streamlit. Por favor, adicione sua chave de API do Gemini em .streamlit/secrets.toml.")
    st.stop()
except Exception as e:
    st.error(f"ERRO ao inicializar o cliente Gemini: {e}")
    st.stop()


# --- FUNÇÃO DE CHAMADA DO GEMINI ---
def gemini_reply(system_instruction, text_input):
    """Função para chamar o modelo Gemini com instruções de sistema."""
    
    config = genai.types.GenerateContentConfig(
        system_instruction=system_instruction
    )
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=text_input,
            config=config
        )
        return response.text.strip()
    except APIError as e:
        st.error(f"Erro da API do Gemini: {e}")
        return f"ERRO NA API: {e}"
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
        return f"ERRO INESPERADO: {e}"


# --- INICIALIZAÇÃO DO ESTADO DE SESSÃO ---
# Inicializa todas as chaves do st.session_state
for key in ["caixa1", "caixa2", "caixa3", "caixa4", "chat_response", "show_manual_copy"]:
    if key not in st.session_state:
        st.session_state[key] = False if key == "show_manual_copy" else ""


# --- FUNÇÕES DE CALLBACK ---

def clear_fields():
    """Callback para a função LIMPAR: Reseta todos os campos de estado da sessão."""
    for key in ["caixa1","caixa2","caixa3","caixa4", "chat_response", "show_manual_copy"]:
        # Reset para valor vazio ou False
        st.session_state[key] = "" if key != "show_manual_copy" else False

def apply_pec1():
    """Callback para a Etapa 2: Aplica Prompt PEC1 e atualiza Caixa 2."""
    if not st.session_state.get("caixa1"):
        st.warning("A Caixa 1 está vazia. Insira a informação crua primeiro.")
        return

    st.session_state["show_manual_copy"] = False

    with st.spinner("Aplicando Prompt PEC1..."):
        st.session_state["caixa2"] = gemini_reply(
            SYSTEM_ROLE_PEC1,
            st.session_state["caixa1"]
        )
        # st.success("Prompt aplicado!", icon="✅") # Mensagem de sucesso opcional

def generate_suggestions():
    """Callback para a Etapa 3: Gerar Sugestões e atualizar Caixa 3."""
    if not st.session_state.get("caixa2"):
        st.warning("A Caixa 2 está vazia. Aplique o Prompt PEC1 (Etapa 2) primeiro.")
        return

    st.session_state["show_manual_copy"] = False

    with st.spinner("Analisando diagnóstico..."):
        st.session_state["caixa3"] = gemini_reply(
            SYSTEM_ROLE_SUGESTOES,
            st.session_state["caixa2"]
        )
        # st.success("Sugestões geradas!", icon="💡") # Mensagem de sucesso opcional

def send_chat():
    """Callback para a Etapa 4: Chat Livre e exibe resposta no Markdown."""
    if not st.session_state.get("caixa4"):
        st.warning("A Caixa 4 está vazia. Digite sua pergunta.")
        return

    st.session_state["show_manual_copy"] = False

    with st.spinner("Respondendo..."):
        resposta = gemini_reply(SYSTEM_ROLE_CHAT, st.session_state["caixa4"])
        st.session_state["chat_response"] = resposta

def copy_caixa2_content():
    """Inverte a flag para exibir/ocultar o bloco de cópia (st.text_area disabled)."""
    st.session_state["show_manual_copy"] = not st.session_state.get("show_manual_copy", False)


# --- MARCADOR E EXPANDER DAS REGRAS ---

st.markdown("---")

# Expander para as regras
with st.expander("Ver Regras Completas do Prompt PEC1"):
    st.code(SYSTEM_ROLE_PEC1, language="markdown")


# --- LAYOUT DAS CAIXAS DE TEXTO ---
col1, col2, col3 = st.columns(3)

# ALTURA OTIMIZADA PARA 120PX (REDUZINDO ESPAÇO)
OPTIMIZED_HEIGHT = 120

with col1:
    st.text_area("SOAP (Informação Crua)", height=OPTIMIZED_HEIGHT, key="caixa1",
                 help="Insira aqui o texto de entrada (anotações, dados brutos, etc.)")

with col2:
    st.text_area("CORRIGIDO (Formato PEC1)", height=OPTIMIZED_HEIGHT, key="caixa2",
                 help="Saída formatada do Gemini conforme as regras PEC1. Use o botão 'COPIAR' para obter o texto puro.")

with col3:
    st.text_area("Sugestões e Discussão", height=OPTIMIZED_HEIGHT, key="caixa3",
                 help="Sugestões de diagnósticos, condutas e discussão geradas pelo Gemini.")

st.markdown("---")

# --- LAYOUT DOS BOTÕES DE CONTROLE ---
# Colunas para alinhar e padronizar botões
colA, colB, colC, colD = st.columns(4)

# Verifica conteúdo para habilitar/desabilitar botões
caixa1_has_content = bool(st.session_state.get("caixa1", "").strip())
caixa2_has_content = bool(st.session_state.get("caixa2", "").strip())
caixa4_has_content = bool(st.session_state.get("caixa4", "").strip())

with colA:
    st.button("LIMPAR TUDO", on_click=clear_fields)

with colB:
    label_copy = "OCULTAR CÓPIA" if st.session_state.get("show_manual_copy") else "COPIAR"
    st.button(label_copy, on_click=copy_caixa2_content, disabled=not caixa2_has_content,
              help="Alterna a visualização de um campo de texto com botão de cópia nativo (texto puro).")

with colC:
    st.button("APLICAR PEC1", on_click=apply_pec1,
              disabled=not caixa1_has_content, help="Aplica o prompt de formatação PEC1 na Caixa 1 e envia para a Caixa 'CORRIGIDO'.")

with colD:
    st.button("GERAR SUGESTÕES", on_click=generate_suggestions,
              disabled=not caixa2_has_content, help="Gera sugestões de diagnóstico e conduta com base no texto da Caixa 'CORRIGIDO'.")


# --- EXIBIÇÃO DO BLOCO DE CÓPIA (USANDO ST.TEXT_AREA DESABILITADO) ---
if st.session_state.get("show_manual_copy") and caixa2_has_content:
    st.markdown("### Bloco de Cópia - Formato Final (CORRIGIDO)")
    st.info("O texto abaixo está no formato Texto Simples exigido pelo PEC. **Use o botão de cópia (dois quadrados) no canto superior direito do campo** para garantir que o texto e as quebras de linha sejam copiados corretamente.")

    # Ajusta a altura dinamicamente para melhor visualização (min: 150px, max: 600px)
    text_length = len(st.session_state["caixa2"].split('\n')) * 22
    # Ajustei o mínimo para 150px, mantendo o máximo para não estourar a tela com um registro gigantesco
    copy_height = max(150, min(600, text_length))

    # O st.text_area desabilitado é a melhor forma de garantir a cópia literal de texto puro
    st.text_area(
        "Cópia Final",
        value=st.session_state["caixa2"],
        height=copy_height,
        key="caixa2_copy_block",
        disabled=True,
        label_visibility="collapsed"
    )
elif st.session_state.get("show_manual_copy") and not caixa2_has_content:
    # Se o botão foi clicado, mas a caixa 2 está vazia
    st.warning("A Caixa CORRIGIDO está vazia. Não há conteúdo para copiar.")
    st.session_state["show_manual_copy"] = False


# --- CHAT LIVRE (CAIXA 4) E BOTÃO DE ENVIO ---
st.markdown("---")

colE, colF = st.columns([5, 1])

with colE:
    # A visibilidade do label está oculta, o placeholder guia o usuário
    st.text_input("Pergunta para o Gemini", key="caixa4", label_visibility="collapsed",
                  placeholder="Chat Livre: Digite sua pergunta (ex: 'Qual a dose máxima de metformina?')",
                  help="Digite sua pergunta livre para o Gemini.")

with colF:
    # Ajuste de layout manual para o botão ENVIAR (para alinhar com o text_input)
    # A margem superior no CSS já ajuda a alinhar, aqui só garantimos o espaço.
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.button("ENVIAR", on_click=send_chat, disabled=not caixa4_has_content, key="chat-button")

# --- EXIBIÇÃO DO RESULTADO DO CHAT (Etapa 4) ---
if st.session_state.get("chat_response"):
    st.markdown("---")
    # Para o chat, mantemos o st.markdown para renderizar a formatação da resposta do Gemini
    st.markdown(f"**Gemini Responde:** {st.session_state['chat_response']}")
    st.markdown("---")
