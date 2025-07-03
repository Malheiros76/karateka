import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import io
import urllib.parse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import hashlib
import bcrypt

# ---------- CONFIGURAÇÕES ----------
# MongoDB connection
MONGO_URI = "mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["academia_karate"]

# Coleções
col_usuarios = db["usuarios"]
col_academia = db["academia"]
col_alunos = db["alunos"]
col_presencas = db["presencas"]
col_mensalidades = db["mensalidades"]
col_exames = db["exames"]
col_equipamentos = db["equipamentos"]
col_emprestimos = db["emprestimos"]

belt_progression = {
    'Branca': {'next': 'Cinza', 'months': 3, 'value': 40.00},
    'Cinza': {'next': 'Azul', 'months': 3, 'value': 45.00},
    'Azul': {'next': 'Amarela', 'months': 3, 'value': 55.00},
    'Amarela': {'next': 'Vermelha', 'months': 3, 'value': 60.00},
    'Vermelha': {'next': 'Laranja', 'months': 6, 'value': 65.00},
    'Laranja': {'next': 'Verde', 'months': 9, 'value': 70.00},
    'Verde': {'next': 'Roxa', 'months': 9, 'value': 75.00},
    'Roxa': {'next': 'Marrom2', 'months': 12, 'value': 80.00},
    'Marrom2': {'next': 'Marrom1', 'months': 12, 'value': 90.00}
}


# ---------- ESTILOS ----------
st.markdown("""
    <style>
    body {
        background-color: #1e3a8a;
        color: white;
    }
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div > select,
    .stDateInput > div > div > input {
        background-color: #1e40af;
        color: white;
        border-radius: 5px;
        border: 1px solid #3b82f6;
    }
    div.stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        font-weight: 600;
        border-radius: 8px;
        border: none;
    }
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-thumb {
        background: #3b82f6;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)


# ---------- FUNÇÕES UTILITÁRIAS ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def enviar_mensagem_whatsapp(telefone, mensagem):
    numero = telefone.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
    texto = urllib.parse.quote(mensagem)
    url = f"https://api.whatsapp.com/send?phone=55{numero}&text={texto}"
    st.markdown(f"[Clique aqui para enviar mensagem via WhatsApp]({url})", unsafe_allow_html=True)


def enviar_alerta_mensalidade():
    hoje = datetime.today().date()
    mensalidades = list(col_mensalidades.find({"pago": False}))

    for mensalidade in mensalidades:
        try:
            vencimento = datetime.strptime(mensalidade['vencimento'], "%Y-%m-%d").date()
        except:
            continue

        aluno = col_alunos.find_one({"nome": mensalidade['aluno']})
        if aluno:
            telefone = aluno.get("telefone", "")
            nome = aluno.get("nome", "")
            if telefone:
                mensagem = f"Olá {nome}, sua mensalidade vence em {vencimento.strftime('%d/%m/%Y')}. Por favor, realize o pagamento."
                enviar_mensagem_whatsapp(telefone, mensagem)


# ---------- EXPORTAÇÕES PDF ----------
# Suas funções de exportação PDF continuam idênticas ao código original.
# Para poupar espaço aqui, não estou repetindo todas elas — pode copiar do seu código sem mudanças.
# (Se quiser que eu insira tudo de novo, me avise!)


# ---------- AUTENTICAÇÃO ----------
if "logado" not in st.session_state:
    st.session_state.logado = False


def criar_admin():
    st.title("🥋 空手道 (Karatedō) - Primeiro Acesso")
    st.info("Nenhum usuário encontrado. Crie o usuário administrador.")

    usuario = st.text_input("Usuário Admin")
    senha = st.text_input("Senha", type="password")
    confirmar = st.text_input("Confirme a Senha", type="password")

    if st.button("Criar Admin"):
        if senha != confirmar:
            st.error("As senhas não coincidem.")
            return

        if not usuario or not senha:
            st.error("Preencha todos os campos.")
            return

        hashed = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())
        col_usuarios.insert_one({
            "usuario": usuario,
            "senha": hashed,
            "nivel": "admin"
        })

        st.success("Usuário admin criado com sucesso! Faça login.")
        st.rerun()


def login():
    st.title("🥋 空手道 (Karatedō) - Sistema Karatê")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        user = col_usuarios.find_one({"usuario": usuario})
        if user and bcrypt.checkpw(senha.encode(), user["senha"]):
            st.session_state["logado"] = True
            st.session_state["nivel"] = user["nivel"]
            st.session_state["usuario"] = usuario
        else:
            st.error("Credenciais inválidas")


# ---------- INTERFACE PRINCIPAL ----------

if col_usuarios.count_documents({}) == 0:
    criar_admin()
elif not st.session_state.logado:
    login()
else:
    st.markdown("""
        <style>
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #ffffff;
            padding: 10px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 9999;
        }
        .menu-radio label {
            margin-right: 15px;
            font-weight: 600;
            cursor: pointer;
        }
        .menu-radio input[type="radio"] {
            margin-right: 5px;
        }
        .logout-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([8, 1])
    with col1:
        pagina = st.radio(
            "Menu",
            ["Alunos", "Presenças", "Mensalidades", "Exames", "Empréstimos", "Equipamentos", "Cadastros Gerais", "Sistema"],
            horizontal=True,
            label_visibility="collapsed"
        )

    def logout():
        st.session_state.logado = False
        st.rerun()

    with col2:
        if st.button("🚪 Sair", use_container_width=True):
            logout()
