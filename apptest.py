import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import io
from dateutil.relativedelta import relativedelta
import urllib.parse
from datetime import datetime, timedelta
import bcrypt

# --- Estilo CSS ---
st.markdown(
    """
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
    """,
    unsafe_allow_html=True
)

# --- Conexão MongoDB ---
MONGO_URI = "mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["academia_karate"]

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

# --- Funções auxiliares ---
def enviar_mensagem_whatsapp(telefone, mensagem):
    numero = telefone.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
    texto = urllib.parse.quote(mensagem)
    url = f"https://api.whatsapp.com/send?phone=55{numero}&text={texto}"
    st.markdown(f"[📱 Enviar WhatsApp]({url})", unsafe_allow_html=True)

def enviar_alerta_mensalidade():
    hoje = datetime.today().date()
    alerta_3_dias = hoje + timedelta(days=3)

    mensalidades = list(col_mensalidades.find({}))
    for mensalidade in mensalidades:
        try:
            vencimento = datetime.strptime(mensalidade['vencimento'], "%Y-%m-%d").date()
        except:
            continue

        if vencimento == alerta_3_dias:
            aluno = col_alunos.find_one({"nome": mensalidade['aluno']})
            if aluno:
                telefone = aluno.get("telefone", "")
                nome = aluno.get("nome")
                if telefone:
                    mensagem = f"Olá {nome}, sua mensalidade vence em 3 dias ({vencimento.strftime('%d/%m/%Y')})."
                    enviar_mensagem_whatsapp(telefone, mensagem)

def calcular_proximo_exame(ultima_faixa, ultima_data):
    if ultima_faixa not in belt_progression:
        return None, None, None, None, None

    next_belt = belt_progression[ultima_faixa]["next"]
    interval = belt_progression[ultima_faixa]["months"]
    valor = belt_progression[ultima_faixa]["value"]

    data_ultimo = datetime.strptime(ultima_data, "%Y-%m-%d")
    data_proximo = data_ultimo + relativedelta(months=interval)

    hoje = datetime.today()
    if data_proximo > hoje:
        diff = relativedelta(data_proximo, hoje)
        meses_faltando = diff.months
        dias_faltando = diff.days
    else:
        meses_faltando = 0
        dias_faltando = 0

    return next_belt, data_proximo, meses_faltando, dias_faltando, valor

# --- Sessão ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

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
        col_usuarios.insert_one({"usuario": usuario, "senha": hashed})
        st.success("Usuário admin criado. Faça login.")
        st.rerun()

