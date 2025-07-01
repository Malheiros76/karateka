// server.js - Servidor para Sistema de Karatê
const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');
const cors = require('cors');
const path = require('path');
const multer = require('multer');

const app = express();
const PORT = 3000;

// Configuração do MongoDB
const MONGODB_URI = 'const uri = mongodb+srv://bibliotecaluizcarlos:8ax7sWrmiCMiQdGs@cluster0.rreynsd.mongodb.net/sistemakarate?retryWrites=true&w=majority&appName=Cluster0';
const DATABASE_NAME = 'karateSystem';

// Configuração do multer para upload de arquivos
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, 'uploads/')
  },
  filename: function (req, file, cb) {
    cb(null, Date.now() + '-' + file.originalname)
  }
});
const upload = multer({ storage: storage });

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));
app.use('/uploads', express.static('uploads'));

let db;

// Conectar ao MongoDB
MongoClient.connect(MONGODB_URI)
  .then(client => {
    console.log('🥋 Conectado ao MongoDB - Sistema de Karatê');
    db = client.db(DATABASE_NAME);
    
    // Criar índices para melhor performance
    db.collection('students').createIndex({ rg: 1 });
    db.collection('students').createIndex({ name: 1 });
    db.collection('attendance').createIndex({ studentId: 1, date: 1 });
    db.collection('payments').createIndex({ studentId: 1, month: 1 });
    db.collection('exams').createIndex({ studentId: 1, examDate: 1 });
  })
  .catch(error => console.error('Erro ao conectar ao MongoDB:', error));

// ================== ROTAS DA API ==================

// === ACADEMIA ===
// GET - Buscar dados da academia
app.get('/api/academy', async (req, res) => {
  try {
    const academy = await db.collection('academy').findOne({});
    res.json(academy || {});
  } catch (error) {
    res.status(500).json({ error: 'Erro ao buscar dados da academia' });
  }
});

// POST - Salvar dados da academia
app.post('/api/academy', upload.single('logo'), async (req, res) => {
  try {
    const academyData = {
      name: req.body.name,
      cnpj: req.body.cnpj,
      logo: req.file ? req.file.filename : null,
      updatedAt: new Date()
    };

    await db.collection('academy').replaceOne({}, academyData, { upsert: true });
    res.json({ message: 'Dados da academia salvos com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao salvar dados da academia' });
  }
});

// === ALUNOS ===
// GET - Buscar todos os alunos
app.get('/api/students', async (req, res) => {
  try {
    const students = await db.collection('students').find({}).sort({ name: 1 }).toArray();
    res.json(students);
  } catch (error) {
    res.status(500).json({ error: 'Erro ao buscar alunos' });
  }
});

// POST - Criar novo aluno
app.post('/api/students', async (req, res) => {
  try {
    const { name, rg, address, birth, height, category, belt, examDate } = req.body;
    
    if (!name || !rg || !birth) {
      return res.status(400).json({ error: 'Nome, RG e data de nascimento são obrigatórios' });
    }

    // Verificar se RG já existe
    const existingStudent = await db.collection('students').findOne({ rg });
    if (existingStudent) {
      return res.status(400).json({ error: 'Já existe um aluno com este RG' });
    }

    const newStudent = {
      name,
      rg,
      address,
      birth: new Date(birth),
      height: parseFloat(height) || 0,
      category,
      belt,
      examDate: examDate ? new Date(examDate) : new Date(),
      createdAt: new Date(),
      active: true
    };

    const result = await db.collection('students').insertOne(newStudent);
    res.status(201).json({ 
      message: 'Aluno cadastrado com sucesso', 
      id: result.insertedId 
    });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao cadastrar aluno' });
  }
});

// PUT - Atualizar aluno
app.put('/api/students/:id', async (req, res) => {
  try {
    const { name, rg, address, birth, height, category, belt, examDate } = req.body;
    
    const updateData = {
      name,
      rg,
      address,
      birth: new Date(birth),
      height: parseFloat(height) || 0,
      category,
      belt,
      examDate: examDate ? new Date(examDate) : new Date(),
      updatedAt: new Date()
    };

    const result = await db.collection('students').updateOne(
      { _id: new ObjectId(req.params.id) },
      { $set: updateData }
    );

    if (result.matchedCount === 0) {
      return res.status(404).json({ error: 'Aluno não encontrado' });
    }

    res.json({ message: 'Aluno atualizado com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao atualizar aluno' });
  }
});

