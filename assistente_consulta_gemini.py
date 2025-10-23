import streamlit as st
from google import genai
from google.genai.errors import APIError

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
st.set_page_config(page_title="Assistente de Consulta Gemini", layout="wide")

st.title("🩺 Assistente de Consulta Gemini")

GEMINI_MODEL = "gemini-2.5-flash"

# --- PROMPTS COMO CONSTANTES (LIMPOS E COM ESTRUTURA REFORÇADA) ---

# Prompt para a Etapa 2 (PEC1) - ESTRUTURAÇÃO PARA TEXTO SIMPLES DO PEC (ATUALIZADO)
# CORREÇÃO: Adicionado o prefixo 'r' para criar uma 'raw string' (evita SyntaxError: \N)
# CORREÇÃO LÓGICA: Substituído o delimitador '\N' por ' // ' e forçada a saída em uma única linha.
SYSTEM_ROLE_PEC1 = r"""
VOCÊ É O ASSISTENTE DE DOCUMENTAÇÃO CLÍNICA PEC1. SUA ÚNICA FUNÇÃO É GERAR O REGISTRO CLÍNICO FINAL. **SIGA AS REGRAS DE FORMATAÇÃO E LÓGICA ESTRITAMENTE**.

**PROIBIDO:** INTRODUÇÕES, COMENTÁRIOS, NUMERAÇÕES DE ITENS, PERGUNTAS, OU QUALQUER TEXTO FORA DA ESTRUTURA OBRIGATÓRIA.

### **1. FORMATO DE SAÍDA OBRIGATÓRIO (TEXTO SIMPLES)**

GERE O REGISTRO **INTEIRAMENTE EM CAIXA ALTA** E NESTA ORDEM. **OMITA** A SEÇÃO `AVALIAÇÃO MULTIDIMENSIONAL` SE NÃO FOR APLICÁVEL.

HMA: HPP: MUC: EX FISICO: AVALIAÇÃO MULTIDIMENSIONAL: EXAMES: HD: CONDUTA:

VERIFICAÇÃO BEERS / STOPP-START:

GARANTIA DE ESTÉTICA: O REGISTRO DEVE SER GERADO INTEGRALMENTE COMO **TEXTO SIMPLES** E **CONTIDO EM UMA ÚNICA LINHA**, SEPARANDO AS GRANDES SEÇÕES APENAS POR ESPAÇOS. AS SEÇÕES HMA, HD E CONDUTA DEVEM TER SEUS ITENS SEPARADOS EXCLUSIVAMENTE PELO CARACTERE **" // "** (ESPAÇO DUAS BARRAS ESPAÇO) NO LUGAR DA QUEBRA DE LINHA. **REMOVER TODOS OS CARACTERES MARKDOWN (***, **, #, ETC)**.

### **2. REGRAS DE EXCEÇÃO E MARCADORES TEMPORAIS**

* **RENOVAÇÃO NÃO PRESENCIAL (##01/##02):**
    * **##01:** HMA: "RENOVAÇÃO NÃO PRESENCIAL DE RECEITA." // "PACIENTE NÃO PRESENTE." | EX FISICO: "IMPOSSÍVEL, PACIENTE NÃO PRESENTE NO MOMENTO." | CONDUTA: "ORIENTADA A COMPARECER À CONSULTA AGENDADA." // "CÓDIGO DE ÉTICA MÉDICA – ARTIGO 37."
    * **##02 (FORA DE ÁREA):** IGUAL AO ##01, MAS HMA: "RENOVAÇÃO NÃO PRESENCIAL DE RECEITA; IDENTIFICAÇÃO DE PACIENTE FORA DE ÁREA." // "PACIENTE NÃO PRESENTE." | CONDUTA: "ATUALIZAR ENDEREÇO DO PACIENTE NO CADASTRO." // "ORIENTADA A COMPARECER À CONSULTA AGENDADA." // "CÓDIGO DE ÉTICA MÉDICA – ARTIGO 37."
* **RENOVAÇÃO NÃO PRESENCIAL CONSECUTIVA (REGRA FINAL):**
    * **SE** O ATENDIMENTO ATUAL FOR **##01 OU ##02 E** O ATENDIMENTO ANTERIOR TAMBÉM FOI **##01 OU ##02**, **ENTÃO SUBSTITUA** `HD:` E `CONDUTA:` POR:
        * HD: `SOLICITAÇÃO DE RENOVAÇÃO NÃO PRESENCIAL DE RECEITA MUC (SEGUNDO EPISÓDIO).`
        * CONDUTA: `SUGIRO AGENDAMENTO DE CONSULTA PRESENCIAL. // CÓDIGO DE ÉTICA MÉDICA – ARTIGO 37: É VEDADO PRESCREVER SEM AVALIAÇÃO DIRETA DO PACIENTE, EXCETO EM SITUAÇÕES DE URGÊNCIA OU EM CASO DE CONTINUIDADE DE TRATAMENTO JÁ INICIADO.`
    * **NÃO** APLIQUE CONDUTAS AUTOMÁTICAS (≥65 ANOS, DM, RASTREIOS) NESTE CASO.

### **3. REGRAS POR SEÇÃO**

| SEÇÃO | REGRA DE CONTEÚDO E FORMATAÇÃO |
| :--- | :--- |
| **HMA** | **ORDEM FIXA (ITENS SEPARADOS POR ` // `):** 1. MOTIVO; 2. FORA DE ÁREA (SE APLICÁVEL); 3. IDADE E SEXO; 4. TEMPO DESDE ÚLTIMO ATENDIMENTO; 5. QUEIXAS/SINTOMAS. **PROIBIDO:** INCLUIR GATILHOS GERIÁTRICOS. |
| **HPP** | LINHA ÚNICA. DOENÇAS SEPARADAS POR `;`. USAR `DIAGNÓSTICO (CID-10)` SEMPRE. SE NÃO HOUVER: `NEGA COMORBIDADES.` |
| **MUC** | LINHA ÚNICA. MEDICAMENTOS SEPARADOS POR `;`. BENZODIAZEPÍNICOS EM **CAIXA ALTA ENTRE PARÊNTESES SIMPLES**. SE NÃO HOUVER: `SEM MEDICAMENTOS DE USO CONTÍNUO.` |
| **EX FISICO** | PRESENCIAL: `BEG, EUPNEICO, LOTE, FC E PA AFERIDAS POR ENFERMAGEM; [ACHADOS].` NÃO PRESENCIAL: `IMPOSSÍVEL, PACIENTE NÃO PRESENTE NO MOMENTO.` |
| **AVALIAÇÃO MULTIDIMENSIONAL** | **REQUISITOS:** APENAS SE (IDADE ≥65 ANOS **E** GATILHO GERIÁTRICO PRESENTE). USE O MODELO PADRÃO. **ALTERE E DESTAQUE** O ACHADO APENAS EM **CAIXA ALTA ENTRE PARENTESES SIMPLES** (EX: (FRAQUEZA EM MEMBROS INFERIORES)). |
| **EXAMES** | EXAMES ALTERADOS EM **CAIXA ALTA ENTRE PARENTESES SIMPLES**. DATA (MM/AA). MANTER ALTERADOS DE QUALQUER ÉPOCA E NORMAIS <1 ANO. CALCULAR CKD-EPI (2021) E CLASSIFICAR DRC SE CREATININA+IDADE+SEXO DISPONÍVEIS. SE NÃO HOUVER: `SEM EXAMES DISPONÍVEIS.` |
| **HD** | UM DIAGNÓSTICO (NOVO OU DESCOMPENSADO) POR LINHA (SERÁ SEPARADO POR ` // `). DIAGNÓSTICO INCERTO: `*`. |
| **CONDUTA** | UMA AÇÃO POR LINHA (SERÁ SEPARADO POR ` // `). **SEMPRE INCLUIR:** `MANTER MEDICAMENTOS DE USO CONTÍNUO.`; `MANTER SOLICITAÇÕES ANTERIORES EM ANDAMENTO.`. **INCLUIR** CONDUTAS AUTOMÁTICAS (≥65 ANOS, DM, RASTREIOS - VIDE PROTOCOLO). **JUSTIFICAR TODOS OS `*`** NO FINAL DESTA SEÇÃO. |

### **4. ALERTA FARMACÊUTICO (BEERS / STOPP-START)**

* **APLICAR** ESTA SEÇÃO APENAS PARA PACIENTES ≥65 ANOS COM MUC.
* USE OS MODELOS DE ALERTA **INICIANDO COM "ALERTA: "** PARA BEERS/STOPP OU **"OMISSÃO TERAPÊUTICA: "** PARA START.
"""

