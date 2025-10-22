import streamlit as st
import json
import requests
import re
# Importação da biblioteca Gemini
from google import genai
from google.genai import types
from datetime import datetime, timedelta

# Importação da biblioteca Anthropic (Claude)
from anthropic import Anthropic 
# Se for usar Pydantic para Claude, descomente:
# from pydantic import BaseModel, Field
# from typing import List 


# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL E CHAVES DE API (Gemini e Claude)
# ==============================================================================
st.set_page_config(page_title="Assistente de Recursos Acadêmicos (Gemini + DRF)", layout="wide")

# Carrega a chave da Gemini
try:
    # A chave deve ser carregada via st.secrets (assumido que você a configurou)
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
    client_gemini = genai.Client(api_key=GEMINI_API_KEY)
    MODELO_GEMINI = "gemini-2.5-flash"
    # st.info("✅ Gemini API configurada com sucesso.") # Removido para limpar o output
except Exception:
    st.error("Erro: A chave GEMINI_API_KEY não foi encontrada. Adicione sua chave Gemini no arquivo .streamlit/secrets.toml")
    st.stop()
    
# Carrega a chave do Anthropic (Claude) - APENAS CONFIGURAÇÃO
try:
    ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"] 
    client_claude = Anthropic(api_key=ANTHROPIC_API_KEY)
    MODELO_CLAUDE = "claude-3-5-sonnet-20240620"
    # st.info("✅ Anthropic API (Claude) configurada. (Não usada na extração JSON principal)") # Removido para limpar o output
except KeyError:
    # st.warning("⚠️ Chave ANTHROPIC_API_KEY não encontrada. O Claude não pode ser usado no momento.") # Removido para limpar o output
    pass
except Exception as e:
    st.error(f"Erro ao inicializar o cliente Anthropic: {e}")


# URL base da sua API Django (Deve ter os endpoints /materias/, /professores/, /reservas/)
API_BASE_URL = "http://127.0.0.1:8000/api/"


# ==============================================================================
# 2. SISTEMA DE EXTRAÇÃO DE INTENÇÃO (Função Core - Mantida com Gemini)
# ==============================================================================

SYSTEM_PROMPT = """
Você é um sistema de extração de intenção para um assistente acadêmico.
Sua **ÚNICA** função é retornar **EXATAMENTE** um objeto JSON válido, aderindo estritamente ao esquema de resposta.
Você deve responder **APENAS** com o JSON, sem markdown (como ```json) ou qualquer texto adicional.

Intenções Permitidas:
'listar_materias', 'cadastrar_materia', 'atualizar_materia', 'excluir_materia',
'listar_professores', 'cadastrar_professor', 'excluir_professor', 
'reservar_laboratorio', 'listar_reservas', 'excluir_reserva',
'outra'

Regras de Extração de Parâmetros:
- Para 'reservar_laboratorio', extraia: {"materia_nome": "...", "data": "DD/MM ou DD/MM/AAAA", "hora_inicio": "HH:MM", "hora_fim": "HH:MM"}
- Para operações de matéria, use: 'id', 'nome', 'professor', 'carga_horaria'.
- Para professor, use: 'nome', 'email', 'departamento'.
- Para 'excluir_reserva', o 'id' é obrigatório.
"""

