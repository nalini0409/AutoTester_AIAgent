/* AutoTester AI — frontend logic */

const form        = document.getElementById('testForm');
const urlInput    = document.getElementById('urlInput');
const submitBtn   = document.getElementById('submitBtn');
const btnLabel    = submitBtn.querySelector('.btn-label');
const btnSpinner  = submitBtn.querySelector('.btn-spinner');

const skillsBadges  = document.getElementById('skillsBadges');
const progressCard  = document.getElementById('progressCard');
const progressLog   = document.getElementById('progressLog');
const reportCard    = document.getElementById('reportCard');
const scoreRing     = document.getElementById('scoreRing');
const scoreValue    = document.getElementById('scoreValue');
const testedUrl     = document.getElementById('testedUrl');
const summaryBox    = document.getElementById('summaryBox');
const summaryText   = document.getElementById('summaryText');
const skillsResults = document.getElementById('skillsResults');
const copyBtn       = document.getElementById('copyBtn');
const newTestBtn    = document.getElementById('newTestBtn');

let currentReport   = null;
let activeSource    = null;

// ── Load active skills on startup ──────────────────────────────────────────
async function loadSkills() {
  try {
    const res  = await fetch('/api/skills');
    const data = await res.json();
    if (!data.skills?.length) return;
    skillsBadges.innerHTML = data.skills
      .map(s => `<span class="skill-badge" title="${s.description}">${s.name}</span>`)
      .join('');
    skillsBadges.classList.remove('hidden');
  } catch (_) { /* silently ignore */ }
}

loadSkills();

// ── Form submit ─────────────────────────────────────────────────────────────
form.addEventListener('submit', e => {
  e.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;
  startTest(url);
});

newTestBtn.addEventListener('click', () => {
  reportCard.classList.add('hidden');
  progressCard.classList.add('hidden');
  urlInput.value = '';
  urlInput.focus();
});

copyBtn.addEventListener('click', () => {
  if (!currentReport) return;
  navigator.clipboard.writeText(JSON.stringify(currentReport, null, 2))
    .then(() => { copyBtn.textContent = 'Copied!'; setTimeout(() => { copyBtn.textContent = 'Copy JSON report'; }, 2000); })
    .catch(() => {});
});

// ── Test runner ─────────────────────────────────────────────────────────────
function startTest(url) {
  if (activeSource) { activeSource.close(); activeSource = null; }

  setLoading(true);
  resetUI();
  progressCard.classList.remove('hidden');

  activeSource = new EventSource(`/api/test?url=${encodeURIComponent(url)}`);

  activeSource.onmessage = e => {
    let payload;
    try { payload = JSON.parse(e.data); } catch (_) { return; }
    handleEvent(payload, url);
  };

  activeSource.onerror = () => {
    addProgressItem('Connection error — check the server console.', '✗');
    setLoading(false);
    activeSource.close();
    activeSource = null;
  };
}

function handleEvent(payload, url) {
  switch (payload.type) {
    case 'started':
      addProgressItem(`Analyzing ${payload.url || url} …`, '🔍');
      break;

    case 'progress':
      addProgressItem(payload.message, payload.message.startsWith('✗') ? '✗' : '');
      break;

    case 'skill_result':
      renderSkillCard(payload.result);
      break;

    case 'report':
      currentReport = payload.data;
      renderReport(payload.data);
      setLoading(false);
      break;

    case 'error':
      addProgressItem(`Error: ${payload.message}`, '✗');
      setLoading(false);
      break;

    case 'done':
      setLoading(false);
      if (activeSource) { activeSource.close(); activeSource = null; }
      break;
  }
}

// ── UI helpers ───────────────────────────────────────────────────────────────
function resetUI() {
  progressLog.innerHTML  = '';
  skillsResults.innerHTML = '';
  reportCard.classList.add('hidden');
  summaryBox.classList.add('hidden');
  scoreValue.textContent = '—';
  scoreRing.className    = 'score-ring';
  currentReport          = null;
}

function setLoading(on) {
  submitBtn.disabled = on;
  btnLabel.textContent = on ? 'Running…' : 'Analyze';
  btnSpinner.classList.toggle('hidden', !on);
}

function addProgressItem(text, icon) {
  const li = document.createElement('li');
  li.className = 'progress-item';
  // strip leading emoji from text if icon provided separately
  const displayText = icon ? text.replace(/^[✓✗🔍]\s*/, '') : text;
  li.innerHTML = `
    <span class="pi-icon">${icon || (text.startsWith('✓') ? '✓' : text.startsWith('✗') ? '✗' : '•')}</span>
    <span class="pi-text">${escHtml(displayText)}</span>`;
  progressLog.appendChild(li);
  li.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderReport(data) {
  reportCard.classList.remove('hidden');

  const score = data.overall_score;
  scoreValue.textContent = score !== null ? score.toFixed(1) : 'N/A';
  testedUrl.textContent  = data.url;

  if (score !== null) {
    scoreRing.classList.add(score >= 7 ? 'green' : score >= 4 ? 'yellow' : 'red');
  }

  if (data.summary) {
    summaryText.textContent = data.summary;
    summaryBox.classList.remove('hidden');
  }

  // Skill cards may already be rendered; if not (e.g. failed run), render them now
  if (!skillsResults.children.length && data.skill_results?.length) {
    data.skill_results.forEach(renderSkillCard);
  }
}

function renderSkillCard(result) {
  // Avoid duplicates
  if (document.getElementById(`skill-${slugify(result.skill_name)}`)) return;

  const score    = result.score;
  const colorCls = score === null ? 'gray' : score >= 7 ? 'green' : score >= 4 ? 'yellow' : 'red';
  const scoreLabel = score !== null ? `${score.toFixed(1)}/10` : (result.error ? 'Error' : 'N/A');

  const card = document.createElement('div');
  card.className = 'skill-card';
  card.id = `skill-${slugify(result.skill_name)}`;

  const findingsHtml = (result.findings || [])
    .map(f => `<li class="finding-item">${escHtml(f)}</li>`)
    .join('');

  card.innerHTML = `
    <div class="skill-header" role="button" aria-expanded="false" tabindex="0">
      <span class="skill-name">${escHtml(result.skill_name)}</span>
      <span class="skill-right">
        <span class="skill-score-badge ${colorCls}">${scoreLabel}</span>
        <span class="chevron">▼</span>
      </span>
    </div>
    <div class="skill-body">
      <div class="skill-body-inner">
        ${result.details ? `<p class="skill-details">${escHtml(result.details)}</p>` : ''}
        ${findingsHtml ? `<ul class="findings-list">${findingsHtml}</ul>` : ''}
        ${result.error ? `<p class="skill-details" style="color:var(--red)">${escHtml(result.error)}</p>` : ''}
      </div>
    </div>`;

  const header = card.querySelector('.skill-header');
  header.addEventListener('click', () => toggleCard(card, header));
  header.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') toggleCard(card, header); });

  skillsResults.appendChild(card);
  // Auto-open the first card
  if (skillsResults.children.length === 1) toggleCard(card, header);
}

function toggleCard(card, header) {
  const open = card.classList.toggle('open');
  header.setAttribute('aria-expanded', open);
}

function slugify(str) {
  return str.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