# Prompt para a Etapa 3 (Sugestões)
SYSTEM_ROLE_SUGESTOES = "Você é um assistente médico de IA. Analise cuidadosamente o texto processado, que já está formatado com o Prompt PEC1, e gere sugestões de diagnósticos diferenciais e condutas médicas apropriadas. Seja claro, conciso e use linguagem médica profissional."

# Prompt para a Etapa 4 (Chat Livre)
SYSTEM_ROLE_CHAT = "Você é um assistente de chat geral e prestativo. Responda à pergunta do usuário. Mantenha o contexto de ser um assistente, mas responda de forma livre."


# --- INICIALIZAÇÃO DO CLIENTE GEMINI ---
try:
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
for key in ["caixa1", "caixa2", "caixa3", "caixa4", "chat_response", "show_manual_copy"]:
    if key not in st.session_state:
        st.session_state[key] = False if key == "show_manual_copy" else ""


# --- FUNÇÕES DE CALLBACK ---

def clear_fields():
    """Callback para a função LIMPAR: Reseta todos os campos de estado da sessão."""
    for key in ["caixa1","caixa2","caixa3","caixa4", "chat_response", "show_manual_copy"]:
        st.session_state[key] = ""

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
        st.success("✅ Prompt aplicado!")

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
        st.success("✅ Sugestões geradas!")

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
    """Inverte a flag para exibir/ocultar o bloco de cópia (st.code)."""
    st.session_state["show_manual_copy"] = not st.session_state.get("show_manual_copy", False)