// DELETE - Deletar aluno (desativar)
app.delete('/api/students/:id', async (req, res) => {
  try {
    const result = await db.collection('students').updateOne(
      { _id: new ObjectId(req.params.id) },
      { $set: { active: false, deletedAt: new Date() } }
    );

    if (result.matchedCount === 0) {
      return res.status(404).json({ error: 'Aluno não encontrado' });
    }

    res.json({ message: 'Aluno desativado com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao desativar aluno' });
  }
});

// === PRESENÇAS ===
// GET - Buscar presenças por mês
app.get('/api/attendance/:month', async (req, res) => {
  try {
    const month = req.params.month; // formato: 2024-01
    const [year, monthNum] = month.split('-');
    
    const startDate = new Date(year, monthNum - 1, 1);
    const endDate = new Date(year, monthNum, 0);
    
    const attendance = await db.collection('attendance').find({
      date: {
        $gte: startDate,
        $lte: endDate
      }
    }).toArray();
    
    res.json(attendance);
  } catch (error) {
    res.status(500).json({ error: 'Erro ao buscar presenças' });
  }
});

// POST - Salvar presenças
app.post('/api/attendance', async (req, res) => {
  try {
    const { attendanceData } = req.body; // Array de objetos { studentId, date, present }
    
    const operations = attendanceData.map(record => ({
      updateOne: {
        filter: { 
          studentId: new ObjectId(record.studentId), 
          date: new Date(record.date) 
        },
        update: { 
          $set: { 
            present: record.present,
            updatedAt: new Date()
          }
        },
        upsert: true
      }
    }));

    await db.collection('attendance').bulkWrite(operations);
    res.json({ message: 'Presenças salvas com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao salvar presenças' });
  }
});

// === MENSALIDADES ===
// GET - Buscar mensalidades por aluno
app.get('/api/payments/:studentId', async (req, res) => {
  try {
    const payments = await db.collection('payments').find({
      studentId: new ObjectId(req.params.studentId)
    }).sort({ month: -1 }).toArray();
    
    res.json(payments);
  } catch (error) {
    res.status(500).json({ error: 'Erro ao buscar mensalidades' });
  }
});

// GET - Verificar alertas de vencimento
app.get('/api/payments/alerts', async (req, res) => {
  try {
    const today = new Date();
    const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
    
    // Buscar alunos com mensalidades vencendo
    const students = await db.collection('students').find({ active: true }).toArray();
    const alerts = [];
    
    for (const student of students) {
      const lastPayment = await db.collection('payments')
        .findOne({ studentId: student._id }, { sort: { month: -1 } });
      
      // Calcular próximo vencimento
      const dueDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      
      if (dueDate <= nextWeek) {
        alerts.push({
          student: student,
          dueDate: dueDate,
          lastPayment: lastPayment
        });
      }
    }
    
    res.json(alerts);
  } catch (error) {
    res.status(500).json({ error: 'Erro ao verificar alertas' });
  }
});

// POST - Registrar pagamento
app.post('/api/payments', async (req, res) => {
  try {
    const { studentId, month, amount, paymentDate, method } = req.body;
    
    const payment = {
      studentId: new ObjectId(studentId),
      month: month, // formato: 2024-01
      amount: parseFloat(amount),
      paymentDate: paymentDate ? new Date(paymentDate) : new Date(),
      method: method || 'cash',
      createdAt: new Date()
    };

    await db.collection('payments').insertOne(payment);
    res.status(201).json({ message: 'Pagamento registrado com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao registrar pagamento' });
  }
});

// === EXAMES ===
// GET - Verificar elegibilidade para exames
app.get('/api/exams/eligibility', async (req, res) => {
  try {
    const beltProgression = {
      'branca': { next: 'cinza', months: 3, value: 40.00 },
      'cinza': { next: 'azul', months: 3, value: 45.00 },
      'azul': { next: 'amarela', months: 3, value: 55.00 },
      'amarela': { next: 'vermelha', months: 3, value: 60.00 },
      'vermelha': { next: 'laranja', months: 6, value: 65.00 },
      'laranja': { next: 'verde', months: 9, value: 70.00 },
      'verde': { next: 'roxa', months: 9, value: 75.00 },
      'roxa': { next: 'marrom2', months: 12, value: 80.00 },
      'marrom2': { next: 'marrom1', months: 12, value: 90.00 }
    };

    const students = await db.collection('students').find({ active: true }).toArray();
    const eligibility = [];

    for (const student of students) {
      const progression = beltProgression[student.belt];
      if (!progression) continue;

      const examDate = new Date(student.examDate);
      const today = new Date();
      const monthsDiff = (today.getFullYear() - examDate.getFullYear()) * 12 + 
                        (today.getMonth() - examDate.getMonth());

      eligibility.push({
        student: student,
        currentBelt: student.belt,
        nextBelt: progression.next,
        monthsSinceLastExam: monthsDiff,
        monthsRequired: progression.months,
        examValue: progression.value,
        canTakeExam: monthsDiff >= progression.months
      });
    }

    res.json(eligibility);
  } catch (error) {
    res.status(500).json({ error: 'Erro ao verificar elegibilidade' });
  }
});

