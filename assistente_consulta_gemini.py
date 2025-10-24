import streamlit as st
from google import genai
from google.genai.errors import APIError

# --- CONSTANTE DE CHAVE DE SESSÃO PARA AS REGRAS ---
SESSION_KEY_PEC1 = "SYSTEM_ROLE_PEC1_EDITED"

# --- PROMPTS COMO CONSTANTES (COM REGRAS DE FORMATO FINAL DO PEC) ---
# Mantenho a constante original, mas o app usará a versão em st.session_state
SYSTEM_ROLE_PEC1_DEFAULT = r"""
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

# --- FUNÇÕES DE CALLBACK ---

def clear_fields():
    """Callback para a função LIMPAR: Reseta todos os campos de estado da sessão."""
    for key in ["caixa1","caixa2","caixa3","caixa4", "chat_response", "show_manual_copy"]:
        # Reset para valor vazio ou False
        st.session_state[key] = "" if key != "show_manual_copy" else False
    # Manter a regra personalizada se existir, senão resetar para o padrão
    if SESSION_KEY_PEC1 in st.session_state:
        st.session_state[SESSION_KEY_PEC1] = SYSTEM_ROLE_PEC1_DEFAULT

def save_pec1_role():
    """Callback para salvar o texto editado do prompt PEC1 na sessão."""
    # O valor do text_area é acessado via key 'pec1_editor'
    st.session_state[SESSION_KEY_PEC1] = st.session_state.pec1_editor
    st.success("Regras PEC1 salvas com sucesso para esta sessão!", icon="💾")

def get_current_pec1_role():
    """Retorna o prompt PEC1 atual (editado ou padrão)."""
    if SESSION_KEY_PEC1 not in st.session_state:
        st.session_state[SESSION_KEY_PEC1] = SYSTEM_ROLE_PEC1_DEFAULT
    return st.session_state[SESSION_KEY_PEC1]

# --- CONFIGURAÇÃO INICIAL ---

# Define o layout wide para usar mais espaço horizontal
st.set_page_config(page_title="ASSISTENTE DE CONSULTA GEMINI", layout="wide")


# --- AJUSTE CSS PARA VISUAL (COR DE FUNDO, TÍTULO, BOTÕES, CAIXAS) ---
st.markdown(f"""
    <style>
    /* 1. COR DE FUNDO DA PÁGINA (AZUL MAIS ESCURO) */
    .stApp {{
        background-color: #D6EAF8; /* Um azul um pouco mais escuro que o anterior */
    }}

    /* 2. VISIBILIDADE DO TÍTULO: Aumenta o padding superior e zera a margem do h1 */
    .block-container {{
        padding-top: 1rem; /* Aumenta para 1rem para garantir visibilidade do título */
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }}

    /* 3. ESPAÇO DO TÍTULO */
    h1 {{
        margin-top: 0rem !important; /* Zera a margem superior do h1 (o padding do container resolve) */
        margin-bottom: 0.5rem !important; /* Reduz espaço inferior */
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }}

    /* 4. ESTILO GERAL DE BOTÕES (FUNDO ROSA, TEXTO PRETO NEGRITO) */
    div.stButton > button {{
        width: 100%;
        height: 48px;
        background-color: #FFC0CB; /* Rosa */
        color: black !important;
        font-weight: bold;
        border: 1px solid #FF69B4; /* Borda rosa escura */
        transition: background-color 0.2s;
    }}
    div.stButton > button:hover {{
        background-color: #FF69B4; /* Rosa mais escuro no hover */
        color: white !important;
    }}

    /* 5. ESTILO DAS CAIXAS DE TEXTO (TEXTO PRETO NEGRITO) */
    .stTextArea, .stTextInput {{
        color: black;
        font-weight: bold;
    }}

    /* Ajustes gerais de margem */
    .stTextInput {{
        margin-top:
