from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)

# Conecte ao seu MongoDB Atlas
client = MongoClient("mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/")
db = client["karate"]

# Coleções
academia_col = db["academia"]
alunos_col = db["alunos"]
presencas_col = db["presencas"]
pagamentos_col = db["pagamentos"]
exames_col = db["exames"]

# ---------------------------
# Rotas Academia
# ---------------------------

@app.route("/academia", methods=["POST"])
def save_academia():
    data = request.json
    academia_col.delete_many({})   # sobrescreve tudo
    academia_col.insert_one(data)
    return jsonify({"message": "Dados da academia salvos com sucesso!"})

@app.route("/academia", methods=["GET"])
def get_academia():
    academia = academia_col.find_one({}, {"_id": 0})
    return jsonify(academia or {})

# ---------------------------
# Rotas Alunos
# ---------------------------

@app.route("/alunos", methods=["POST"])
def save_aluno():
    data = request.json
    alunos_col.insert_one(data)
    return jsonify({"message": "Aluno cadastrado com sucesso!"})

@app.route("/alunos", methods=["GET"])
def get_alunos():
    alunos = list(alunos_col.find({}, {"_id": 0}))
    return jsonify(alunos)

# ---------------------------
# Rotas Presenças (opcional)
# ---------------------------

@app.route("/presencas", methods=["POST"])
def save_presencas():
    data = request.json  # objeto { "studentId-date": true/false, ... }
    presencas_col.delete_many({})
    for key, value in data.items():
        presencas_col.insert_one({"key": key, "value": value})
    return jsonify({"message": "Presenças salvas!"})

@app.route("/presencas", methods=["GET"])
def get_presencas():
    presencas = {}
    for item in presencas_col.find():
        presencas[item["key"]] = item["value"]
    return jsonify(presencas)

# ---------------------------
# Rodar servidor
# ---------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

from flask import render_template

@app.route("/")
def index():
    return render_template("index.html")
