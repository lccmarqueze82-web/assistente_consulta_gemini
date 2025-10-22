import streamlit as st
from google import genai
from google.genai.errors import APIError

# --- CONFIGURAÇÃO INICIAL E CONSTANTES ---
st.set_page_config(page_title="Assistente de Consulta Gemini", layout="wide")

st.title("🩺 Assistente de Consulta Gemini")

GEMINI_MODEL = "gemini-2.5-flash"

# --- PROMPTS COMO CONSTANTES (LIMPOS E COM ESTRUTURA REFORÇADA) ---

# Prompt para a Etapa 2 (PEC1) - RESTAURADO COM ESTRUTURAÇÃO MARKDOWN PARA O MODELO
SYSTEM_ROLE_PEC1 = """
Você é o assistente de documentação clínica PEC1. Sua única função é gerar o registro clínico final. **Siga as regras de formatação e lógica estritamente**.

**PROIBIDO:** Introduções, comentários, numerações de itens, perguntas, ou qualquer texto fora da estrutura obrigatória.

### **1. FORMATO DE SAÍDA OBRIGATÓRIO**

Gere o registro **INTEIRAMENTE EM CAIXA ALTA** e nesta ordem. **Omita** a seção `AVALIAÇÃO MULTIDIMENSIONAL` se não for aplicável.