def extrair_intencao(mensagem_usuario: str) -> dict:
    """
    Usa o Gemini para extrair a intenção, com lógica aprimorada de fallback (REGEX).
    """
    
    # CORREÇÃO CRÍTICA: Substitui o espaço inseparável (\xa0 ou \u00a0) por um espaço normal
    clean_prompt = mensagem_usuario.lower().replace('\xa0', ' ').strip()
    
    
    # 1. VERIFICAÇÃO DE COMANDOS SIMPLES (Garantia de intenção)
    simple_intents = {
        "listar": "listar_materias", "lista": "listar_materias", "ver": "listar_materias",
        "crie a matéria": "cadastrar_materia", 
        "cadastrar materia": "cadastrar_materia", "excluir materia": "excluir_materia", 
        "atualizar materia": "atualizar_materia",
        
        "cadastrar professor": "cadastrar_professor",
        "cadastre o professor": "cadastrar_professor",
        "criar professor": "cadastrar_professor",
        "excluir professor": "excluir_professor", # Adicionada intenção para consistência
        
        "listar professores": "listar_professores","falar professores": "listar_professores",
        "reservar": "reservar_laboratorio", "listar reservas": "listar_reservas", "reservas": "listar_reservas",
        "apagar reserva": "excluir_reserva", 
        "deletar reserva": "excluir_reserva", 
        "excluir reserva": "excluir_reserva" 
    }
    # Verificação de comandos simples no início da frase
    for key, intent in simple_intents.items():
        if clean_prompt.startswith(key.lower()):
            # Se for uma ação que requer ID (ex: 'excluir reserva') a IA cuidará dos parâmetros
            if 'id' not in clean_prompt and 'professor' not in clean_prompt and 'materia' not in clean_prompt:
                    return {"intencao": intent, "parametros": {}}
    
    # 2. CHAMADA À IA (Tentativa Primária - usando Gemini)
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "intencao": types.Schema(type=types.Type.STRING),
            "parametros": types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "id": types.Schema(type=types.Type.NUMBER),
                    "nome": types.Schema(type=types.Type.STRING),
                    "professor": types.Schema(type=types.Type.STRING),
                    "carga_horaria": types.Schema(type=types.Type.NUMBER),
                    "email": types.Schema(type=types.Type.STRING),
                    "departamento": types.Schema(type=types.Type.STRING),
                    "materia_nome": types.Schema(type=types.Type.STRING), # Nome da matéria para reservas
                    "data": types.Schema(type=types.Type.STRING),
                    "hora_inicio": types.Schema(type=types.Type.STRING),
                    "hora_fim": types.Schema(type=types.Type.STRING),
                },
            ),
        },
        required=["intencao", "parametros"]
    )
    
    final_prompt = f"{SYSTEM_PROMPT}\n\nMENSAGEM DO USUÁRIO: \"{mensagem_usuario}\""
    intent_data = {"intencao": "outra", "parametros": {}}

    try:
        response = client_gemini.models.generate_content(
            model=MODELO_GEMINI,
            contents=[final_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
                timeout=15.0 
            )
        )
        
        raw_json_output = response.text.strip()
        
        json_text = raw_json_output
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        
        intent_data = json.loads(json_text.strip())
        
        # 3. CORREÇÃO DE TIPOS
        for key in ["carga_horaria", "id"]:
              if intent_data.get("parametros", {}).get(key) is not None:
                try: intent_data["parametros"][key] = int(intent_data["parametros"][key])
                except: intent_data["parametros"].pop(key) 

    except Exception as e:
        # print(f"Erro na extração de IA ou timeout: {type(e).__name__} - {e}")
        intent_data["intencao"] = "outra"
        
    # 4. LÓGICA DE FALLBACK AGRESSIVA (REGEX) - Matéria CRUD
    
    if intent_data.get("intencao") == "outra" or "materia" in clean_prompt or "disciplina" in clean_prompt:
        
        if "cadastrar" in clean_prompt or "crie" in clean_prompt:
              intent_data["intencao"] = "cadastrar_materia"
        
        
        if intent_data.get("intencao") in ["atualizar_materia", "cadastrar_materia"]:
              
              # NOME DA MATÉRIA 
              nome_match = re.search(r'(?:matéria|disciplina)\s*([\'"]?)\s*(.+?)\s*([\'"]?)\s*(?:e\s*vincule|com\s*o\s*professor|ou|$)', clean_prompt)

              if nome_match:
                  nome = nome_match.group(2).strip().replace("'", "").replace('"', '')
                  if nome and not re.match(r'id\s*\d+', nome, re.IGNORECASE) and not nome.isdigit():
                      intent_data["parametros"]["nome"] = nome.strip()
              
              # PROFESSOR 
              prof_match = re.search(r'professor\s*([\'"].+?[\'"]|[\w\s]+?)\s*(?:e\s*|\s*carga|ou|$)', clean_prompt)
              if prof_match:
                  prof = prof_match.group(1).strip().replace("'", "").replace('"', '')
                  if prof and len(prof.split()) >= 1 and len(prof) > 2: 
                      intent_data["parametros"]["professor"] = prof.strip()

              # CARGA HORÁRIA 
              ch_match = re.search(r'(\d+)\s*(?:hora|h)', clean_prompt)
              if ch_match:
                  intent_data["parametros"]["carga_horaria"] = int(ch_match.group(1))

        
        # ID (SÓ DEPOIS DOS DEMAIS PARÂMETROS)
        id_match = re.search(r'(?:id\s*|#\s*)(\d+)|(?:\s|^)(\d+)(?:\s|$)', clean_prompt)
        if id_match:
            # Pega o ID da primeira ou segunda captura do regex
            id_val = int(id_match.group(1) or id_match.group(2)) 
            if id_val:
                intent_data["parametros"]["id"] = id_val
                
                if "atualizar" in clean_prompt and "materia" in clean_prompt:
                    intent_data["intencao"] = "atualizar_materia"
                elif "excluir" in clean_prompt and "materia" in clean_prompt:
                    intent_data["intencao"] = "excluir_materia"
                elif "excluir" in clean_prompt and "professor" in clean_prompt:
                    intent_data["intencao"] = "excluir_professor"
                elif ("apagar" in clean_prompt or "deletar" in clean_prompt or "excluir" in clean_prompt) and "reserva" in clean_prompt:
                    intent_data["intencao"] = "excluir_reserva"

    # 5. FALLBACK ESPECÍFICO PARA CADASTRO DE PROFESSOR
    if "professor" in clean_prompt and "cadastr" in clean_prompt:
        
        intent_data["intencao"] = "cadastrar_professor"
        
        # Nome
        nome_match = re.search(r'(?:professor\s*)([^,]+?)(?:,|$|\scom)', clean_prompt)
        if nome_match:
            intent_data["parametros"]["nome"] = nome_match.group(1).strip()
            
        # Email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', clean_prompt)
        if email_match:
            intent_data["parametros"]["email"] = email_match.group(1).strip()
            
        # Departamento
        depto_match = re.search(r'(?:departamento\s*de|depto\s*de)\s*([^,.\s]+)', clean_prompt)
        if depto_match:
            intent_data["parametros"]["departamento"] = depto_match.group(1).strip()
            
            
    # 6. FALLBACK ESPECÍFICO PARA RESERVAS (ULTRA-SIMPLIFICAÇÃO)
    if intent_data.get("intencao") == "reservar_laboratorio" or "reservar" in clean_prompt:
        
        intent_data["intencao"] = "reservar_laboratorio"
        
        # 6a. Extrair NOME DA MATÉRIA (Simplificação extrema)
        # Tenta pegar a palavra após 'matéria' e ANTES de um delimitador de tempo/data
        nome_materia_match = re.search(r"matéria\s*['\"]?\s*([^,]+?)(?=\s+no\s+dia|\s+em|\s+das|\s*$)", clean_prompt)
        
        if nome_materia_match:
            nome = nome_materia_match.group(1).strip().strip('\'"').strip()
            # Se o nome capturado for apenas uma data, hora, ou palavra-chave (ex: 'dia'), ignora.
            if nome and not re.match(r'(\d+/\d+)|(\d+:\d+)|dia|das|em', nome, re.IGNORECASE):
                intent_data["parametros"]["materia_nome"] = nome
                
        # 6b. Extrair DATA (Captura DD/MM ou DD/MM/AAAA)
        data_match = re.search(r'(?:dia|em)\s*(\d{1,2}/\d{1,2}(?:/\d{4})?)', clean_prompt)
        if data_match:
            intent_data["parametros"]["data"] = data_match.group(1).strip()
            
        # 6c. Extrair HORA INÍCIO e FIM (Captura HH:MM)
        horas_match = re.search(r'das\s*(\d{1,2}:\d{2})\s*às\s*(\d{1,2}:\d{2})', clean_prompt)
        if horas_match:
            intent_data["parametros"]["hora_inicio"] = horas_match.group(1).strip()
            intent_data["parametros"]["hora_fim"] = horas_match.group(2).strip()

    return intent_data


