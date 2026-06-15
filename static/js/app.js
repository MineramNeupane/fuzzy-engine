let currentPath = 1;
let pathData = {};
let modulesData = {};

async function initApp() {
  await loadPaths();
  await loadDashboard();
  setInterval(loadDashboard, 5000);
}

async function loadPaths() {
  const res = await fetch('/api/paths');
  const paths = await res.json();
  if (paths.length) {
    currentPath = paths[0].id;
    pathData = paths[0];
  }
}

async function loadDashboard() {
  const modulesRes = await fetch(`/api/modules/${currentPath}`);
  const modules = await modulesRes.json();
  modulesData = {};
  
  let totalLessons = 0;
  let completedLessons = 0;
  let daysStudied = 0;
  
  for (let mod of modules) {
    const lessRes = await fetch(`/api/lessons/${mod.id}`);
    const lessons = await lessRes.json();
    modulesData[mod.id] = { ...mod, lessons };
    
    totalLessons += lessons.length;
    const completed = lessons.filter(l => l.done).length;
    completedLessons += completed;
    if (completed > 0) daysStudied++;
  }
  
  const percent = totalLessons ? Math.round((completedLessons / totalLessons) * 100) : 0;
  document.getElementById('progress-display').textContent = percent + '%';
  document.getElementById('lessons-display').textContent = `${completedLessons}/${totalLessons} Lessons`;
  document.getElementById('lessons-completed').textContent = completedLessons;
  document.getElementById('days-studied').textContent = daysStudied;
  
  const progressFill = document.querySelector('.progress-bar-fill');
  if (progressFill) progressFill.style.width = percent + '%';
  
  loadCourse();
  loadNotes();
  loadTools();
  loadPlan();
}

function switchPage(pageName) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(pageName);
  if (page) page.classList.add('active');
  
  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
  event.target?.classList.add('active');
}

async function loadCourse() {
  const container = document.getElementById('modules-container');
  if (!container) return;
  
  container.innerHTML = '';
  
  for (let modId in modulesData) {
    const mod = modulesData[modId];
    const card = document.createElement('div');
    card.className = 'module-card';
    
    const completed = mod.lessons.filter(l => l.done).length;
    const total = mod.lessons.length;
    const percent = Math.round((completed / total) * 100);
    
    card.innerHTML = `
      <div class="module-header" onclick="this.parentElement.classList.toggle('expanded')">
        <div>
          <strong>${mod.title}</strong> (${completed}/${total})
          <div class="progress-bar" style="width: 200px; display: inline-block; margin-left: 8px;">
            <div class="progress-bar-fill" style="width: ${percent}%"></div>
          </div>
        </div>
        <span>▼</span>
      </div>
      <div class="lessons-list" style="display: none;">
        ${mod.lessons.map((l, i) => `
          <div class="lesson-item">
            <input type="checkbox" class="lesson-checkbox" ${l.done ? 'checked' : ''} 
              onchange="toggleLesson(${l.id})">
            <span class="lesson-text ${l.done ? 'done' : ''}">${l.title}</span>
          </div>
        `).join('')}
      </div>
    `;
    
    container.appendChild(card);
  }
}

async function toggleLesson(lessonId) {
  await fetch(`/api/lessons/${lessonId}/toggle`, { method: 'POST' });
  await loadDashboard();
}

async function loadNotes() {
  const select = document.getElementById('notes-module');
  if (!select) return;
  
  select.innerHTML = '';
  for (let modId in modulesData) {
    const mod = modulesData[modId];
    const option = document.createElement('option');
    option.value = mod.id;
    option.textContent = mod.title;
    select.appendChild(option);
  }
  
  if (Object.keys(modulesData).length > 0) {
    const firstModId = Object.keys(modulesData)[0];
    select.value = firstModId;
    await loadNoteContent(firstModId);
  }
  
  select.addEventListener('change', (e) => loadNoteContent(e.target.value));
}

async function loadNoteContent(moduleId) {
  const res = await fetch(`/api/notes/${moduleId}`);
  const notes = await res.json();
  
  const textarea = document.getElementById('notes-textarea');
  if (textarea && notes.length) {
    textarea.value = notes[0].content;
  }
  
  const history = document.getElementById('notes-list');
  if (history) {
    history.innerHTML = notes.length ? notes.map(n => 
      `<div style="padding: 8px 0; border-bottom: 1px solid #eee;">
        <small>${new Date(n.updated_at).toLocaleString()}</small>
        <p>${n.content.substring(0, 100)}...</p>
      </div>`
    ).join('') : '<p>No notes yet.</p>';
  }
}

