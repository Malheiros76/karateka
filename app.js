let systemData = {
    students: []
};

// ✅ Carregar dados da academia e alunos
function loadSystemData() {
    fetch("http://127.0.0.1:5000/academia")
        .then(response => response.json())
        .then(data => {
            if (data && data.name) {
                document.getElementById('academyName').textContent = data.name;
                document.getElementById('academyNameInput').value = data.name;
                document.getElementById('cnpj').value = data.cnpj || "";
            }
        })
        .catch(err => console.error("Erro ao buscar academia:", err));

    fetch("http://127.0.0.1:5000/alunos")
        .then(response => response.json())
        .then(students => {
            systemData.students = students;
            updateStudentsList();
            atualizarCampoNumeroAlunos();  // 🔁 Atualiza o número de alunos no campo
        })
        .catch(err => console.error("Erro ao buscar alunos:", err));
}

// ✅ Atualiza o campo de número de alunos automaticamente
function atualizarCampoNumeroAlunos() {
    const campo = document.getElementById('numeroAlunos');
    if (campo) {
        campo.value = systemData.students.length;
    }
}

// ✅ Calcular arrecadação com base no valor e número de alunos
function calcularArrecadacao() {
    const valorMensalidade = parseFloat(document.getElementById('mensalidadeValor').value);
    const numeroAlunos = parseInt(document.getElementById('numeroAlunos').value);

    if (isNaN(valorMensalidade) || isNaN(numeroAlunos)) {
        document.getElementById('resultadoArrecadacao').textContent = "⚠️ Preencha todos os campos corretamente.";
        return;
    }

    const total = valorMensalidade * numeroAlunos;

    document.getElementById('resultadoArrecadacao').textContent =
        `✅ O dojô irá arrecadar R$ ${total.toFixed(2).replace('.', ',')} no mês. 🗓️ Vencimento: todo dia 5.`;
}

// ✅ Salvar dados da academia
function saveGeneralData() {
    const data = {
        name: document.getElementById('academyNameInput').value,
        cnpj: document.getElementById('cnpj').value,
        logo: document.getElementById('academyLogo').files[0]?.name || ''
    };

    fetch("http://127.0.0.1:5000/academia", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    })
        .then(response => response.json())
        .then(result => {
            alert(result.message);
            document.getElementById('academyName').textContent = data.name || "Academia de Karatê";
        })
        .catch(err => console.error("Erro ao salvar academia:", err));
}

// ✅ Cadastrar aluno
function addStudent() {
    const student = {
        id: Date.now(),
        name: document.getElementById('studentName').value,
        rg: document.getElementById('studentRG').value,
        address: document.getElementById('studentAddress').value,
        birth: document.getElementById('studentBirth').value,
        height: document.getElementById('studentHeight').value,
        category: document.getElementById('studentCategory').value,
        belt: document.getElementById('studentBelt').value,
        examDate: document.getElementById('studentExamDate').value
    };

    if (!student.name || !student.rg || !student.birth) {
        alert('Preencha todos os campos obrigatórios!');
        return;
    }

    fetch("http://127.0.0.1:5000/alunos", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(student)
    })
        .then(response => response.json())
        .then(result => {
            alert(result.message);
            clearStudentForm();
            loadSystemData(); // Recarrega alunos e atualiza número
        })
        .catch(err => console.error("Erro ao cadastrar aluno:", err));
}
// ✅ Atualiza o campo de número de alunos automaticamente
function atualizarCampoNumeroAlunos() {
    const campo = document.getElementById('numeroAlunos');
    if (campo) {
        campo.value = systemData.students.length;
    }
}

// ✅ Calcular arrecadação com base no valor e número de alunos
function calcularArrecadacao() {
    const valorMensalidade = parseFloat(document.getElementById('mensalidadeValor').value);
    const numeroAlunos = parseInt(document.getElementById('numeroAlunos').value);

    if (isNaN(valorMensalidade) || isNaN(numeroAlunos)) {
        document.getElementById('resultadoArrecadacao').textContent = "⚠️ Preencha todos os campos corretamente.";
        return;
    }

    const total = valorMensalidade * numeroAlunos;

    document.getElementById('resultadoArrecadacao').textContent =
        `✅ O dojô irá arrecadar R$ ${total.toFixed(2).replace('.', ',')} no mês. 🗓️ Vencimento: todo dia 5.`;
}
// ✅ Exibir exames realizados na tabela
function updateExamsTable() {
    const tbody = document.getElementById("examsTableBody");
    tbody.innerHTML = "";

    // percorre cada aluno salvo
    systemData.students.forEach(student => {
        if (student.examDate && student.belt) {
            const row = document.createElement("tr");

            row.innerHTML = `
                <td>${student.name}</td>
                <td>${student.belt}</td>
                <td>${formatarDataBR(student.examDate)}</td>
                <td>${calcularNovaFaixa(student.belt)}</td>
            `;

            tbody.appendChild(row);
        }
    });
}

// ✅ Função auxiliar para formatar data
function formatarDataBR(dataISO) {
    if (!dataISO) return "-";
    const date = new Date(dataISO);
    return date.toLocaleDateString("pt-BR");
}

// ✅ Função fictícia para calcular nova faixa
function calcularNovaFaixa(faixaAtual) {
    // Simples exemplo: só incrementa a cor da faixa
    const faixas = ["Branca", "Amarela", "Laranja", "Verde", "Roxa", "Marrom", "Preta"];
    const idx = faixas.indexOf(faixaAtual);
    if (idx >= 0 && idx < faixas.length - 1) {
        return faixas[idx + 1];
    }
    return faixaAtual; // já está na última faixa
}

fetch("http://127.0.0.1:5000/alunos")
    .then(response => response.json())
    .then(students => {
        systemData.students = students;
        updateStudentsList();
        atualizarCampoNumeroAlunos(); // 🔁 chama a função assim que carrega alunos
    })
    .catch(err => console.error("Erro ao buscar alunos:", err));

    fetch("http://127.0.0.1:5000/alunos")
    .then(response => response.json())
    .then(students => {
        systemData.students = students;
        updateStudentsList();
        atualizarCampoNumeroAlunos();
        updateExamsTable(); // ✅ chama para preencher a grid de exames
    })
    .catch(err => console.error("Erro ao buscar alunos:", err));