# ==============================================================================
# 3. FUNÇÕES AUXILIARES E DE ORQUESTRAÇÃO
# ==============================================================================

def buscar_professor_id(nome_professor: str) -> (int | None):
    """
    Busca o ID de um professor pelo nome. 
    CORRIGIDO: Usa 'params' para garantir o URL Encoding do nome, mas o ponto de falha 
    AGORA é na sua API Django, que precisa de um filtro exato no ViewSet.
    """
    try:
        url = f"{API_BASE_URL}professores/" 
        
        # O requests se encarrega de formatar a URL (ex: "João Silva" -> "Jo%C3%A3o%20Silva")
        # Se a sua API Django estiver configurada para filtrar por 'nome' (via django-filter com 'exact'), isso funciona.
        response = requests.get(url, params={'nome': nome_professor}) 
        
        if response.status_code == 200 and response.json():
            # CORREÇÃO: Verifica se a lista retornada tem o professor exato (melhor prática)
            # No entanto, se o filtro na API estiver errado, isso continuará pegando o 1º de TODOS.
            # Assumimos que o primeiro resultado é o correto APÓS a correção no Django ViewSet.
            return response.json()[0]['id']
        return None
    except requests.exceptions.RequestException:
        return None

def buscar_materia_id(nome_materia: str) -> (int | None):
    """
    Busca o ID de uma matéria pelo nome.
    CORRIGIDO: Usa 'params' para garantir o URL Encoding do nome.
    """
    try:
        # Busca flexível
        url = f"{API_BASE_URL}materias/"
        # O requests se encarrega de formatar a URL
        response = requests.get(url, params={'nome': nome_materia})
        if response.status_code == 200 and response.json():
            # Retorna o ID da primeira matéria encontrada
            return response.json()[0]['id']
        return None
    except requests.exceptions.RequestException:
        return None