// POST - Aprovar exame
app.post('/api/exams/approve', async (req, res) => {
  try {
    const { studentId, newBelt, examDate } = req.body;
    
    // Atualizar faixa do aluno
    await db.collection('students').updateOne(
      { _id: new ObjectId(studentId) },
      { 
        $set: { 
          belt: newBelt,
          examDate: examDate ? new Date(examDate) : new Date(),
          updatedAt: new Date()
        }
      }
    );

    // Registrar exame
    const examRecord = {
      studentId: new ObjectId(studentId),
      previousBelt: req.body.previousBelt,
      newBelt: newBelt,
      examDate: examDate ? new Date(examDate) : new Date(),
      status: 'approved',
      createdAt: new Date()
    };

    await db.collection('exams').insertOne(examRecord);
    
    res.json({ message: 'Exame aprovado com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao aprovar exame' });
  }
});

// POST - Remarcar exame
app.post('/api/exams/reschedule', async (req, res) => {
  try {
    const { studentId, newExamDate } = req.body;
    
    const examRecord = {
      studentId: new ObjectId(studentId),
      examDate: new Date(newExamDate),
      status: 'rescheduled',
      createdAt: new Date()
    };

    await db.collection('exams').insertOne(examRecord);
    
    res.json({ message: 'Exame remarcado com sucesso' });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao remarcar exame' });
  }
});

// === RELATÓRIOS ===
// GET - Relatório de presenças por aluno
app.get('/api/reports/attendance/:studentId/:month', async (req, res) => {
  try {
    const { studentId, month } = req.params;
    const [year, monthNum] = month.split('-');
    
    const startDate = new Date(year, monthNum - 1, 1);
    const endDate = new Date(year, monthNum, 0);
    
    const attendance = await db.collection('attendance').find({
      studentId: new ObjectId(studentId),
      date: { $gte: startDate, $lte: endDate }
    }).toArray();
    
    const totalDays = attendance.length;
    const presentDays = attendance.filter(a => a.present).length;
    const attendanceRate = totalDays > 0 ? (presentDays / totalDays * 100).toFixed(1) : 0;
    
    res.json({
      totalDays,
      presentDays,
      absentDays: totalDays - presentDays,
      attendanceRate: `${attendanceRate}%`
    });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao gerar relatório de presenças' });
  }
});

// GET - Relatório financeiro
app.get('/api/reports/financial/:month', async (req, res) => {
  try {
    const month = req.params.month;
    
    const payments = await db.collection('payments').find({ month }).toArray();
    const students = await db.collection('students').find({ active: true }).toArray();
    
    const totalReceived = payments.reduce((sum, payment) => sum + payment.amount, 0);
    const totalExpected = students.length * 100; // Assumindo mensalidade de R$ 100
    const pendingAmount = totalExpected - totalReceived;
    
    res.json({
      month,
      totalStudents: students.length,
      paymentsMade: payments.length,
      pendingPayments: students.length - payments.length,
      totalReceived,
      totalExpected,
      pendingAmount,
      collectionRate: ((payments.length / students.length) * 100).toFixed(1) + '%'
    });
  } catch (error) {
    res.status(500).json({ error: 'Erro ao gerar relatório financeiro' });
  }
});

// Servir o arquivo HTML principal
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'karate_management_system.html'));
});

// Middleware de tratamento de erros
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Algo deu errado!' });
});

app.listen(PORT, () => {
  console.log(`🥋 Servidor do Sistema de Karatê rodando em http://localhost:${PORT}`);
  console.log(`📁 Certifique-se de que a pasta 'uploads' existe para upload de logos`);
});