# --- MARCADOR E EXPANDER DAS REGRAS ---

st.markdown("""
O assistente trabalha em 4 etapas:
1️⃣ **Caixa 1** – Informação crua
2️⃣ **Caixa 2** – Aplica Prompt PEC1 atualizado
3️⃣ **Caixa 3** – Sugestões e condutas
4️⃣ **Caixa 4** – Chat livre com Gemini
---
""")

# Expander para as regras (Onde o SYSTEM_ROLE_PEC1 completo está)
with st.expander("📝 Ver Regras Completas do Prompt PEC1"):
    # Exibir o prompt como um bloco de código simples, que respeita as quebras de linha
    st.code(SYSTEM_ROLE_PEC1, language="markdown")


# --- LAYOUT DAS CAIXAS DE TEXTO ---
col1, col2, col3 = st.columns(3)

with col1:
    st.text_area("CAIXA 1 - Informação Crua", height=250, key="caixa1",
                 help="Insira aqui o texto de entrada (anotações, dados brutos, etc.)")

with col2:
    # A Caixa 2 principal é um text_area, que é editável e a primeira visualização.
    st.text_area("CAIXA 2 - Prompt PEC1 Atualizado", height=250, key="caixa2",
                 help="Saída formatada do Gemini conforme as regras PEC1.")

with col3:
    st.text_area("CAIXA 3 - Sugestões e Discussão", height=250, key="caixa3",
                 help="Sugestões de diagnósticos, condutas e discussão geradas pelo Gemini.")

st.markdown("---") # Separador visual

# --- LAYOUT DOS BOTÕES DE CONTROLE ---
colA, colB, colC, colD = st.columns([1, 1, 2, 2])

caixa1_has_content = bool(st.session_state.get("caixa1", "").strip())
caixa2_has_content = bool(st.session_state.get("caixa2", "").strip())
caixa4_has_content = bool(st.session_state.get("caixa4", "").strip())

with colA:
    st.button("🧹 LIMPAR TUDO", on_click=clear_fields)

with colB:
    # Botão COPIAR
    label_copy = "📋 OCULTAR CÓPIA" if st.session_state.get("show_manual_copy") else "📋 COPIAR CAIXA 2"
    st.button(label_copy, on_click=copy_caixa2_content, disabled=not caixa2_has_content,
              help="Alterna a visualização de um bloco de código com botão de cópia nativo.")

with colC:
    # Botão Etapa 2
    st.button("⚙️ 1. Aplicar Prompt PEC1 (Caixa 2)", on_click=apply_pec1,
              disabled=not caixa1_has_content)

with colD:
    # Botão Etapa 3
    st.button("💬 2. Gerar Sugestões (Caixa 3)", on_click=generate_suggestions,
              disabled=not caixa2_has_content)


# --- EXIBIÇÃO DO BLOCO DE CÓPIA (Com formatação preservada e botão visível) ---
if st.session_state.get("show_manual_copy"):
    if caixa2_has_content:
        st.markdown("### 📋 Bloco de Cópia - Formato Final (Caixa 2)")
        st.info("💡 **Dica:** O texto abaixo está no formato **Texto Simples** exigido pelo PEC. Use o botão **'Copy' (dois quadrados)** para garantir que a formatação de linha única (com delimitadores ` // `) seja copiada corretamente para o seu sistema.")
        
        # O USO DE language="markdown" AQUI É SÓ PARA O STREAMLIT VISUALIZAR MELHOR
        st.code(st.session_state["caixa2"], language="markdown") 
        
    else:
        st.warning("A Caixa 2 está vazia. Não há conteúdo para copiar.")
        st.session_state["show_manual_copy"] = False # Limpa a flag


# --- CHAT LIVRE (CAIXA 4) E BOTÃO DE ENVIO ---
st.markdown("---")
st.subheader("4. Chat Livre com Gemini")

# Usando colunas para a Caixa 4 e o botão de envio
colE, colF = st.columns([4, 1])

with colE:
    st.text_input("Pergunta para o Gemini", key="caixa4", label_visibility="collapsed",
                  placeholder="Digite sua pergunta livre para o Gemini...",
                  help="Digite sua pergunta livre para o Gemini (ex: 'Qual a dose máxima de metformina?')")

with colF:
    # Alinhamento vertical do botão
    st.markdown("<style>div.stButton > button {width: 100%; height: 38px; margin-top: 24px;}</style>", unsafe_allow_html=True)
    st.button("💭 Enviar Chat", on_click=send_chat, disabled=not caixa4_has_content)

# --- EXIBIÇÃO DO RESULTADO DO CHAT (Etapa 4) ---
if st.session_state.get("chat_response"):
    st.markdown("---")
    st.markdown(f"**Gemini Responde:** {st.session_state['chat_response']}")
    st.markdown("---")