# ==============================================================================
# 4. FUNÇÕES DE CRUD NA API DJANGO (usando requests)
# ==============================================================================

def listar_reservas() -> (str, int):
    """Realiza um GET na API e retorna a lista de reservas formatada."""
    try:
        response = requests.get(f"{API_BASE_URL}reservas/")
        response.raise_for_status()
        reservas = response.json()
        
        if not reservas:
            return "Não há reservas de laboratório cadastradas no momento.", 200

        lista = "\n"
        for r in reservas:
            # Assumindo que a API retorna o ID da matéria e não o nome
            materia_id = r.get('materia') 
            data = r.get('data')
            h_in = r.get('hora_inicio')[:5] # Pega HH:MM
            h_fim = r.get('hora_fim')[:5] # Pega HH:MM
            
            lista += f"ID: {r['id']} | Matéria ID: {materia_id} | Data: {data} | Horário: {h_in} - {h_fim}\n"
        
        return "📅 Reservas de Laboratório cadastradas:\n" + lista, 200
    except requests.exceptions.ConnectionError:
        return "Erro: A API Django está offline. Inicie o servidor.", 500
    except requests.exceptions.RequestException as e:
        return f"❌ Erro ao listar reservas: {e}", response.status_code if 'response' in locals() else 500


def excluir_reserva(params: dict) -> (str, int):
    """Realiza um DELETE na API para excluir uma reserva pelo ID."""
    reserva_id = params.get('id')

    if not reserva_id:
        return "Erro: Você precisa informar o ID da reserva a ser excluída. Exemplo: 'apagar a reserva ID 5'.", 400
    
    try:
        # Converte para int 
        reserva_id = int(reserva_id) 
        url = f"{API_BASE_URL}reservas/{reserva_id}/"
        response = requests.delete(url)
        
        if response.status_code == 204: # 204 No Content é o sucesso do DELETE
            return f"🗑️ Reserva ID {reserva_id} excluída com sucesso!", 204
        elif response.status_code == 404:
            return f"❌ Erro: Reserva ID {reserva_id} não encontrada.", 404
        else:
            response.raise_for_status() 
            
    except requests.exceptions.ConnectionError:
        return "Erro: A API Django está offline. Inicie o servidor.", 500
    except requests.exceptions.RequestException as e:
        status_code = response.status_code if 'response' in locals() else 500
        # Tenta pegar a mensagem de erro detalhada, caso a API retorne JSON no erro
        try:
              erro_msg = response.json() if 'response' in locals() and response.content else response.text
        except:
            erro_msg = str(e)
        return f"❌ Erro ao excluir reserva (Status {status_code}): {erro_msg}", status_code