def login():
    st.title("🥋 空手道 (Karatedō) - Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        user = col_usuarios.find_one({"usuario": usuario})
        if user and bcrypt.checkpw(senha.encode(), user["senha"]):
            st.session_state["logado"] = True
            st.rerun()
        else:
            st.error("Credenciais inválidas")

def logout():
    st.session_state["logado"] = False
    st.rerun()

# --- PÁGINAS ---
def pagina_geral():
    st.header("🏢 Dados Gerais da Academia")

    dados = col_academia.find_one()
    if dados:
        st.success(f"**Academia:** {dados.get('nome','')}")
        st.write(f"**CNPJ:** {dados.get('cnpj','')}")
        if dados.get("logo_url"):
            st.image(dados["logo_url"], width=150)

    with st.form("form_geral"):
        nome = st.text_input("Nome da Academia", value=dados.get("nome") if dados else "")
        cnpj = st.text_input("CNPJ", value=dados.get("cnpj") if dados else "")
        logo = st.file_uploader("Logo da Academia", type=["png","jpg","jpeg"])

        if st.form_submit_button("Salvar Dados Gerais"):
            logo_url = None
            if logo:
                logo_path = f"logo_academia.{logo.type.split('/')[-1]}"
                with open(logo_path, "wb") as f:
                    f.write(logo.getbuffer())
                logo_url = logo_path

            col_academia.delete_many({})
            col_academia.insert_one({
                "nome": nome,
                "cnpj": cnpj,
                "logo_url": logo_url
            })
            st.success("Dados salvos!")
            st.rerun()

def pagina_alunos():
    st.header("👨‍🎓 Alunos Cadastrados")
    alunos = list(col_alunos.find())
    if alunos:
        for a in alunos:
            st.markdown(f"✅ **{a['nome']}** | RG: {a.get('rg','')} | Faixa: {a.get('faixa','')} | Tel: {a.get('telefone','')}")
    else:
        st.info("Nenhum aluno cadastrado.")

    st.divider()
    st.header("Cadastrar Novo Aluno")
    with st.form("form_novo_aluno"):
        nome = st.text_input("Nome")
        rg = st.text_input("RG")
        faixa = st.selectbox("Faixa", list(belt_progression.keys()))
        data_nasc = st.date_input("Data de Nascimento")
        telefone = st.text_input("Telefone/WhatsApp", max_chars=15)
        if st.form_submit_button("Cadastrar"):
            if not nome:
                st.error("Nome é obrigatório!")
            else:
                col_alunos.insert_one({
                    "nome": nome,
                    "rg": rg,
                    "faixa": faixa,
                    "data_nascimento": data_nasc.strftime("%Y-%m-%d"),
                    "telefone": telefone
                })
                st.success("Aluno cadastrado!")
                st.rerun()

def pagina_presencas():
    st.header("📋 Presenças")

    hoje = datetime.today().strftime("%Y-%m-%d")
    presenca = col_presencas.find_one({"data": hoje})
    st.subheader("Presenças Hoje")
    if presenca and presenca.get("presentes"):
        for nome in presenca["presentes"]:
            st.markdown(f"✅ {nome}")
    else:
        st.info("Nenhuma presença registrada hoje.")

    st.header("Registrar Presença")
    alunos = list(col_alunos.find())
    nomes_alunos = [a["nome"] for a in alunos]
    with st.form("form_presenca"):
        presentes = st.multiselect("Selecione os alunos presentes", nomes_alunos)
        if st.form_submit_button("Registrar"):
            if presenca:
                col_presencas.update_one({"_id": presenca["_id"]}, {"$set": {"presentes": presentes}})
            else:
                col_presencas.insert_one({"data": hoje, "presentes": presentes})
            st.success("Presença registrada!")
            st.rerun()

def pagina_mensalidades():
    st.header("💰 Mensalidades")

    mensalidades = list(col_mensalidades.find())
    if mensalidades:
        for m in mensalidades:
            st.markdown(f"Aluno: **{m['aluno']}** - Vencimento: {m['vencimento']} - Pago: {'Sim' if m.get('pago') else 'Não'}")
    else:
        st.info("Nenhuma mensalidade cadastrada.")

    st.header("Cadastrar Mensalidade")
    alunos = list(col_alunos.find())
    nomes_alunos = [a["nome"] for a in alunos]
    with st.form("form_mensalidade"):
        aluno = st.selectbox("Aluno", nomes_alunos)
        vencimento = st.date_input("Data de Vencimento")
        pago = st.checkbox("Pago?")
        if st.form_submit_button("Cadastrar"):
            col_mensalidades.insert_one({
                "aluno": aluno,
                "vencimento": vencimento.strftime("%Y-%m-%d"),
                "pago": pago
            })
            st.success("Mensalidade cadastrada!")
            st.rerun()

def pagina_exames():
    st.header("🥋 Exames")

    exames = list(col_exames.find())
    if exames:
        for e in exames:
            st.markdown(f"Aluno: **{e['aluno']}** | Faixa: {e['faixa']} | Data: {e['data']}")
    else:
        st.info("Nenhum exame registrado.")

    st.header("Registrar Exame")
    alunos = list(col_alunos.find())
    nomes_alunos = [a["nome"] for a in alunos]
    with st.form("form_exame"):
        aluno = st.selectbox("Aluno", nomes_alunos)
        faixa = st.selectbox("Faixa", list(belt_progression.keys()))
        data_exame = st.date_input("Data do Exame")
        if st.form_submit_button("Registrar"):
            col_exames.insert_one({
                "aluno": aluno,
                "faixa": faixa,
                "data": data_exame.strftime("%Y-%m-%d")
            })
            st.success("Exame registrado!")
            st.rerun()

# continua abaixo...
def pagina_equipamentos():
    st.header("🎽 Equipamentos")

    equipamentos = list(col_equipamentos.find())
    if equipamentos:
        for eq in equipamentos:
            cor_faixa = eq.get("cor_faixa", "")
            faixa_info = f" | Cor Faixa: {cor_faixa}" if cor_faixa else ""
            st.markdown(
                f"**Tipo:** {eq['tipo']}  \n"
                f"**Tamanho:** {eq['tamanho']}  \n"
                f"**Código:** {eq['codigo']}  \n"
                f"**Estado:** {eq['estado']}{faixa_info}"
            )
            st.markdown("---")
    else:
        st.info("Nenhum equipamento cadastrado.")

    st.header("Adicionar Equipamento")
    with st.form("form_equipamento"):
        tipo = st.selectbox("Tipo de Equipamento", 
            ["Kimono", "Faixa", "Luvas", "Colete", "Protetor Bucal", "Bandeira", "Apostila"])
        tamanho = st.selectbox("Tamanho", ["PP", "P", "M", "G", "GG", "XG"])
        codigo = st.text_input("Código/Número (ex: K001, F001)")
        estado = st.selectbox("Estado", ["Novo", "Bom", "Regular", "Ruim"])
        cor_faixa = None
        if tipo.lower() == "faixa":
            cor_faixa = st.selectbox("Cor da Faixa", 
                ["Branca", "Cinza", "Azul", "Amarela", "Vermelha", "Laranja", "Verde", "Roxa", "Marrom", "Preta"])

        if st.form_submit_button("Adicionar"):
            if not codigo.strip():
                st.error("Informe o código do equipamento.")
            else:
                equip_doc = {
                    "tipo": tipo,
                    "tamanho": tamanho,
                    "codigo": codigo.strip(),
                    "estado": estado,
                }
                if cor_faixa:
                    equip_doc["cor_faixa"] = cor_faixa

                existe = col_equipamentos.find_one({"codigo": equip_doc["codigo"]})
                if existe:
                    st.error("Já existe um equipamento com esse código.")
                else:
                    col_equipamentos.insert_one(equip_doc)
                    st.success("Equipamento cadastrado!")
                    st.rerun()

def pagina_emprestimos():
    st.header("📦 Gerenciamento de Empréstimos")

    # --- Registrar Novo Empréstimo ---
    with st.expander("Registrar Novo Empréstimo", expanded=True):
        alunos = list(col_alunos.find())
        equipamentos = list(col_equipamentos.find({"estado": {"$in": ["Novo", "Bom", "Regular"]}}))
        emprestados_ids = [e['equipamento_id'] for e in col_emprestimos.find({"devolvido": False})]
        equipamentos_disponiveis = [eq for eq in equipamentos if eq["_id"] not in emprestados_ids]

        nomes_alunos = [a["nome"] for a in alunos]
        nomes_equip = [f"{eq['tipo']} ({eq['codigo']})" for eq in equipamentos_disponiveis]

        aluno_sel = st.selectbox("Aluno", [""] + nomes_alunos)
        equipamento_sel = st.selectbox("Equipamento Disponível", [""] + nomes_equip)
        data_emprestimo = st.date_input("Data de Empréstimo", value=datetime.today())
        data_devolucao = st.date_input("Data de Devolução Prevista", value=datetime.today() + timedelta(days=7))
        observacoes = st.text_input("Observações")

        if st.button("Registrar Empréstimo"):
            if not aluno_sel:
                st.error("Selecione um aluno.")
            elif not equipamento_sel:
                st.error("Selecione um equipamento disponível.")
            elif data_devolucao < data_emprestimo:
                st.error("Data de devolução não pode ser anterior à data do empréstimo.")
            else:
                aluno_doc = next((a for a in alunos if a["nome"] == aluno_sel), None)
                equipamento_doc = next((eq for eq in equipamentos_disponiveis if f"{eq['tipo']} ({eq['codigo']})" == equipamento_sel), None)

                if not aluno_doc or not equipamento_doc:
                    st.error("Erro ao localizar aluno ou equipamento.")
                else:
                    col_emprestimos.insert_one({
                        "aluno_id": aluno_doc["_id"],
                        "aluno": aluno_sel,
                        "equipamento_id": equipamento_doc["_id"],
                        "equipamento": equipamento_sel,
                        "data_emprestimo": data_emprestimo.strftime("%Y-%m-%d"),
                        "data_devolucao": data_devolucao.strftime("%Y-%m-%d"),
                        "observacoes": observacoes,
                        "devolvido": False,
                    })
                    st.success("Empréstimo registrado!")
                    st.rerun()

    st.markdown("---")

    # --- Empréstimos Ativos ---
    st.subheader("Empréstimos Ativos")
    emprestimos_ativos = list(col_emprestimos.find({"devolvido": False}))
    if not emprestimos_ativos:
        st.info("Nenhum empréstimo ativo no momento.")
    else:
        for emp in emprestimos_ativos:
            col1, col2 = st.columns([7, 1])
            with col1:
                st.markdown(
                    f"**Aluno:** {emp['aluno']}  \n"
                    f"**Equipamento:** {emp['equipamento']}  \n"
                    f"**Data Empréstimo:** {emp['data_emprestimo']}  \n"
                    f"**Previsão Devolução:** {emp['data_devolucao']}  \n"
                    f"**Observações:** {emp.get('observacoes','')}"
                )
            with col2:
                if st.button(f"Registrar Devolução - {emp['aluno']} - {emp['equipamento']}", key=f"dev_{emp['_id']}"):
                    col_emprestimos.update_one({"_id": emp["_id"]}, {"$set": {"devolvido": True}})
                    st.success(f"Devolução registrada para {emp['aluno']}.")
                    st.rerun()

    st.markdown("---")

    # --- Histórico de Empréstimos ---
    st.subheader("Histórico de Empréstimos")
    emprestimos_todos = list(col_emprestimos.find().sort("data_emprestimo", -1))
    if not emprestimos_todos:
        st.info("Nenhum histórico de empréstimos.")
    else:
        for emp in emprestimos_todos:
            status = "✅ Devolvido" if emp.get("devolvido", False) else "❌ Em aberto"
            st.markdown(
                f"**Aluno:** {emp['aluno']}  \n"
                f"**Equipamento:** {emp['equipamento']}  \n"
                f"**Data Empréstimo:** {emp['data_emprestimo']}  \n"
                f"**Data Devolução Prevista:** {emp['data_devolucao']}  \n"
                f"**Observações:** {emp.get('observacoes','')}  \n"
                f"**Status:** {status}"
            )
            st.markdown("---")

# --- Execução Principal ---
if col_usuarios.count_documents({}) == 0:
    criar_admin()
elif not st.session_state["logado"]:
    login()
else:
    enviar_alerta_mensalidade()

    st.markdown("## 🥋 空手道 (Karatedō) - Sistema de Karatê 🇯🇵")

    st.markdown("### Escolha uma página:")

    # --- Menu em Botões ---
    paginas = {
        "Cadastros Gerais": pagina_geral,
        "Alunos": pagina_alunos,
        "Presenças": pagina_presencas,
        "Mensalidades": pagina_mensalidades,
        "Exames": pagina_exames,
        "Equipamentos": pagina_equipamentos,
        "Empréstimos": pagina_emprestimos
    }

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Cadastros Gerais"):
            pagina_geral()
    with col2:
        if st.button("Alunos"):
            pagina_alunos()
    with col3:
        if st.button("Presenças"):
            pagina_presencas()
    with col4:
        if st.button("Mensalidades"):
            pagina_mensalidades()

    col5, col6, col7 = st.columns(3)
    with col5:
        if st.button("Exames"):
            pagina_exames()
    with col6:
        if st.button("Equipamentos"):
            pagina_equipamentos()
    with col7:
        if st.button("Empréstimos"):
            pagina_emprestimos()

    st.markdown("---")
    if st.button("🚪 Sair"):
        logout()