def pagina_alunos():
    st.header("🥋 空手道 (Karatedō) - Alunos Cadastrados")
    alunos = list(col_alunos.find())

    if alunos:
        for a in alunos:
            col1, col2, col3 = st.columns([4,4,4])
            with col1:
                st.markdown(f"**{a['nome']}** | RG: {a.get('rg','')} | Faixa: {a.get('faixa','')} | Tel: {a.get('telefone','')}")
            with col2:
                # Botão para editar
                if st.button(f"✏️ Editar {a['nome']}", key=f"editar_{a['_id']}"):
                    st.session_state["editar_id"] = str(a["_id"])
                    st.experimental_rerun()
            with col3:
                if st.button(f"🗑️ Excluir {a['nome']}", key=f"excluir_{a['_id']}"):
                    col_alunos.delete_one({"_id": a["_id"]})
                    st.success(f"Aluno {a['nome']} excluído!")
                    st.rerun()
    else:
        st.info("Nenhum aluno cadastrado.")

    editar_id = st.session_state.get("editar_id", None)
    if editar_id:
        aluno_edit = col_alunos.find_one({"_id": ObjectId(editar_id)})
        st.subheader(f"Editar Aluno: {aluno_edit['nome']}")
        with st.form("form_editar_aluno"):
            nome = st.text_input("Nome", value=aluno_edit["nome"])
            rg = st.text_input("RG", value=aluno_edit.get("rg", ""))
            faixa = st.selectbox("Faixa", ["Branca", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"], index=["Branca", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"].index(aluno_edit.get("faixa","Branca")))
            data_nascimento = st.date_input("Data de Nascimento", value=datetime.strptime(aluno_edit.get("data_nascimento", "2000-01-01"), "%Y-%m-%d"))
            telefone = st.text_input("Telefone/WhatsApp (com DDD)", value=aluno_edit.get("telefone",""))

            if st.form_submit_button("Salvar Alterações"):
                col_alunos.update_one(
                    {"_id": ObjectId(editar_id)},
                    {"$set": {
                        "nome": nome,
                        "rg": rg,
                        "faixa": faixa,
                        "data_nascimento": str(data_nascimento),
                        "telefone": telefone
                    }}
                )
                st.success("Aluno atualizado com sucesso!")
                del st.session_state["editar_id"]
                st.rerun()

        if st.button("Cancelar edição"):
            del st.session_state["editar_id"]
            st.rerun()

    else:
        # Formulário para cadastrar novo aluno, só aparece se não estiver editando
        st.header("🥋 空手道 (Karatedō) - Cadastrar Novo Aluno")
        with st.form("form_aluno"):
            nome = st.text_input("Nome")
            rg = st.text_input("RG")
            faixa = st.selectbox("Faixa", ["Branca", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"])
            data_nascimento = st.date_input("Data de Nascimento")
            telefone = st.text_input("Telefone/WhatsApp (com DDD)", max_chars=15)
            if st.form_submit_button("Cadastrar"):
                col_alunos.insert_one({
                    "nome": nome,
                    "rg": rg,
                    "telefone": telefone,
                    "faixa": faixa,
                    "data_nascimento": str(data_nascimento)
                })
                st.success("Aluno cadastrado!")
                st.rerun()
# Cria a barra superior
    col1, col2 = st.columns([8, 1])
    with col1:
        pagina = st.radio(
            "Menu",
            ["Alunos", "Presenças", "Mensalidades", "Exames","Empréstimos", "Equipamentos", "Cadastros Gerais","Sistema"],
            horizontal=True,
            label_visibility="collapsed"
        )
        def logout():
            st.session_state.logado = False
            st.rerun()

    with col2:
       if st.button("🚪 Sair", use_container_width=True):
        logout()
            
    # Exibe a página selecionada
    if pagina == "Alunos":
        pagina_alunos()
    elif pagina == "Presenças":
        pagina_presencas()
    elif pagina == "Mensalidades":
        pagina_mensalidades()
    elif pagina == "Exames":
        pagina_exames()
    elif pagina == "Empréstimos":
        pagina_emprestimos()
    elif pagina == "Equipamentos":
        pagina_equipamentos()
    elif pagina == "Cadastros Gerais":
        pagina_geral()
    elif pagina == "Sistema":
        pagina_admin_system()