def listar_materias() -> (str, int):
    """Realiza um GET na API e retorna a lista formatada."""
    try:
        response = requests.get(f"{API_BASE_URL}materias/")
        response.raise_for_status()
        materias = response.json()
        
        if not materias:
            return "Não há matérias cadastradas no momento.", 200

        lista = "\n"
        for m in materias:
            carga = m.get('carga_horaria')
            carga_str = f"{carga}h" if carga is not None else "N/D"
            prof_id = m.get('professor') 
            prof_info = f"Prof ID: {prof_id}" if prof_id is not None else "Professor: N/A"
            lista += f"ID: {m['id']} | Matéria: {m['nome']} | {prof_info} | Carga: {carga_str}\n"
        
        return "Matérias cadastradas:\n" + lista, 200
    except requests.exceptions.ConnectionError:
        return "Erro: A API Django está offline. Inicie o servidor.", 500
    except requests.exceptions.RequestException as e:
        return f"Erro ao listar matérias: {e}", response.status_code if 'response' in locals() else 500
    

def cadastrar_materia(params: dict) -> (str, int):
    """Realiza um POST para criar uma nova matéria, orquestrando o Professor."""
    nome_materia = params.get('nome')
    nome_professor = params.get('professor')
    carga_horaria_valor = params.get('carga_horaria')
    
    if not nome_materia:
        return "Erro: O nome da matéria é obrigatório para o cadastro.", 400
    
    professor_id = None
    if nome_professor:
        # Tenta buscar o professor existente usando a função CORRIGIDA
        professor_id = buscar_professor_id(nome_professor)
        
        if professor_id is None:
            return f"❌ Professor '{nome_professor}' não encontrado no sistema. Por favor, cadastre o professor primeiro (Ex: Cadastre o professor {nome_professor}, email: x, depto: y).", 404

    payload = {
        'nome': nome_materia,
        'carga_horaria': int(carga_horaria_valor) if carga_horaria_valor else None,
        'professor': professor_id  # Usa o ID
    }
    # Remove valores None
    payload = {k: v for k, v in payload.items() if v is not None}
    
    try:
        response = requests.post(f"{API_BASE_URL}materias/", json=payload)
        response.raise_for_status()
        return f"✅ Matéria '{nome_materia}' cadastrada e vinculada com sucesso! (ID: {response.json().get('id')})", 201
    except requests.exceptions.RequestException as e:
        status_code = response.status_code if 'response' in locals() else 500
        try:
            erro_msg = response.json() if 'response' in locals() else str(e)
        except:
             erro_msg = response.text
        return f"❌ Erro ao cadastrar matéria (Status {status_code}): {erro_msg}", status_code
    
def atualizar_materia(params: dict) -> (str, int):
    """(STUB) Lógica para atualizar uma matéria pelo ID."""
    materia_id = params.get('id')
    if not materia_id:
          return "Erro: ID da matéria é obrigatório para atualização.", 400
    
    return f"⚠️ **Atualizar Matéria (ID {materia_id})** - Intenção detectada, mas a função de atualização (PUT/PATCH) ainda não foi implementada. Parâmetros: {params}", 400
    
