(() => {
  "use strict";

  // Paleta determinística de alto contraste para IDs de blocos alocados
  const BLOCK_COLORS = [
    "#2563eb", // azul
    "#0d9488", // teal
    "#d97706", // âmbar
    "#7c3aed", // roxo
    "#db2777", // rosa
    "#059669", // esmeralda
    "#ea580c", // laranja
    "#4f46e5", // índigo
    "#0284c7", // ciano escuro
    "#65a30d", // verde oliva
    "#be123c", // carmesim
    "#0891b2", // petróleo
  ];

  // Estado da simulação (snapshots pré-calculados pelo núcleo Python)
  const state = {
    steps: [],
    currentIndex: -1, // -1 = Passo 0 (antes do primeiro comando)
    scriptName: "",
    isPlaying: false,
    timerId: null,
    loadError: null,
  };

  // Referências do DOM
  const els = {
    fileInput: document.getElementById("scriptFileInput"),
    btnLoadSample: document.getElementById("btnLoadSample"),
    btnPrev: document.getElementById("btnPrev"),
    btnNext: document.getElementById("btnNext"),
    btnPlay: document.getElementById("btnPlay"),
    btnPause: document.getElementById("btnPause"),
    btnReset: document.getElementById("btnReset"),
    intervalInput: document.getElementById("intervalInput"),
    playbackBadge: document.getElementById("playbackBadge"),
    errorBanner: document.getElementById("errorBanner"),
    errorMessage: document.getElementById("errorMessage"),
    stepCounter: document.getElementById("stepCounter"),
    scriptName: document.getElementById("scriptName"),
    actionBadge: document.getElementById("actionBadge"),
    currentCommand: document.getElementById("currentCommand"),
    progressFill: document.getElementById("progressFill"),
    metaTotal: document.getElementById("metaTotal"),
    metaNextFitPtr: document.getElementById("metaNextFitPtr"),
    metaNextId: document.getElementById("metaNextId"),
    memoryEmptyState: document.getElementById("memoryEmptyState"),
    memoryEmptyText: document.getElementById("memoryEmptyText"),
    memoryStage: document.getElementById("memoryStage"),
    nextFitMarker: document.getElementById("nextFitMarker"),
    nextFitLabel: document.getElementById("nextFitLabel"),
    nextFitLine: document.getElementById("nextFitLine"),
    memoryBar: document.getElementById("memoryBar"),
    addressRuler: document.getElementById("addressRuler"),
    overlaySection: document.getElementById("overlaySection"),
    overlayTitle: document.getElementById("overlayTitle"),
    overlaySubtitle: document.getElementById("overlaySubtitle"),
    overlayTrack: document.getElementById("overlayTrack"),
    statUsed: document.getElementById("statUsed"),
    statFree: document.getElementById("statFree"),
    statHoles: document.getElementById("statHoles"),
    statLargestHole: document.getElementById("statLargestHole"),
    statUsage: document.getElementById("statUsage"),
    statUsageBar: document.getElementById("statUsageBar"),
    eventDetails: document.getElementById("eventDetails"),
    segmentsTableBody: document.getElementById("segmentsTableBody"),
    timelineCount: document.getElementById("timelineCount"),
    stepsTimeline: document.getElementById("stepsTimeline"),
  };

  function getBlockColor(blockId) {
    if (blockId == null) return "#94a3b8";
    const idx = Math.abs(Number(blockId) - 1) % BLOCK_COLORS.length;
    return BLOCK_COLORS[idx];
  }

  function formatBytes(val) {
    return `${val} B`;
  }

  function getIntervalMs() {
    const raw = parseFloat(els.intervalInput.value);
    if (Number.isNaN(raw) || raw <= 0) {
      els.intervalInput.value = "0.5";
      return 500;
    }
    return Math.max(50, Math.round(raw * 1000));
  }

  // --- Controle de Reprodução Automática ---

  function pausePlayback() {
    if (state.timerId !== null) {
      clearInterval(state.timerId);
      state.timerId = null;
    }
    if (state.isPlaying) {
      state.isPlaying = false;
      updateControlsAndBadges();
    }
  }

  function startPlayback() {
    if (state.steps.length === 0) return;
    if (state.currentIndex >= state.steps.length - 1) return;

    pausePlayback();
    state.isPlaying = true;
    updateControlsAndBadges();

    const tick = () => {
      if (state.currentIndex < state.steps.length - 1) {
        state.currentIndex += 1;
        render();
        if (state.currentIndex >= state.steps.length - 1) {
          pausePlayback();
        }
      } else {
        pausePlayback();
      }
    };

    // Avança o primeiro passo imediatamente se estiver no passo 0, ou aguarda o intervalo configurado
    const delayMs = getIntervalMs();
    state.timerId = setInterval(tick, delayMs);
  }

  function stepNextManual() {
    pausePlayback();
    if (state.currentIndex < state.steps.length - 1) {
      state.currentIndex += 1;
      render();
    }
  }

  function stepPrevManual() {
    pausePlayback();
    if (state.currentIndex >= 0) {
      state.currentIndex -= 1;
      render();
    }
  }

  function resetSimulation() {
    pausePlayback();
    state.currentIndex = -1;
    render();
  }

  function jumpToStep(index) {
    pausePlayback();
    if (index >= -1 && index < state.steps.length) {
      state.currentIndex = index;
      render();
    }
  }

  // --- Carregamento de Roteiros ---

  async function loadScriptText(scriptText, filename) {
    pausePlayback();
    state.loadError = null;

    try {
      const response = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script: scriptText }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `Erro HTTP ${response.status} ao processar roteiro.`);
      }

      if (!Array.isArray(payload.steps) || payload.steps.length === 0) {
        throw new Error("O roteiro não contém nenhum comando executável (init, alloc, freeid, freeaddr ou defrag).");
      }

      state.steps = payload.steps;
      state.currentIndex = -1;
      state.scriptName = filename;
      render();
    } catch (err) {
      state.steps = [];
      state.currentIndex = -1;
      state.scriptName = filename || "";
      state.loadError = err.message || "Falha inesperada ao carregar o roteiro.";
      render();
    }
  }

  async function loadSampleTrace() {
    pausePlayback();
    state.loadError = null;

    try {
      const response = await fetch("sample_trace.json");
      if (!response.ok) {
        throw new Error(`Não foi possível carregar sample_trace.json (HTTP ${response.status}).`);
      }
      const payload = await response.json();
      if (!Array.isArray(payload.steps) || payload.steps.length === 0) {
        throw new Error("O arquivo sample_trace.json está vazio ou inválido.");
      }

      state.steps = payload.steps;
      state.currentIndex = -1;
      state.scriptName = "exemplo_nextfit.cmd (amostra)";
      render();
    } catch (err) {
      state.loadError = err.message || "Falha ao carregar exemplo demonstrativo.";
      render();
    }
  }

  // --- Renderização ---

  function render() {
    updateControlsAndBadges();
    renderStatusAndErrors();
    renderMemoryView();
    renderStats();
    renderEventDetails();
    renderSegmentsTable();
    renderTimeline();
  }

  function updateControlsAndBadges() {
    const hasSteps = state.steps.length > 0;
    const atStart = state.currentIndex < 0;
    const atEnd = hasSteps && state.currentIndex >= state.steps.length - 1;

    els.btnPrev.disabled = !hasSteps || atStart;
    els.btnNext.disabled = !hasSteps || atEnd;
    els.btnPlay.disabled = !hasSteps || atEnd || state.isPlaying;
    els.btnPause.disabled = !state.isPlaying;
    els.btnReset.disabled = !hasSteps || atStart;

    els.playbackBadge.className = "badge";
    if (!hasSteps) {
      els.playbackBadge.classList.add("badge-idle");
      els.playbackBadge.textContent = "Aguardando roteiro";
    } else if (state.isPlaying) {
      els.playbackBadge.classList.add("badge-playing");
      els.playbackBadge.textContent = `Reproduzindo (${parseFloat(els.intervalInput.value) || 0.5}s)`;
    } else if (atEnd) {
      els.playbackBadge.classList.add("badge-done");
      els.playbackBadge.textContent = "Fim do roteiro";
    } else if (atStart) {
      els.playbackBadge.classList.add("badge-idle");
      els.playbackBadge.textContent = "Pronto para iniciar";
    } else {
      els.playbackBadge.classList.add("badge-paused");
      els.playbackBadge.textContent = "Pausado";
    }
  }

  function renderStatusAndErrors() {
    const total = state.steps.length;
    const currentStep = state.currentIndex >= 0 ? state.steps[state.currentIndex] : null;

    if (state.loadError) {
      els.errorBanner.classList.remove("hidden");
      els.errorMessage.textContent = state.loadError;
    } else if (currentStep && currentStep.event && currentStep.event.error) {
      els.errorBanner.classList.remove("hidden");
      els.errorMessage.textContent = currentStep.event.error;
    } else {
      els.errorBanner.classList.add("hidden");
      els.errorMessage.textContent = "";
    }

    els.scriptName.textContent = state.scriptName || "Nenhum roteiro carregado";

    if (!currentStep) {
      els.stepCounter.textContent = `Passo 0 de ${total}`;
      els.actionBadge.className = "action-badge action-idle";
      els.actionBadge.textContent = "INÍCIO";
      els.currentCommand.textContent = total > 0
        ? "Aguardando início (clique em Avançar ou Reproduzir)"
        : "Aguardando carregamento de roteiro (.cmd / .txt)";
      els.progressFill.style.width = "0%";
      return;
    }

    const stepNum = currentStep.step_index || state.currentIndex + 1;
    els.stepCounter.textContent = `Passo ${stepNum} de ${total}`;

    const action = (currentStep.event && currentStep.event.action) || "cmd";
    const hasError = Boolean(currentStep.event && currentStep.event.error);
    els.actionBadge.className = `action-badge ${hasError ? "action-error" : `action-${action}`}`;
    els.actionBadge.textContent = hasError ? `${action.toUpperCase()} · ERRO` : action.toUpperCase();
    els.currentCommand.textContent = currentStep.command;

    const pct = total > 0 ? (stepNum / total) * 100 : 0;
    els.progressFill.style.width = `${pct.toFixed(1)}%`;
  }

  function renderMemoryView() {
    const currentStep = state.currentIndex >= 0 ? state.steps[state.currentIndex] : null;

    if (!currentStep || !currentStep.snapshot || currentStep.snapshot.total_size <= 0) {
      els.memoryStage.classList.add("hidden");
      els.memoryEmptyState.classList.remove("hidden");
      els.metaTotal.textContent = "—";
      els.metaNextFitPtr.textContent = "—";
      els.metaNextId.textContent = "—";

      if (state.steps.length > 0) {
        els.memoryEmptyText.innerHTML =
          `Roteiro <strong>${escapeHtml(state.scriptName)}</strong> carregado com <strong>${state.steps.length} passos</strong>. ` +
          `Clique em <strong>Avançar</strong> ou <strong>Reproduzir</strong> para executar o Passo 1 (<code>${escapeHtml(state.steps[0].command)}</code>).`;
      } else {
        els.memoryEmptyText.innerHTML =
          `Carregue um arquivo <code>.cmd</code> ou <code>.txt</code> e clique em <strong>Avançar</strong> ou <strong>Reproduzir</strong> para iniciar a simulação.`;
      }
      return;
    }

    els.memoryEmptyState.classList.add("hidden");
    els.memoryStage.classList.remove("hidden");

    const snap = currentStep.snapshot;
    const event = currentStep.event || {};
    const totalSize = snap.total_size;

    els.metaTotal.textContent = formatBytes(totalSize);
    els.metaNextFitPtr.textContent = `@${snap.next_fit_ptr}`;
    els.metaNextId.textContent = `#${snap.next_id}`;

    // 1. Posicionar marcador do Next Fit
    const ptrPct = Math.max(0, Math.min(100, (snap.next_fit_ptr / totalSize) * 100));
    els.nextFitMarker.style.left = `${ptrPct}%`;
    els.nextFitLine.style.left = `${ptrPct}%`;
    els.nextFitLabel.textContent = `Next Fit @${snap.next_fit_ptr}`;
    els.nextFitMarker.classList.remove("align-left", "align-right");
    if (ptrPct <= 8) {
      els.nextFitMarker.classList.add("align-left");
    } else if (ptrPct >= 92) {
      els.nextFitMarker.classList.add("align-right");
    }

    // Identificar blocos afetados para destaque direto na barra
    const affectedIds = new Set();
    const coalescedStarts = new Set();
    const examinedFreeStarts = new Set();

    if (Array.isArray(event.affected_blocks)) {
      for (const blk of event.affected_blocks) {
        if (blk.coalesced) {
          coalescedStarts.add(blk.start);
        } else if (blk.id != null && (event.action === "alloc" || event.action === "defrag")) {
          affectedIds.add(blk.id);
        }
      }
    }

    if (event.action === "alloc" && event.error && Array.isArray(event.examined_holes)) {
      for (const h of event.examined_holes) {
        examinedFreeStarts.add(h.start);
      }
    }

    // 2. Renderizar blocos proporcionais na barra de memória
    els.memoryBar.innerHTML = "";
    for (const block of snap.blocks) {
      const widthPct = (block.size / totalSize) * 100;
      const div = document.createElement("div");
      div.className = "mem-block " + (block.free ? "is-free" : "is-allocated");
      div.style.width = `${widthPct}%`;

      if (widthPct < 10) div.classList.add("narrow");
      if (widthPct < 4) div.classList.add("very-narrow");

      if (!block.free) {
        div.style.backgroundColor = getBlockColor(block.id);
        if (affectedIds.has(block.id)) {
          div.classList.add("is-affected");
        }
      } else {
        if (coalescedStarts.has(block.start)) {
          div.classList.add("is-coalesced");
        } else if (examinedFreeStarts.has(block.start)) {
          div.classList.add("is-examined-free");
        }
      }

      const idText = block.free ? "Livre" : `ID #${block.id}`;
      const infoText = `@${block.start} +${block.size}B`;

      div.title = block.free
        ? `Buraco Livre | Início: @${block.start} | Fim: @${block.end} | Tamanho: ${block.size} B`
        : `Bloco ID #${block.id} | Início: @${block.start} | Fim: @${block.end} | Tamanho: ${block.size} B`;

      const spanId = document.createElement("span");
      spanId.className = "block-id";
      spanId.textContent = idText;

      const spanInfo = document.createElement("span");
      spanInfo.className = "block-info";
      spanInfo.textContent = infoText;

      div.appendChild(spanId);
      div.appendChild(spanInfo);
      els.memoryBar.appendChild(div);
    }

    // 3. Renderizar régua de endereços (início, fim e fronteiras sem sobreposição)
    renderAddressRuler(snap.blocks, totalSize);

    // 4. Renderizar faixa de destaque de busca / liberação / defrag
    renderActionOverlay(event, totalSize);
  }

  function renderAddressRuler(blocks, totalSize) {
    els.addressRuler.innerHTML = "";

    const rawTicks = new Set([0, totalSize]);
    for (const b of blocks) {
      rawTicks.add(b.start);
      rawTicks.add(b.end);
    }

    const sorted = Array.from(rawTicks).sort((a, b) => a - b);
    // Filtrar rótulos muito próximos (< 4.5% de distância) preservando sempre 0 e totalSize
    const filtered = [];
    for (const addr of sorted) {
      if (addr === 0 || addr === totalSize) {
        filtered.push(addr);
        continue;
      }
      const pct = (addr / totalSize) * 100;
      const lastPct = filtered.length > 0 ? (filtered[filtered.length - 1] / totalSize) * 100 : -100;
      const distToEnd = 100 - pct;
      if (pct - lastPct >= 4.5 && distToEnd >= 4.5) {
        filtered.push(addr);
      }
    }

    for (const addr of filtered) {
      const pct = (addr / totalSize) * 100;
      const tick = document.createElement("span");
      tick.className = "ruler-tick";
      if (addr === 0) tick.classList.add("tick-start");
      else if (addr === totalSize) tick.classList.add("tick-end");
      tick.style.left = `${pct}%`;
      tick.textContent = `@${addr}`;
      els.addressRuler.appendChild(tick);
    }
  }

  function renderActionOverlay(event, totalSize) {
    els.overlayTrack.innerHTML = "";
    const action = event.action;

    if (action === "alloc" && Array.isArray(event.examined_holes) && event.examined_holes.length > 0) {
      els.overlaySection.classList.remove("hidden");
      els.overlayTitle.textContent = "Busca de Buracos no alloc";
      els.overlaySubtitle.textContent = event.chosen_hole
        ? `${event.examined_holes.length} buraco(s) examinado(s) · escolhido @${event.chosen_hole.start} (+${event.chosen_hole.size}B)`
        : `${event.examined_holes.length} buraco(s) examinado(s) · nenhum comportou o pedido`;

      event.examined_holes.forEach((hole, idx) => {
        const isChosen =
          event.chosen_hole &&
          event.chosen_hole.start === hole.start &&
          event.chosen_hole.size === hole.size;

        const seg = document.createElement("div");
        seg.className = `overlay-seg ${isChosen ? "overlay-chosen" : "overlay-examined"}`;
        seg.style.left = `${(hole.start / totalSize) * 100}%`;
        seg.style.width = `${(hole.size / totalSize) * 100}%`;
        seg.textContent = isChosen
          ? `${idx + 1}º ✓ @${hole.start} (+${hole.size}B)`
          : `${idx + 1}º @${hole.start} (+${hole.size}B)`;
        seg.title = isChosen
          ? `Ordem ${idx + 1} — Buraco ESCOLHIDO: @${hole.start}..${hole.end} (${hole.size} B)`
          : `Ordem ${idx + 1} — Buraco examinado: @${hole.start}..${hole.end} (${hole.size} B)`;
        els.overlayTrack.appendChild(seg);
      });
      return;
    }

    if ((action === "freeid" || action === "freeaddr") && !event.error && Array.isArray(event.affected_blocks) && event.affected_blocks.length > 0) {
      els.overlaySection.classList.remove("hidden");
      const freed = event.affected_blocks.find((b) => !b.coalesced);
      const coalesced = event.affected_blocks.find((b) => b.coalesced);

      els.overlayTitle.textContent = coalesced
        ? "Liberação com Coalescência de Buracos Vizinhos"
        : "Bloco Liberado";
      els.overlaySubtitle.textContent = coalesced
        ? `Novo buraco fundido: @${coalesced.start}..${coalesced.end} (+${coalesced.size}B)`
        : freed
          ? `Liberado ID #${freed.id} em @${freed.start} (+${freed.size}B)`
          : "";

      if (coalesced) {
        const segCoal = document.createElement("div");
        segCoal.className = "overlay-seg overlay-coalesced";
        segCoal.style.left = `${(coalesced.start / totalSize) * 100}%`;
        segCoal.style.width = `${(coalesced.size / totalSize) * 100}%`;
        segCoal.textContent = `Coalescido @${coalesced.start} (+${coalesced.size}B)`;
        segCoal.title = `Buraco resultante da coalescência: @${coalesced.start}..${coalesced.end} (${coalesced.size} B)`;
        els.overlayTrack.appendChild(segCoal);
      }

      if (freed) {
        const segFreed = document.createElement("div");
        segFreed.className = "overlay-seg overlay-freed";
        segFreed.style.left = `${(freed.start / totalSize) * 100}%`;
        segFreed.style.width = `${(freed.size / totalSize) * 100}%`;
        segFreed.textContent = `Liberado #${freed.id}`;
        segFreed.title = `Bloco liberado ID #${freed.id}: @${freed.start}..${freed.end} (${freed.size} B)`;
        els.overlayTrack.appendChild(segFreed);
      }
      return;
    }

    if (action === "defrag" && !event.error) {
      els.overlaySection.classList.remove("hidden");
      const moved = Array.isArray(event.affected_blocks) ? event.affected_blocks : [];
      els.overlayTitle.textContent = "Compactação de Memória (defrag)";
      els.overlaySubtitle.textContent =
        `${event.moved_blocks_count || 0} bloco(s) movido(s) · ${event.displaced_bytes || 0} B deslocado(s)`;

      for (const blk of moved) {
        const newStart = blk.new_start != null ? blk.new_start : blk.start;
        if (newStart == null || !blk.size) continue;
        const seg = document.createElement("div");
        seg.className = "overlay-seg overlay-moved";
        seg.style.left = `${(newStart / totalSize) * 100}%`;
        seg.style.width = `${(blk.size / totalSize) * 100}%`;
        seg.textContent = `#${blk.id}: @${blk.old_start}→@${newStart}`;
        seg.title = `Bloco #${blk.id} deslocado de @${blk.old_start} para @${newStart} (${blk.size} B)`;
        els.overlayTrack.appendChild(seg);
      }
      return;
    }

    els.overlaySection.classList.add("hidden");
  }

  function renderStats() {
    const currentStep = state.currentIndex >= 0 ? state.steps[state.currentIndex] : null;
    if (!currentStep || !currentStep.snapshot || !currentStep.snapshot.stats) {
      els.statUsed.textContent = "—";
      els.statFree.textContent = "—";
      els.statHoles.textContent = "—";
      els.statLargestHole.textContent = "—";
      els.statUsage.textContent = "—";
      els.statUsageBar.style.width = "0%";
      return;
    }

    const st = currentStep.snapshot.stats;
    els.statUsed.textContent = formatBytes(st.used_bytes);
    els.statFree.textContent = formatBytes(st.free_bytes);
    els.statHoles.textContent = String(st.holes_count);
    els.statLargestHole.textContent = formatBytes(st.largest_hole);
    els.statUsage.textContent = `${Number(st.effective_usage).toFixed(2)}%`;
    els.statUsageBar.style.width = `${Math.max(0, Math.min(100, st.effective_usage))}%`;
  }

  function renderEventDetails() {
    const currentStep = state.currentIndex >= 0 ? state.steps[state.currentIndex] : null;
    if (!currentStep) {
      els.eventDetails.innerHTML = `<p class="muted">Nenhum passo executado ainda.</p>`;
      return;
    }

    const ev = currentStep.event || {};
    const rows = [];

    if (ev.error) {
      rows.push(
        `<div class="detail-row"><strong>Resultado:</strong> <span class="detail-chip chip-error">${escapeHtml(ev.error)}</span></div>`
      );
    }

    if (ev.action === "init") {
      rows.push(
        `<div class="detail-row">Memória inicializada com <strong>${currentStep.snapshot.total_size} B</strong> totalmente livres, <code>next_id = 1</code> e <code>next_fit_ptr = 0</code>.</div>`
      );
    }

    if (ev.action === "alloc") {
      if (Array.isArray(ev.examined_holes) && ev.examined_holes.length > 0) {
        const chips = ev.examined_holes
          .map((h, i) => {
            const isChosen =
              ev.chosen_hole && ev.chosen_hole.start === h.start && ev.chosen_hole.size === h.size;
            return `<span class="detail-chip ${isChosen ? "chip-chosen" : "chip-examined"}">${i + 1}º @${h.start} (+${h.size}B)${isChosen ? " ✓" : ""}</span>`;
          })
          .join(" ");
        rows.push(`<div class="detail-row"><strong>Buracos examinados:</strong> ${chips}</div>`);
      }

      if (ev.chosen_hole) {
        rows.push(
          `<div class="detail-row"><strong>Buraco escolhido:</strong> <span class="detail-chip chip-chosen">@${ev.chosen_hole.start}..${ev.chosen_hole.end} (+${ev.chosen_hole.size}B)</span></div>`
        );
      }

      if (Array.isArray(ev.affected_blocks) && ev.affected_blocks.length > 0) {
        const b = ev.affected_blocks[0];
        rows.push(
          `<div class="detail-row"><strong>Bloco alocado:</strong> <span class="detail-chip">ID #${b.id} em @${b.start}..${b.end} (+${b.size}B)</span></div>`
        );
      }
    }

    if ((ev.action === "freeid" || ev.action === "freeaddr") && !ev.error) {
      const freed = (ev.affected_blocks || []).find((b) => !b.coalesced);
      const coalesced = (ev.affected_blocks || []).find((b) => b.coalesced);

      if (freed) {
        rows.push(
          `<div class="detail-row"><strong>Bloco liberado:</strong> <span class="detail-chip">ID #${freed.id} em @${freed.start}..${freed.end} (+${freed.size}B)</span></div>`
        );
      }
      if (coalesced) {
        rows.push(
          `<div class="detail-row"><strong>Coalescência:</strong> <span class="detail-chip chip-coalesced">Sim — fundido em @${coalesced.start}..${coalesced.end} (+${coalesced.size}B)</span></div>`
        );
      } else {
        rows.push(
          `<div class="detail-row"><strong>Coalescência:</strong> <span class="muted">Não houve buracos vizinhos livres para fundir.</span></div>`
        );
      }
    }

    if (ev.action === "defrag" && !ev.error) {
      rows.push(
        `<div class="detail-row"><strong>Resumo:</strong> <span class="detail-chip chip-moved">${ev.moved_blocks_count || 0} bloco(s) movido(s)</span> <span class="detail-chip chip-moved">${ev.displaced_bytes || 0} B deslocado(s)</span> <span class="detail-chip">next_fit_ptr resetado para @0</span></div>`
      );
      if (Array.isArray(ev.affected_blocks) && ev.affected_blocks.length > 0) {
        const movedChips = ev.affected_blocks
          .map(
            (b) =>
              `<span class="detail-chip chip-moved">#${b.id}: @${b.old_start} → @${b.new_start} (+${b.size}B)</span>`
          )
          .join(" ");
        rows.push(`<div class="detail-row"><strong>Deslocamentos:</strong> ${movedChips}</div>`);
      } else {
        rows.push(`<div class="detail-row muted">Nenhum bloco precisou ser deslocado.</div>`);
      }
    }

    els.eventDetails.innerHTML = rows.join("") || `<p class="muted">Sem detalhes adicionais para este passo.</p>`;
  }

  function renderSegmentsTable() {
    const currentStep = state.currentIndex >= 0 ? state.steps[state.currentIndex] : null;
    if (!currentStep || !currentStep.snapshot || !Array.isArray(currentStep.snapshot.blocks)) {
      els.segmentsTableBody.innerHTML =
        `<tr><td colspan="5" class="muted center-cell">Sem dados para exibir.</td></tr>`;
      return;
    }

    const html = currentStep.snapshot.blocks
      .map((b) => {
        const dotColor = b.free ? "#cbd5e1" : getBlockColor(b.id);
        const typeLabel = b.free ? "Buraco" : "Alocado";
        const idLabel = b.free ? "—" : `#${b.id}`;
        return `
          <tr>
            <td><span class="seg-dot" style="background:${dotColor};"></span>${typeLabel}</td>
            <td>${idLabel}</td>
            <td>@${b.start}</td>
            <td>@${b.end}</td>
            <td>+${b.size} B</td>
          </tr>
        `;
      })
      .join("");

    els.segmentsTableBody.innerHTML = html;
  }

  function renderTimeline() {
    const total = state.steps.length;
    els.timelineCount.textContent = `${total} ${total === 1 ? "passo" : "passos"}`;

    if (total === 0) {
      els.stepsTimeline.innerHTML =
        `<li class="timeline-empty muted">Carregue um arquivo <code>.cmd</code> ou <code>.txt</code> para ver os comandos válidos.</li>`;
      return;
    }

    els.stepsTimeline.innerHTML = "";
    state.steps.forEach((step, idx) => {
      const li = document.createElement("li");
      li.className = "timeline-item";
      if (idx < state.currentIndex) li.classList.add("is-done");
      if (idx === state.currentIndex) li.classList.add("is-current");
      if (step.event && step.event.error) li.classList.add("has-error");

      const left = document.createElement("div");
      left.className = "timeline-left";

      const num = document.createElement("span");
      num.className = "timeline-num";
      num.textContent = `${idx + 1}.`;

      const cmd = document.createElement("span");
      cmd.className = "timeline-cmd";
      cmd.textContent = step.command;

      left.appendChild(num);
      left.appendChild(cmd);
      li.appendChild(left);

      if (step.event && step.event.error) {
        const tag = document.createElement("span");
        tag.className = "timeline-tag tag-err";
        tag.textContent = "ERRO";
        li.appendChild(tag);
      } else if (idx <= state.currentIndex) {
        const tag = document.createElement("span");
        tag.className = "timeline-tag tag-ok";
        tag.textContent = "OK";
        li.appendChild(tag);
      }

      li.addEventListener("click", () => jumpToStep(idx));
      els.stepsTimeline.appendChild(li);

      if (idx === state.currentIndex) {
        li.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // --- Eventos de Interface ---

  els.fileInput.addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const text = await file.text();
    await loadScriptText(text, file.name);
    // Permite recarregar o mesmo arquivo novamente se o usuário editá-lo
    els.fileInput.value = "";
  });

  els.btnLoadSample.addEventListener("click", loadSampleTrace);
  els.btnNext.addEventListener("click", stepNextManual);
  els.btnPrev.addEventListener("click", stepPrevManual);
  els.btnPlay.addEventListener("click", startPlayback);
  els.btnPause.addEventListener("click", pausePlayback);
  els.btnReset.addEventListener("click", resetSimulation);

  els.intervalInput.addEventListener("change", () => {
    getIntervalMs();
    if (state.isPlaying) {
      startPlayback();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (document.activeElement === els.intervalInput) return;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      stepNextManual();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      stepPrevManual();
    } else if (e.key === " ") {
      if (state.steps.length === 0) return;
      e.preventDefault();
      if (state.isPlaying) pausePlayback();
      else startPlayback();
    } else if (e.key === "r" || e.key === "R") {
      if (state.steps.length === 0) return;
      e.preventDefault();
      resetSimulation();
    }
  });

  // Render inicial
  render();
})();