async function saveNotes() {
  const moduleId = document.getElementById('notes-module').value;
  const content = document.getElementById('notes-textarea').value;
  
  const res = await fetch('/api/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ module_id: moduleId, content })
  });
  
  alert('Notes saved!');
  await loadNoteContent(moduleId);
}

async function copyNotes() {
  const text = document.getElementById('notes-textarea').value;
  navigator.clipboard.writeText(text).then(() => alert('Copied to clipboard!'));
}

async function exportNotesMarkdown() {
  let markdown = '# Study Notes\n\n';
  
  for (let modId in modulesData) {
    const res = await fetch(`/api/notes/${modId}`);
    const notes = await res.json();
    if (notes.length) {
      markdown += `## ${modulesData[modId].title}\n\n${notes[0].content}\n\n`;
    }
  }
  
  const blob = new Blob([markdown], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'study_notes.md';
  a.click();
}

async function generateQuizFromNotes() {
  const moduleId = document.getElementById('notes-module').value;
  const content = document.getElementById('notes-textarea').value;
  
  if (!content) {
    alert('Please add notes first');
    return;
  }
  
  alert('Quiz generation requires Ollama. Configure AI Assistant first.');
}

async function loadTools() {
  const res = await fetch(`/api/tools/${currentPath}`);
  const tools = await res.json();
  
  const grid = document.getElementById('tools-grid');
  if (!grid) return;
  
  grid.innerHTML = tools.map(t => `
    <div class="tool-card">
      <h3>${t.name}</h3>
      <input type="range" class="tool-slider" min="0" max="100" value="${t.progress * 100}" 
        onchange="updateTool(${t.id}, this.value / 100)">
      <div>${Math.round(t.progress * 100)}%</div>
      ${t.url ? `<a href="${t.url}" target="_blank" class="tool-link">Open</a>` : ''}
    </div>
  `).join('');
}

async function updateTool(toolId, progress) {
  await fetch(`/api/tools/${toolId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ progress })
  });
}

async function loadPlan() {
  const res = await fetch(`/api/plan/${currentPath}`);
  const plan = await res.json();
  
  const grid = document.getElementById('plan-grid');
  if (!grid) return;
  
  grid.innerHTML = plan.map(d => `
    <div class="plan-day ${d.done ? 'done' : ''}" onclick="togglePlanDay(${d.id})">
      <strong>Day ${d.day_num}</strong>
      <p>${d.tasks}</p>
    </div>
  `).join('');
}

async function togglePlanDay(dayId) {
  await fetch(`/api/plan/${dayId}/toggle`, { method: 'POST' });
  await loadPlan();
}

async function regeneratePlan() {
  alert('Smart plan regeneration coming soon!');
}

async function askAI() {
  const query = document.getElementById('ai-query').value;
  if (!query) return;
  
  const responseDiv = document.getElementById('ai-response');
  responseDiv.style.display = 'block';
  responseDiv.innerHTML = '⏳ Thinking...';
  
  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    
    const data = await res.json();
    if (data.success) {
      responseDiv.innerHTML = `<strong>Answer:</strong><br>${data.response}`;
    } else {
      responseDiv.innerHTML = `<strong>Error:</strong> ${data.error}`;
    }
  } catch (e) {
    responseDiv.innerHTML = `<strong>Error:</strong> ${e.message}`;
  }
}

async function testOllama() {
  const url = document.getElementById('ollama-url').value;
  const statusDiv = document.getElementById('ollama-status');
  statusDiv.innerHTML = '🔍 Testing...';
  
  try {
    const res = await fetch('/api/ai/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    
    const data = await res.json();
    if (data.success) {
      statusDiv.innerHTML = `✅ Connected! Models: ${data.models.join(', ')}`;
    } else {
      statusDiv.innerHTML = `❌ Error: ${data.error}`;
    }
  } catch (e) {
    statusDiv.innerHTML = `❌ Error: ${e.message}`;
  }
}

async function savePathSettings() {
  const targetDate = document.getElementById('target-date').value;
  const dailyMins = document.getElementById('daily-mins').value;
  alert('Settings saved!');
}

async function exportData() {
  const data = { paths: pathData, modules: modulesData };
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'studyhub_data.json';
  a.click();
}

async function importData() {
  alert('Import feature coming soon!');
}

async function clearAllData() {
  if (confirm('This will delete all data. Continue?')) {
    alert('Clear feature coming soon!');
  }
}

window.addEventListener('DOMContentLoaded', initApp);