def excluir_materia(params: dict) -> (str, int):
    """(STUB) Lógica para excluir uma matéria pelo ID."""
    materia_id = params.get('id')
    if not materia_id:
          return "Erro: ID da matéria é obrigatório para exclusão.", 400
          
    return f"⚠️ **Excluir Matéria (ID {materia_id})** - Intenção detectada, mas a função de exclusão (DELETE) ainda não foi implementada.", 400


def listar_professores() -> (str, int):
    """Realiza um GET na API e retorna a lista de professores formatada."""
    try:
        response = requests.get(f"{API_BASE_URL}professores/")
        response.raise_for_status()
        professores = response.json()
        
        if not professores:
            return "Não há professores cadastrados no momento.", 200

        lista = "\n"
        for p in professores:
            lista += f"ID: {p['id']} | Professor: {p['nome']} | E-mail: {p['email']} | Depto: {p['departamento']}\n"
        
        return "Professores cadastrados:\n" + lista, 200
    except requests.exceptions.ConnectionError:
        return "Erro: A API Django está offline. Inicie o servidor.", 500
    except requests.exceptions.RequestException as e:
        return f"Erro ao listar professores: {e}", response.status_code if 'response' in locals() else 500

def cadastrar_professor(params: dict) -> (str, int):
    """Realiza um POST na API para criar um novo professor."""
    nome = params.get('nome')
    email = params.get('email')
    departamento = params.get('departamento')

    if not nome or not email or not departamento:
        return "Erro: Faltam dados essenciais (nome, email e departamento) para cadastrar o professor. Tente reformular a frase.", 400
    
    payload = {'nome': nome, 'email': email, 'departamento': departamento}
    
    try:
        response = requests.post(f"{API_BASE_URL}professores/", json=payload)
        response.raise_for_status()
        return f"🧑‍🏫 Professor '{nome}' do departamento '{departamento}' cadastrado com sucesso! (ID: {response.json().get('id')})", 201
    except requests.exceptions.RequestException as e:
        status_code = response.status_code if 'response' in locals() else 500
        try:
            erro_msg = response.json() if 'response' in locals() else str(e)
        except:
             erro_msg = response.text
        return f"❌ Erro ao cadastrar professor (Status {status_code}): {erro_msg}", status_code

def excluir_professor(params: dict) -> (str, int):
    """(STUB) Lógica para excluir um professor pelo ID."""
    professor_id = params.get('id')
    if not professor_id:
          return "Erro: ID do professor é obrigatório para exclusão.", 400
          
    return f"⚠️ **Excluir Professor (ID {professor_id})** - Intenção detectada, mas a função de exclusão (DELETE) ainda não foi implementada.", 400

