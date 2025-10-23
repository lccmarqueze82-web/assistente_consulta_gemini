import streamlit as st
from google import genai
from google.genai.errors import APIError

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
# 2. Assistente de Consulta Gemini EM CAIXA ALTA
st.set_page_config(page_title="ASSISTENTE DE CONSULTA GEMINI", layout="wide")

# 1. RETIRAR EMOJIS
st.title("ASSISTENTE DE CONSULTA GEMINI")

GEMINI_MODEL = "gemini-2.5-flash"

# --- PROMPTS COMO CONSTANTES (INALTERADOS APÓS ÚLTIMA CORREÇÃO DE FORMATO) ---

SYSTEM_ROLE_PEC1 = r"""
VOCÊ É O ASSISTENTE DE DOCUMENTAÇÃO CLÍNICA PEC1. SUA ÚNICA FUNÇÃO É GERAR O REGISTRO CLÍNICO FINAL. **SIGA AS REGRAS DE FORMATAÇÃO E LÓGICA ESTRITAMENTE**.

**PROIBIDO:** INTRODUÇÕES, COMENTÁRIOS, NUMERAÇÕES DE ITENS, PERGUNTAS, OU QUALQUER TEXTO FORA DA ESTRUTURA OBRIGATÓRIA.

### **1. FORMATO DE SAÍDA OBRIGATÓRIO (TEXTO SIMPLES)**

GERE O REGISTRO **INTEIRAMENTE EM CAIXA ALTA** E NESTA ORDEM. **OMITA** A SEÇÃO `AVALIAÇÃO MULTIDIMENSIONAL` SE NÃO FOR APLICÁVEL.

HMA: HPP: MUC: EX FISICO: AVALIAÇÃO MULTIDIMENSIONAL: EXAMES: HD: CONDUTA:

VERIFICAÇÃO BEERS / STOPP-START:

GARANTIA DE ESTÉTICA: O REGISTRO DEVE SER GERADO INTEGRALMENTE COMO **TEXTO SIMPLES**. **REMOVER TODOS OS CARACTERES MARKDOWN (***, **, #, ETC)**.
**AS REGRAS DE QUEBRA DE LINHA SÃO:**
1. **RÓTULOS DE SEÇÃO** (HMA:, HPP:, MUC:, EX FISICO:, EXAMES:, HD:, CONDUTA:, VERIFICAÇÃO BEERS / STOPP-START:) DEVEM FICAR EM UMA **LINHA PRÓPRIA**.
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
| **EXAMES** | LINHA ÚNICA. EXAMES ALTERADOS EM **CAIXA ALTA ENTRE PARENTESES SIMPLES**. DATA (MM/AA). MANTER ALTERADOS DE QUALQUER ÉPOCA E NORMAIS <1 ANO. CALCULAR CKD-EPI (2021) E CLASSIFICAR DRC SE CREATININA+IDADE+SEXO DISPONÍVEIS. SE NÃO HOUVER: `SEM EXAMES DISPONÍVEIS.` |
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

# 3. RETIRAR O TEXTO EXPLICATIVO
st.markdown("---") # Separador visual

# Expander para as regras
with st.expander("Ver Regras Completas do Prompt PEC1"):
    st.code(SYSTEM_ROLE_PEC1, language="markdown")


# --- LAYOUT DAS CAIXAS DE TEXTO ---
col1, col2, col3 = st.columns(3)

with col1:
    # 4. CAIXA 1 - Informação Crua - TROCAR POR SOAP
    st.text_area("SOAP", height=250, key="caixa1",
                 help="Insira aqui o texto de entrada (anotações, dados brutos, etc.)")

with col2:
    # 5. CAIXA 2 - Prompt PEC1 Atualizado - TROCA POR CORRIGIDO
    st.text_area("CORRIGIDO", height=250, key="caixa2",
                 help="Saída formatada do Gemini conforme as regras PEC1.")

with col3:
    st.text_area("Sugestões e Discussão", height=250, key="caixa3",
                 help="Sugestões de diagnósticos, condutas e discussão geradas pelo Gemini.")

st.markdown("---") # Separador visual

# --- LAYOUT DOS BOTÕES DE CONTROLE ---
# 6. ALINHAR BOTOES e 7. DEIXAR BOTOES COM MESMAS DIMENSOES
# Usaremos 4 colunas de tamanho igual (1, 1, 1, 1) para forçar o alinhamento
colA, colB, colC, colD = st.columns(4)

# Estilo CSS para forçar todos os botões a terem a mesma altura e largura,
# e o texto do botão a alinhar no centro (melhor UX).
st.markdown("""
<style>
div.stButton > button {
    width: 100%;
    height: 48px; 
    padding-top: 10px !important;
    padding-bottom: 10px !important;
}
</style>
""", unsafe_allow_html=True)


caixa1_has_content = bool(st.session_state.get("caixa1", "").strip())
caixa2_has_content = bool(st.session_state.get("caixa2", "").strip())
caixa4_has_content = bool(st.session_state.get("caixa4", "").strip())

with colA:
    # Botão LIMPAR
    st.button("LIMPAR TUDO", on_click=clear_fields)

with colB:
    # Botão COPIAR
    label_copy = "OCULTAR CÓPIA" if st.session_state.get("show_manual_copy") else "COPIAR"
    st.button(label_copy, on_click=copy_caixa2_content, disabled=not caixa2_has_content,
              help="Alterna a visualização de um bloco de código com botão de cópia nativo.")

with colC:
    # Botão Etapa 2
    st.button("APLICAR PEC1", on_click=apply_pec1,
              disabled=not caixa1_has_content, help="Aplica o prompt de formatação PEC1 na Caixa 1 e envia para a Caixa 'CORRIGIDO'.")

with colD:
    # Botão Etapa 3
    st.button("GERAR SUGESTÕES", on_click=generate_suggestions,
              disabled=not caixa2_has_content, help="Gera sugestões de diagnóstico e conduta com base no texto da Caixa 'CORRIGIDO'.")


# --- EXIBIÇÃO DO BLOCO DE CÓPIA (Com formatação preservada e botão visível) ---
if st.session_state.get("show_manual_copy"):
    if caixa2_has_content:
        st.markdown("### Bloco de Cópia - Formato Final (CORRIGIDO)")
        st.info("O texto abaixo está no formato Texto Simples exigido pelo PEC. Use o botão 'Copy' (dois quadrados) para garantir que as quebras de linha sejam copiadas corretamente.")
        st.code(st.session_state["caixa2"], language="markdown") 
    else:
        st.warning("A Caixa CORRIGIDO está vazia. Não há conteúdo para copiar.")
        st.session_state["show_manual_copy"] = False


# --- CHAT LIVRE (CAIXA 4) E BOTÃO DE ENVIO ---
st.markdown("---")
# 8. 4. Chat Livre com Gemini - APAGAR (APENAS UM SEPARADOR SIMPLES)

# 9. TRAZER BARRA DE CHAT P IMEDIATAMENTE ABAIXO DAS OUTRAS CAIXAS ENFILEIRADAS.
# O chat já está logo abaixo da seção de botões e cópia.
colE, colF = st.columns([5, 1])

with colE:
    st.text_input("Pergunta para o Gemini", key="caixa4", label_visibility="collapsed",
                  placeholder="Chat Livre: Digite sua pergunta (ex: 'Qual a dose máxima de metformina?')",
                  help="Digite sua pergunta livre para o Gemini.")

with colF:
    # Forçando o botão do chat a ter a mesma altura da caixa de texto, para alinhamento.
    st.markdown("""
    <style>
    div.stButton#chat-button > button {
        height: 38px; 
        margin-top: -8px; /* Ajusta a margem para alinhar com o text_input */
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.button("ENVIAR", on_click=send_chat, disabled=not caixa4_has_content, key="chat-button")

# --- EXIBIÇÃO DO RESULTADO DO CHAT (Etapa 4) ---
if st.session_state.get("chat_response"):
    st.markdown("---")
    st.markdown(f"**Gemini Responde:** {st.session_state['chat_response']}")
    st.markdown("---")
