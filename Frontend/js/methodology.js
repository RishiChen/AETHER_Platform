/**
 * AETHER Methodology & 11-Step Pipeline Module
 * SIH 2026 Problem Statement 26227
 */

function initMethodologyModule() {
  renderPipelineStrip();
  renderFalseAlarmMatrix();
}

function renderPipelineStrip() {
  const strip = document.getElementById('pipeline-steps-strip');
  const detailCard = document.getElementById('pipeline-detail-card');
  if (!strip || !window.AETHER_DATA) return;

  strip.innerHTML = '';
  const steps = window.AETHER_DATA.PIPELINE_STEPS;

  steps.forEach((step, idx) => {
    const box = document.createElement('div');
    box.className = `pipeline-step-box ${idx === 0 ? 'active' : ''}`;
    box.innerHTML = `
      <span class="step-num">${step.num}</span>
      <span class="step-name">${step.name}</span>
    `;

    box.addEventListener('click', () => {
      document.querySelectorAll('.pipeline-step-box').forEach(b => b.classList.remove('active'));
      box.classList.add('active');
      showStepDetail(step);
    });

    strip.appendChild(box);
  });

  // Default to step 1
  if (steps.length > 0) {
    showStepDetail(steps[0]);
  }
}

function showStepDetail(step) {
  const titleEl = document.getElementById('pipeline-step-title');
  const stageEl = document.getElementById('pipeline-step-stage');
  const descEl = document.getElementById('pipeline-step-desc');

  if (titleEl) titleEl.textContent = `Stage ${step.num}: ${step.name}`;
  if (stageEl) stageEl.textContent = step.stage.toUpperCase();
  if (descEl) descEl.innerHTML = `<strong>${step.summary}</strong><br><br>${step.details}`;
}

function renderFalseAlarmMatrix() {
  const tbody = document.getElementById('matrix-table-body');
  if (!tbody || !window.AETHER_DATA) return;

  tbody.innerHTML = '';
  window.AETHER_DATA.FALSE_ALARM_MATRIX.forEach(item => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="matrix-challenge">
        <span style="color: var(--accent-orange);">▲</span> ${item.challenge}
      </td>
      <td class="matrix-mitigation">${item.mitigation}</td>
      <td class="matrix-detail">${item.impact}</td>
    `;
    tbody.appendChild(tr);
  });
}

window.AETHER_METHODOLOGY = {
  initMethodologyModule
};