def reservar_laboratorio(params: dict) -> (str, int):
    """Realiza um POST na API para criar uma nova reserva."""
    nome_materia = params.get('materia_nome')
    data_str = params.get('data')
    hora_inicio_str = params.get('hora_inicio', '10:00') # Default
    hora_fim_str = params.get('hora_fim', '12:00') # Default

    if not nome_materia or not data_str:
        return "Erro: Faltam dados (nome da matéria e data) para a reserva.", 400
    
    # 1. ORQUESTRAÇÃO: Buscar ID da Matéria 
    materia_id = buscar_materia_id(nome_materia)
    if materia_id is None:
        return f"Matéria '{nome_materia}' não encontrada. Verifique o nome e tente novamente.", 404
        
    # 2. Processamento da Data e Hora
    try:
        # A data pode vir como DD/MM ou DD/MM/AAAA
        formatos_data = ["%d/%m/%Y", "%d/%m"]
        data_reserva = None
        
        for fmt in formatos_data:
            try:
                dt_obj = datetime.strptime(data_str, fmt)
                # Se o formato for DD/MM, assume o ano atual
                if fmt == "%d/%m":
                    dt_obj = dt_obj.replace(year=datetime.now().year)
                data_reserva = dt_obj.date()
                break
            except ValueError:
                continue

        if data_reserva is None:
            raise ValueError("Formato de data inválido.")

        hora_inicio = datetime.strptime(hora_inicio_str, "%H:%M").time()
        hora_fim = datetime.strptime(hora_fim_str, "%H:%M").time()
        
        # Simples validação de lógica
        if datetime.combine(data_reserva, hora_inicio) >= datetime.combine(data_reserva, hora_fim):
            return "Erro: A hora de início deve ser anterior à hora de fim.", 400
            
    except ValueError as e:
        return f"Erro na formatação de data/hora. Use DD/MM ou DD/MM/AAAA e HH:MM. Erro: {e}", 400

    payload = {
        'materia': materia_id,
        'data': data_reserva.isoformat(),
        'hora_inicio': hora_inicio.isoformat(),
        'hora_fim': hora_fim.isoformat(),
        'confirmada': True 
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}reservas/", json=payload)
        response.raise_for_status()
        return f"📅 Reserva do laboratório para '{nome_materia}' em {data_str} das {hora_inicio_str} às {hora_fim_str} **CRIADA com sucesso!** (ID: {response.json().get('id')})", 201
    except requests.exceptions.RequestException as e:
        status_code = response.status_code if 'response' in locals() else 500
        try:
            # Tenta obter a mensagem de erro detalhada da API
            erro_msg = response.json() if 'response' in locals() and response.content else response.text
        except:
             erro_msg = str(e)
        return f"❌ Erro ao criar reserva (Status {status_code}): {erro_msg}", status_code


# ==============================================================================
# 5. CHATBOT E LÓGICA DE EXECUÇÃO
# ==============================================================================

def main():
    # Título para garantir que o código foi atualizado
    st.title("🤖 Assistente - (DRF+Anthropic+Gemini)") 
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "Olá! Sou seu assistente para gerenciar Matérias, Professores e Reservas. O que você gostaria de fazer? (Ex: **listar professores, cadastrar matéria, reservar laboratório, excluir reserva ID 5**)"})

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Fale com o assistente..."):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analisando intenção e executando operação..."):
                
                # 1. Extrai a intenção
                intent_data = extrair_intencao(prompt)
                intenção = intent_data.get("intencao", "outra")
                params = intent_data.get("parametros", {})
                
                # 2. Exibe a Intenção Detectada (DEBUG)
                st.write(f"Intenção detectada: **{intenção}**")
                st.write(f"Parâmetros: **{params}**")
                
                # 3. Executa a Ação com base na Intenção
                
                response_text = "Intenção não reconhecida ou fora do escopo do assistente."
                status_code = 400
                
                if intenção == "listar_materias":
                    response_text, status_code = listar_materias()
                elif intenção == "cadastrar_materia":
                    response_text, status_code = cadastrar_materia(params)
                elif intenção == "atualizar_materia": # Incluído
                    response_text, status_code = atualizar_materia(params)
                elif intenção == "excluir_materia": # Incluído
                    response_text, status_code = excluir_materia(params)
                elif intenção == "listar_professores":
                    response_text, status_code = listar_professores()
                elif intenção == "cadastrar_professor":
                    response_text, status_code = cadastrar_professor(params)
                elif intenção == "excluir_professor": # Incluído
                    response_text, status_code = excluir_professor(params)
                elif intenção == "reservar_laboratorio":
                    response_text, status_code = reservar_laboratorio(params)
                elif intenção == "listar_reservas": 
                    response_text, status_code = listar_reservas()
                elif intenção == "excluir_reserva": 
                    response_text, status_code = excluir_reserva(params)
                # ... Outras intenções
                
                # 4. Formatação da Resposta
                if status_code >= 200 and status_code < 400:
                    st.success(response_text)
                elif status_code == 204: # Sucesso para DELETE (No Content)
                    st.success(response_text)
                else:
                    st.error(response_text)
                    
                st.session_state.messages.append({"role": "assistant", "content": response_text})

if __name__ == "__main__":
    main()