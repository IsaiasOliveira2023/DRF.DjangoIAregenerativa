🤖 Assistente Conversacional de Gerenciamento Acadêmico (DRF + Gemini + Anthropic)
🎯 Objetivo do ProjetoEste projeto integra um frontend conversacional construído com Streamlit e as APIs de ponta Google Gemini e Anthropic (Claude) para extração de intenção e parâmetros, com um backend robusto de gerenciamento de dados acadêmicos construído com Django Rest Framework (DRF).O assistente permite que o usuário gerencie cadastros (CRUD) de matérias, professores e reservas de laboratório usando comandos de linguagem natural, eliminando a necessidade de interagir diretamente com o banco de dados ou endpoints da API.✨ Tecnologias UtilizadasComponenteTecnologiaFunçãoBackend (API)Python / Django Rest Framework (DRF)Gerencia os dados (Matérias, Professores, Reservas) e expõe os endpoints REST.Frontend (Interface)Python / StreamlitCria a interface de chat interativa.Inteligência Artificial (Extração principal)Google GeminiExtrai a intenção (o que fazer) e os parâmetros (os dados) da mensagem do usuário (uso principal no extrair_intencao).Inteligência Artificial (Configuração)Anthropic (Claude)Biblioteca configurada para uso futuro/alternativo em tarefas de LLM (embora não seja o extrator principal no código atual).ComunicaçãorequestsPermite que o Streamlit se comunique com a API Django.

https://drive.google.com/file/d/17gJPOsRf_89hbDKD5u8MpZ8GWmKTnS-l/view?usp=sharing

modo de usar 
gere as keys e coloque no lugar delas em secrets.toml

depois siga seus passos para localizar o arquivo mostrei meu exemplo de caminho as segundas linhas pode seguir iguais

terminal 1
# NAVEGA PARA A PASTA PRINCIPAL
cd C:\Users\isaia\Downloads\aaa drf\MeuProjetoDRF

# 1. ATIVA O AMBIENTE ESTÁVEL (Python 3.12)
.\venv_312\Scripts\Activate.ps1

# 2. ENTRA NA PASTA DO PROJETO
cd escola_api

# 3. EXECUTA O SERVIDOR DJANGO (Se tudo estiver instalado)
python manage.py runserver

terminal 2 front end IA

# NAVEGA PARA A PASTA PRINCIPAL
cd C:\Users\isaia\Downloads\aaa drf\MeuProjetoDRF

# 1. ATIVA O AMBIENTE ESTÁVEL (Python 3.12)
.\venv_312\Scripts\Activate.ps1

# 2. ENTRA NA PASTA DO PROJETO
cd escola_api

# 3. EXECUTA O STREAMLIT (com o código de DEBUG)
streamlit run Prog3_assistente.py

comandos testados abaixo


Listar matérias

Cadastrar o professor 'Leandro.' com o e-mail 'Leandro@escola.br' do departamento de 'Infraestrutura'.
Cadastrar o professor 'Rafael.' com o e-mail 'Rafael@escola.br' do departamento de 'Ciencia da Inf.'.
Cadastrar o professor 'mario.' com o e-mail 'mario@escola.br' do departamento de 'TI.'.



vincule ao professor 'Leandro' e Crie matéria 'redes ' . de 80 horas de carga
vincule ao professor 'Rafael' e Crie matéria 'Programação ' . de 180 horas de carga
vincule ao professor 'mario' e Crie matéria 'informatica ' . de 90 horas de carga




Quero reservar o laboratório para a matéria 'redes' no dia 28/11 das 13:00 às 17:30.
Quero reservar o laboratório para a matéria 'Programação' no dia 29/11 das 14:00 às 18:30.
Quero reservar o laboratório para a matéria 'informatica' no dia 30/11 das 15:00 às 19:30.



Reservas agendadas

apagar a reserva ID 5




