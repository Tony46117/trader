/* ── Trading Signals Dashboard — Main Application ───────────── */

const API_BASE = '';
let refreshInterval = null;

// ── Utilities ────────────────────────────────────────────────────────

function formatPrice(num, pair) {
    if (num === null || num === undefined || num === 0) return '—';
    const decimals = pair && (pair.includes('BTC') || pair.includes('ETH') || pair.includes('XAU')) ? 2 : 5;
    return num.toFixed(decimals);
}

function formatChange(val) {
    if (val === null || val === undefined) return '0.00%';
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(2)}%`;
}

function signalClass(signal) {
    if (!signal) return 'neutral';
    const s = signal.toUpperCase();
    if (s === 'BUY' || s === 'BULLISH' || s === 'STRONG_BUY') return 'buy';
    if (s === 'SELL' || s === 'BEARISH' || s === 'STRONG_SELL') return 'sell';
    return 'neutral';
}

function signalBadge(signal, text) {
    const cls = signalClass(signal);
    const label = text || signal || 'NEUTRAL';
    return `<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold badge-${cls}">${label}</span>`;
}

function formatTimestamp() {
    return new Date().toLocaleTimeString('en-US', { hour12: false });
}

function rrBadge(rr) {
    if (rr === null || rr === undefined) return '<span class="text-[9px]" style="color: var(--text-muted)">—</span>';
    const rrNum = parseFloat(rr);
    if (rrNum < 2.0) return `<span class="text-[9px] px-1.5 py-0.5" style="background: rgba(239, 68, 68, 0.08); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.15); font-family: JetBrains Mono, monospace; font-weight: 600;">1:${rrNum.toFixed(1)} LOW</span>`;
    if (rrNum >= 4.0) return `<span class="text-[9px] px-1.5 py-0.5" style="background: rgba(16, 185, 129, 0.08); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.15); font-family: JetBrains Mono, monospace; font-weight: 600;">1:${rrNum.toFixed(1)}</span>`;
    return `<span class="text-[9px] px-1.5 py-0.5" style="background: rgba(37, 99, 235, 0.08); color: var(--accent-blue-light); border: 1px solid rgba(37, 99, 235, 0.15); font-family: JetBrains Mono, monospace; font-weight: 600;">1:${rrNum.toFixed(1)}</span>`;
}

// ── API Calls ────────────────────────────────────────────────────────

async function apiFetch(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        return await res.json();
    } catch (err) {
        console.error(`API error [${endpoint}]:`, err);
        return { status: 'error', message: err.message };
    }
}

async function closeSignal(pair) {
    try {
        await fetch(`${API_BASE}/api/signals/close/${pair}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reason: 'MANUAL_CLOSE'}) });
        refreshAll();
    } catch (err) {
        console.error('Close signal error:', err);
    }
}

// ── Dashboard Functions ────────────────────────────────────────────

async function refreshMarketOverview() {
    const result = await apiFetch('/api/market/overview');
    if (result.status !== 'ok' || !result.data) return;

    const data = result.data;
    Object.keys(data).forEach(pair => {
        const card = document.getElementById(`card-${pair}`);
        if (!card) return;

        const item = data[pair];
        const cls = signalClass(item.direction);
        const isValid = item.setup_valid;
        const sigState = item.signal_state || {};
        const isActive = sigState.status === 'ACTIVE';

        card.className = `pair-card ${cls}-highlight` + (isValid ? ' setup-valid' : '') + (isActive ? ' signal-active' : '');

        const priceEl = card.querySelector('.pair-price');
        if (priceEl) priceEl.textContent = formatPrice(item.price, pair);

        const changeEl = card.querySelector('.pair-change');
        if (changeEl) {
            changeEl.textContent = formatChange(item.change);
            changeEl.className = `text-[11px] font-mono pair-change ${item.change >= 0 ? 'text-green-400' : 'text-red-400'}`;
        }

        const dirEl = card.querySelector('.pair-direction');
        if (dirEl) dirEl.innerHTML = signalBadge(item.direction);

        const slEl = card.querySelector('.pair-sl');
        if (slEl) slEl.textContent = formatPrice(item.sl, pair);

        const tpEl = card.querySelector('.pair-tp');
        if (tpEl) tpEl.textContent = formatPrice(item.tp1, pair);

        const rrEl = card.querySelector('.pair-rr');
        if (rrEl) rrEl.innerHTML = rrBadge(item.rr1);

        // Signal state indicator
        const stateEl = card.querySelector('.pair-signal-state');
        if (stateEl) {
            if (isActive) {
                stateEl.innerHTML = '<div class="flex items-center gap-1"><div class="w-1.5 h-1.5" style="background: var(--accent-blue);"></div><span class="text-[9px] font-semibold" style="color: var(--accent-blue-light);">ACTIVE</span></div>';
            } else if (sigState.status?.startsWith('HIT_TP')) {
                stateEl.innerHTML = `<span class="text-[9px] font-semibold" style="color: var(--accent-green);">TP HIT</span>`;
            } else if (sigState.status === 'HIT_SL') {
                stateEl.innerHTML = `<span class="text-[9px] font-semibold" style="color: var(--accent-red);">SL HIT</span>`;
            } else {
                stateEl.innerHTML = '';
            }
        }

        if (!isValid) {
            const invalidBadge = card.querySelector('.invalid-badge');
            if (invalidBadge) invalidBadge.style.display = 'flex';
        } else {
            const invalidBadge = card.querySelector('.invalid-badge');
            if (invalidBadge) invalidBadge.style.display = 'none';
        }
    });

    updateLastUpdate();
}

async function refreshSetups() {
    const result = await apiFetch('/api/signals/setups?min_score=55&max=5');
    if (result.status !== 'ok' || !result.data) return;

    const container = document.getElementById('setups-container');
    const countEl = document.getElementById('setup-count');
    if (!container) return;

    const setups = result.data;
    if (countEl) countEl.textContent = `${setups.length} active`;

    if (setups.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-8 text-gray-600">
                <svg class="w-8 h-8 mb-2 text-gray-700 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span class="text-sm">No active setups</span>
                <span class="text-xs mt-1">Waiting for clearer signals</span>
            </div>`;
        return;
    }

    container.innerHTML = setups.map((s, i) => {
        const cls = signalClass(s.direction);
        const isValid = s.setup_valid !== false;
        const isActive = s.is_active_signal;
        const sigState = s.signal_state || {};
        const statusLabel = sigState.status === 'ACTIVE' ? 'ACTIVE SIGNAL' : 
                           sigState.status === 'HIT_TP1' ? 'TP1 HIT' :
                           sigState.status === 'HIT_TP2' ? 'TP2 HIT' :
                           sigState.status === 'HIT_TP3' ? 'TP3 HIT' :
                           sigState.status === 'HIT_SL' ? 'STOPPED OUT' : '';
        const stateClass = sigState.status === 'ACTIVE' ? 'signal-active' :
                          sigState.status?.startsWith('HIT_TP') ? 'signal-hit-tp' :
                          sigState.status === 'HIT_SL' ? 'signal-hit-sl' : '';

        return `
            <div class="setup-card setup-card-${cls} fade-in ${stateClass}" style="animation-delay: ${i * 50}ms">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-9 h-9 flex items-center justify-center text-sm font-bold ${cls === 'buy' ? 'signal-buy-icon' : 'signal-sell-icon'}" style="background: ${cls === 'buy' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'}; color: ${cls === 'buy' ? 'var(--accent-green)' : 'var(--accent-red)'};">
                            ${s.direction === 'BUY' ? '↑' : '↓'}
                        </div>
                        <div>
                            <div class="text-sm font-bold" style="color: var(--text-primary);">${s.pair_name || s.pair}</div>
                            <div class="text-[10px] max-w-[200px] truncate" style="color: var(--text-muted);">${s.verdict ? s.verdict.substring(0, 55) : ''}</div>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-base font-bold font-mono ${cls === 'buy' ? 'text-green-400' : 'text-red-400'}">${s.score}</div>
                        <div class="flex items-center gap-1.5 justify-end mt-0.5">
                            ${signalBadge(s.direction)}
                            <span class="text-[9px]" style="color: var(--text-muted);">${s.timing}</span>
                        </div>
                    </div>
                </div>
                ${isActive ? `
                <div class="flex items-center justify-between mt-2 pt-2" style="border-top: 1px solid var(--border-color);">
                    <div class="flex items-center gap-2">
                        <div class="w-1.5 h-1.5" style="background: var(--accent-blue);"></div>
                        <span class="text-[10px] font-semibold" style="color: var(--accent-blue-light);">ACTIVE SIGNAL</span>
                    </div>
                    <button onclick="closeSignal('${s.pair}')" class="text-[9px] px-2 py-1 transition-all" style="background: rgba(239, 68, 68, 0.08); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.15);">Close</button>
                </div>` : ''}
                ${statusLabel && !isActive ? `
                <div class="flex items-center mt-2 pt-2" style="border-top: 1px solid var(--border-color);">
                    <span class="text-[10px] font-semibold ${sigState.status?.startsWith('HIT_TP') ? 'text-green-400' : sigState.status === 'HIT_SL' ? 'text-red-400' : ''}" style="color: ${sigState.status?.startsWith('HIT_TP') ? 'var(--accent-green)' : sigState.status === 'HIT_SL' ? 'var(--accent-red)' : 'var(--text-muted)'};">${statusLabel}${sigState.pips_result ? ` (${sigState.pips_result > 0 ? '+' : ''}${sigState.pips_result} pips)` : ''}</span>
                </div>` : ''}
                <div class="flex items-center justify-between mt-2 pt-2" style="border-top: 1px solid var(--border-color);">
                    <div class="text-[9px]" style="color: var(--text-muted);">${s.confidence} confidence</div>
                    <div class="flex items-center gap-1">
                        <span class="text-[9px]" style="color: var(--text-muted);">R:R</span>
                        ${rrBadge(s.risk_reward_1)}
                    </div>
                </div>
            </div>`;
    }).join('');
}

async function refreshSignalMatrix() {
    const result = await apiFetch('/api/signals/unified');
    if (result.status !== 'ok' || !result.data) return;

    const tbody = document.getElementById('unified-signal-body');
    if (!tbody) return;

    const data = result.data;
    tbody.innerHTML = Object.keys(data).map(pair => {
        const sig = data[pair];
        const unified = sig.unified || {};
        const tech = sig.technical_signal || {};
        const news = sig.news_signal || {};
        const components = unified.components || {};
        const isValid = sig.setup_valid !== false;

        return `
            <tr class="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors fade-in">
                <td class="py-2.5 px-2">
                    <div class="flex items-center gap-2">
                        <span class="font-semibold text-white">${pair.slice(0, 3)}/<span class="text-gray-400">${pair.slice(3)}</span></span>
                        ${!isValid ? '<span class="text-[8px] px-1 py-0.5 rounded bg-red-500/10 text-red-400 font-bold">NO SETUP</span>' : ''}
                    </div>
                    <div class="text-[9px] text-gray-600">${sig.type || ''}</div>
                </td>
                <td class="text-right py-2.5 px-2 font-mono text-sm text-gray-200">${formatPrice(sig.current_price, pair)}</td>
                <td class="text-center py-2.5 px-2">
                    <div class="text-xs font-mono ${tech.score >= 60 ? 'text-green-400' : tech.score <= 40 ? 'text-red-400' : 'text-gray-400'}">${tech.score || 50}</div>
                </td>
                <td class="text-center py-2.5 px-2">${signalBadge(tech.direction)}</td>
                <td class="text-center py-2.5 px-2">
                    <div class="text-xs font-mono ${news.score >= 60 ? 'text-orange-400' : news.score <= 40 ? 'text-orange-400' : 'text-gray-400'}">${news.score || 50}</div>
                </td>
                <td class="text-center py-2.5 px-2">${signalBadge(news.direction)}</td>
                <td class="text-center py-2.5 px-2">
                    <div class="flex items-center justify-center gap-1.5">
                        ${signalBadge(unified.direction)}
                        <span class="text-[9px] ${unified.confidence === 'HIGH' ? 'text-green-400' : unified.confidence === 'MEDIUM' ? 'text-yellow-400' : 'text-gray-500'}">${unified.confidence || ''}</span>
                    </div>
                </td>
                <td class="text-right py-2.5 px-2 font-mono text-xs text-yellow-400">${formatPrice(sig.entry_price, pair)}</td>
                <td class="text-right py-2.5 px-2 font-mono text-xs text-red-400">${formatPrice(sig.stop_loss, pair)}</td>
                <td class="text-right py-2.5 px-2 font-mono text-xs text-green-400">${formatPrice(sig.take_profit_1, pair)}</td>
                <td class="text-center py-2.5 px-2">${rrBadge(sig.risk_reward_1)}</td>
                <td class="text-center py-2.5 px-2">
                    <span class="text-[9px] px-1.5 py-0.5 rounded ${sig.timing === 'IMMEDIATE' ? 'bg-green-500/10 text-green-400' : sig.timing === 'SOON' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-gray-500/10 text-gray-400'}">${sig.timing || 'WAIT'}</span>
                </td>
            </tr>`;
    }).join('');
}

async function refreshNewsPreview() {
    const result = await apiFetch('/api/news/upcoming?hours=48');
    if (result.status !== 'ok' || !result.data) return;

    const container = document.getElementById('news-preview');
    if (!container) return;

    const events = result.data.slice(0, 5);
    if (events.length === 0) {
        container.innerHTML = `<div class="text-center py-4 text-gray-600 text-xs">No upcoming events in 48H</div>`;
        return;
    }

    container.innerHTML = events.map((e, i) => {
        const isHigh = e.impact && (e.impact.toLowerCase().includes('high') || e.impact.toLowerCase().includes('red'));
        return `
            <div class="p-2.5 rounded-lg ${isHigh ? 'impact-high' : 'impact-medium'} mb-1.5 fade-in" style="animation-delay: ${i * 80}ms">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-bold ${isHigh ? 'text-red-400' : 'text-orange-400'}">${e.currency || ''}</span>
                    <span class="text-[9px] text-gray-500 font-mono">${e.datetime ? e.datetime.split(' ')[1] : ''}</span>
                </div>
                <div class="text-xs text-gray-300 mt-0.5 truncate">${e.event || ''}</div>
                <div class="flex items-center gap-2 mt-1 text-[9px] text-gray-500">
                    <span>F: ${e.forecast || '—'}</span>
                    <span>P: ${e.previous || '—'}</span>
                </div>
            </div>`;
    }).join('');
}

async function refreshRegime() {
    const result = await apiFetch('/api/analysis/regime');
    if (result.status !== 'ok' || !result.data) return;

    const container = document.getElementById('regime-content');
    if (!container) return;

    const r = result.data;
    const regimeColor = r.regime_color === 'green' ? 'text-green-400' : r.regime_color === 'red' ? 'text-red-400' : 'text-yellow-400';
    const bgColor = r.regime_color === 'green' ? 'bg-green-500/5 border-green-500/20' : r.regime_color === 'red' ? 'bg-red-500/5 border-red-500/20' : 'bg-yellow-500/5 border-yellow-500/20';

    container.innerHTML = `
        <div class="p-3 rounded-lg ${bgColor} border">
            <div class="flex items-center justify-between">
                <span class="text-xs font-bold ${regimeColor}">${r.regime || 'NEUTRAL'}</span>
                <span class="text-[10px] text-gray-500 font-mono">VIX ${r.vix?.toFixed(1) || '—'}</span>
            </div>
            <div class="flex justify-between mt-2 text-[10px] text-gray-500">
                <span>DXY ${r.dxy_value?.toFixed(2) || '—'}</span>
                <span>Spread ${r.yield_spread?.toFixed(3) || '—'}</span>
            </div>
        </div>
        ${(r.signals || []).slice(0, 2).map(s => `
            <div class="flex items-start gap-2 text-xs text-gray-400 p-2 rounded-lg bg-white/[0.02] mt-1.5">
                <span class="text-[9px] px-1.5 py-0.5 rounded flex-shrink-0 ${s.severity === 'high' || s.severity === 'extreme' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}">${s.type}</span>
                <span class="text-[10px]">${s.message}</span>
            </div>
        `).join('')}
    `;
}

async function refreshCrossAsset() {
    const result = await apiFetch('/api/analysis/cross-asset');
    if (result.status !== 'ok' || !result.data) return;

    const container = document.getElementById('cross-asset-snapshot');
    if (!container) return;

    const d = result.data;
    const items = [
        { label: 'DXY', value: d.dxy?.value, change: d.dxy?.change, color: d.dxy?.change >= 0 ? 'text-green-400' : 'text-red-400' },
        { label: 'VIX', value: d.vix?.value, change: d.vix?.change, color: d.vix?.change >= 0 ? 'text-red-400' : 'text-green-400' },
        { label: '10Y', value: d.yields?.['10y_yield'], change: null, color: 'text-blue-400' },
        { label: '2/10', value: d.yields?.spread_2_10, change: null, color: d.yields?.spread_2_10 < 0 ? 'text-red-400' : 'text-green-400' },
    ];

    container.innerHTML = items.map(item => `
        <div class="flex items-center justify-between p-2 rounded-lg bg-white/[0.02]">
            <span class="text-xs text-gray-500">${item.label}</span>
            <div class="text-right">
                <span class="text-xs font-mono font-semibold ${item.color}">${item.value?.toFixed(2) || '—'}</span>
                ${item.change !== null ? `<span class="text-[9px] ml-1 ${item.color}">${item.change >= 0 ? '+' : ''}${item.change.toFixed(2)}%</span>` : ''}
            </div>
        </div>
    `).join('');
}

// ── Signals Page Functions ──────────────────────────────────────────

async function refreshSignals() {
    const filter = document.getElementById('pair-filter');
    const selected = filter ? filter.value : 'all';
    const container = document.getElementById('signal-detail-container');
    if (!container) return;

    const result = selected === 'all'
        ? await apiFetch('/api/signals/unified')
        : await apiFetch(`/api/signals/unified/${selected}`);

    if (result.status !== 'ok') {
        container.innerHTML = `<div class="text-center py-8 text-red-400 text-sm">Error: ${result.message}</div>`;
        return;
    }

    if (selected === 'all') {
        const data = result.data;
        container.innerHTML = Object.keys(data).map(pair => buildSignalCard(pair, data[pair])).join('');
        updateSRQuickRef(null);
    } else {
        container.innerHTML = buildSignalCard(selected, result.data);
        updateSRQuickRef(result.data);
    }

    await refreshSignalSummary();
}

function buildSignalCard(pair, sig) {
    const unified = sig.unified || {};
    const tech = sig.technical_signal || {};
    const news = sig.news_signal || {};
    const tick = sig.tick_signal || {};
    const cme = sig.cme_signal || {};
    const social = sig.social_signal || {};
    const components = unified.components || {};
    const dir = signalClass(unified.direction);
    const conf = unified.confidence || 'LOW';
    const isValid = sig.setup_valid !== false;

    return `
        <div class="section-card mb-3 fade-in signal-card" data-pair="${pair}" style="opacity: ${isValid ? '1' : '0.55'}">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl ${dir === 'buy' ? 'bg-green-500/15' : dir === 'sell' ? 'bg-red-500/15' : 'bg-white/5'} flex items-center justify-center">
                        <span class="text-lg font-bold ${dir === 'buy' ? 'text-green-400' : dir === 'sell' ? 'text-red-400' : 'text-gray-400'}">${unified.direction === 'BUY' ? '↑' : unified.direction === 'SELL' ? '↓' : '→'}</span>
                    </div>
                    <div>
                        <h4 class="text-sm font-bold text-white">${pair.slice(0, 3)}/<span class="text-gray-400">${pair.slice(3)}</span></h4>
                        <div class="flex items-center gap-2 mt-0.5">
                            ${signalBadge(unified.direction)}
                            <span class="text-[10px] ${conf === 'HIGH' ? 'text-green-400' : conf === 'MEDIUM' ? 'text-yellow-400' : 'text-gray-500'}">${conf}</span>
                            ${!isValid ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 font-bold">NO SETUP</span>' : ''}
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-xl font-bold font-mono ${dir === 'buy' ? 'text-green-400' : dir === 'sell' ? 'text-red-400' : 'text-gray-400'}">${unified.score || 50}</div>
                    <div class="text-[9px] text-gray-600">Unified</div>
                </div>
            </div>

            <!-- Component Breakdown -->
            <div class="grid grid-cols-5 gap-2 mb-3">
                ${[
                    { label: 'Tech', score: components.technical || tech.score || 50 },
                    { label: 'News', score: components.news || news.score || 50 },
                    { label: 'Tick', score: components.tick || tick.score || 50 },
                    { label: 'CME', score: components.cme || cme.score || 50 },
                    { label: 'Social', score: components.social || social.score || 50 },
                ].map(c => {
                    const cDir = c.score >= 60 ? 'buy' : c.score <= 40 ? 'sell' : 'neutral';
                    return `
                        <div class="text-center">
                            <div class="text-[9px] text-gray-500 mb-1">${c.label}</div>
                            <div class="text-xs font-mono font-semibold ${cDir === 'buy' ? 'text-green-400' : cDir === 'sell' ? 'text-red-400' : 'text-gray-400'}">${Math.round(c.score)}</div>
                            <div class="w-full h-1 bg-white/5 rounded mt-1">
                                <div class="component-bar ${cDir}" style="width: ${c.score}%"></div>
                            </div>
                        </div>`;
                }).join('')}
            </div>

            <!-- Entry/SL/TP/R:R -->
            <div class="grid grid-cols-4 gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                <div>
                    <div class="text-[9px] text-gray-600 mb-0.5">Entry</div>
                    <div class="text-xs font-mono text-yellow-400 font-bold">${formatPrice(sig.entry_price, pair)}</div>
                </div>
                <div>
                    <div class="text-[9px] text-gray-600 mb-0.5">Stop Loss</div>
                    <div class="text-xs font-mono text-red-400 font-bold">${formatPrice(sig.stop_loss, pair)}</div>
                </div>
                <div>
                    <div class="text-[9px] text-gray-600 mb-0.5">TP1</div>
                    <div class="text-xs font-mono text-green-400 font-bold">${formatPrice(sig.take_profit_1, pair)}</div>
                </div>
                <div>
                    <div class="text-[9px] text-gray-600 mb-0.5">R:R</div>
                    ${rrBadge(sig.risk_reward_1)}
                </div>
            </div>

            <!-- CME Levels -->
            ${sig.cme_levels ? `
            <div class="flex gap-3 mt-2 text-[10px] text-gray-500">
                <span>Max Pain: <span class="font-mono text-gray-400">${formatPrice(sig.cme_levels.max_pain, pair)}</span></span>
                <span>R1: <span class="font-mono text-red-400">${formatPrice(sig.cme_levels.primary_resistance, pair)}</span></span>
                <span>S1: <span class="font-mono text-green-400">${formatPrice(sig.cme_levels.primary_support, pair)}</span></span>
            </div>` : ''}

            <div class="mt-2 text-[11px] text-gray-500 italic">${unified.verdict || ''}</div>
        </div>`;
}

function updateSRQuickRef(signalData) {
    const container = document.getElementById('sr-quick-ref');
    if (!container) return;

    if (!signalData || !signalData.support_levels || !signalData.resistance_levels) {
        container.innerHTML = `
            <h3 class="text-sm font-bold text-white mb-3">S/R Levels</h3>
            <div class="text-xs text-gray-500 text-center py-4">Select a signal to view levels</div>`;
        return;
    }

    container.innerHTML = `
        <h3 class="text-sm font-bold text-white mb-3">S/R Levels</h3>
        <div class="space-y-2">
            <div class="p-2 rounded-lg bg-red-500/5 border border-red-500/15">
                <div class="text-[9px] text-red-400 mb-1 font-semibold">RESISTANCE</div>
                ${(signalData.resistance_levels || []).map(l => `<div class="text-xs font-mono text-gray-300">${formatPrice(l, null)}</div>`).join('')}
            </div>
            <div class="p-2 rounded-lg bg-green-500/5 border border-green-500/15">
                <div class="text-[9px] text-green-400 mb-1 font-semibold">SUPPORT</div>
                ${(signalData.support_levels || []).map(l => `<div class="text-xs font-mono text-gray-300">${formatPrice(l, null)}</div>`).join('')}
            </div>
        </div>`;
}

async function refreshSignalSummary() {
    const container = document.getElementById('signal-summary');
    if (!container) return;

    const result = await apiFetch('/api/market/overview');
    if (result.status !== 'ok' || !result.data) return;

    const data = result.data;
    let buyCount = 0, sellCount = 0, neutralCount = 0, validCount = 0;

    Object.values(data).forEach(item => {
        if (item.direction === 'BUY') buyCount++;
        else if (item.direction === 'SELL') sellCount++;
        else neutralCount++;
        if (item.setup_valid) validCount++;
    });

    const total = buyCount + sellCount + neutralCount;
    const buyPct = total ? Math.round((buyCount / total) * 100) : 0;
    const sellPct = total ? Math.round((sellCount / total) * 100) : 0;

    container.innerHTML = `
        <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
            <div class="flex items-center justify-between mb-2">
                <span class="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">Distribution</span>
                <span class="text-[10px] text-gray-600">${total} pairs</span>
            </div>
            <div class="flex gap-1.5 h-1.5 rounded-full overflow-hidden mb-3">
                <div class="bg-green-500 rounded-full" style="width: ${buyPct}%"></div>
                <div class="bg-red-500 rounded-full" style="width: ${sellPct}%"></div>
                <div class="bg-gray-500 rounded-full flex-1"></div>
            </div>
            <div class="flex gap-2">
                <div class="flex-1 p-2 rounded-lg bg-green-500/5 text-center">
                    <div class="text-sm font-bold text-green-400">${buyCount}</div>
                    <div class="text-[9px] text-green-500/70">BUY</div>
                </div>
                <div class="flex-1 p-2 rounded-lg bg-red-500/5 text-center">
                    <div class="text-sm font-bold text-red-400">${sellCount}</div>
                    <div class="text-[9px] text-red-500/70">SELL</div>
                </div>
                <div class="flex-1 p-2 rounded-lg bg-white/[0.02] text-center">
                    <div class="text-sm font-bold text-gray-400">${neutralCount}</div>
                    <div class="text-[9px] text-gray-500">HOLD</div>
                </div>
            </div>
        </div>
        <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] mt-2">
            <div class="flex items-center justify-between">
                <span class="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">Valid Setups</span>
                <span class="text-[10px] font-mono ${validCount > 0 ? 'text-green-400' : 'text-gray-500'}">${validCount}/${total}</span>
            </div>
            <div class="mt-1.5 text-[10px] ${buyCount > sellCount ? 'text-green-400' : 'text-red-400'}">
                ${buyCount > sellCount ? 'Bullish bias' : sellCount > buyCount ? 'Bearish bias' : 'Neutral'}
                — ${buyCount} buy vs ${sellCount} sell
            </div>
        </div>`;
}

// ── News Page Functions ──────────────────────────────────────────────

async function refreshNews(hours) {
    hours = hours || 72;
    const result = await apiFetch(`/api/news/upcoming?hours=${hours}`);
    if (result.status !== 'ok' || !result.data) return;

    const container = document.getElementById('news-container');
    if (!container) return;

    const events = result.data;
    const currencyFilter = document.getElementById('currency-filter');
    const impactFilter = document.getElementById('impact-filter');
    const selectedCurrency = currencyFilter ? currencyFilter.value : 'all';
    const selectedImpact = impactFilter ? impactFilter.value : 'all';

    let filtered = events;
    if (selectedCurrency !== 'all') filtered = filtered.filter(e => e.currency === selectedCurrency);
    if (selectedImpact !== 'all') filtered = filtered.filter(e => e.impact && e.impact.toLowerCase().includes(selectedImpact.toLowerCase()));

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-12 text-gray-600">
                <svg class="w-8 h-8 mb-2 text-gray-700 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/>
                </svg>
                <span class="text-sm">No events matching filters</span>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="space-y-1">
            ${filtered.map((e, i) => {
                const isHigh = e.impact && (e.impact.toLowerCase().includes('high') || e.impact.toLowerCase().includes('red'));
                const isLive = e.status === 'live';
                return `
                    <div class="flex items-center p-3 rounded-lg ${isHigh ? 'impact-high' : 'impact-medium'} fade-in" style="animation-delay: ${i * 30}ms">
                        ${isLive ? '<span class="w-2 h-2 rounded-full bg-red-500 animate-pulse mr-2 flex-shrink-0"></span>' : ''}
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] font-bold ${isHigh ? 'text-red-400' : 'text-orange-400'}">${e.currency || ''}</span>
                                <span class="text-[9px] text-gray-500 font-mono">${e.datetime || ''}</span>
                                <span class="text-[9px] text-gray-600">${e.impact || ''}</span>
                            </div>
                            <div class="text-sm text-gray-200 truncate">${e.event || ''}</div>
                            <div class="flex items-center gap-3 mt-0.5 text-[10px] text-gray-500">
                                ${e.forecast ? `<span>F: ${e.forecast}</span>` : ''}
                                ${e.previous ? `<span>P: ${e.previous}</span>` : ''}
                                ${signalBadge(e.direction, e.direction)}
                            </div>
                        </div>
                    </div>`;
            }).join('')}
        </div>`;
}

async function refreshNewsStats() {
    const result = await apiFetch('/api/news/summary');
    if (result.status !== 'ok' || !result.data) return;

    const container = document.getElementById('news-stats');
    if (!container) return;

    container.innerHTML = Object.keys(result.data).map(currency => {
        const stats = result.data[currency];
        return `
            <div class="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02]">
                <div class="flex items-center gap-2">
                    <span class="w-6 h-4 rounded ${currency === 'USD' ? 'bg-blue-600' : currency === 'EUR' ? 'bg-orange-600' : 'bg-green-600'} text-center text-[9px] leading-4 font-bold text-white">${currency}</span>
                    <span class="text-xs text-gray-400">${stats.total || 0} events</span>
                </div>
                <div class="flex gap-2 text-[10px]">
                    <span class="text-red-400">${stats.high || 0}H</span>
                    <span class="text-orange-400">${stats.medium || 0}M</span>
                    <span class="text-blue-400">${stats.upcoming_24h || 0} soon</span>
                </div>
            </div>`;
    }).join('');
}

// ── Analysis Page Functions ──────────────────────────────────────────

async function refreshAnalysis() {
    const crossResult = await apiFetch('/api/analysis/cross-asset');
    if (crossResult.status === 'ok' && crossResult.data) {
        const d = crossResult.data;
        updateElement('dxy-analysis', buildDXYAnalysis(d.dxy));
        updateElement('vix-analysis', buildVIXAnalysis(d.vix));
        updateElement('yield-analysis', buildYieldAnalysis(d.yields));
        updateElement('correlation-matrix', buildCorrelationMatrix(d.correlations));
    }

    const regimeResult = await apiFetch('/api/analysis/regime');
    if (regimeResult.status === 'ok' && regimeResult.data) {
        updateElement('regime-banner', buildRegimeBanner(regimeResult.data));
        updateElement('regime-signals', buildRegimeSignals(regimeResult.data.signals));
        updateElement('bias-summary', buildBiasSummary(regimeResult.data));
    }
}

function updateElement(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
}

function buildDXYAnalysis(dxy) {
    if (!dxy) return '<div class="text-gray-600 text-xs">No DXY data</div>';
    const trend = dxy.trend === 'bullish' ? '↑' : '↓';
    const trendColor = dxy.trend === 'bullish' ? 'text-green-400' : 'text-red-400';
    return `
        <div class="flex items-center justify-between">
            <div>
                <span class="text-2xl font-bold font-mono text-white">${dxy.value?.toFixed(2) || '—'}</span>
                <span class="ml-2 ${trendColor} text-sm">${trend} ${dxy.change?.toFixed(2) || '0'}%</span>
            </div>
            <div class="text-right">
                <div class="text-[10px] text-gray-500">Range</div>
                <div class="text-[10px] font-mono text-gray-400">H: ${dxy.high?.toFixed(2) || '—'} L: ${dxy.low?.toFixed(2) || '—'}</div>
            </div>
        </div>
        <div class="mt-2 text-xs text-gray-500">DXY ${dxy.trend || 'neutral'} — ${dxy.strength || ''}</div>`;
}

function buildVIXAnalysis(vix) {
    if (!vix) return '<div class="text-gray-600 text-xs">No VIX data</div>';
    const riskColor = vix.risk_on ? 'text-green-400' : 'text-red-400';
    return `
        <div class="flex items-center justify-between">
            <div>
                <span class="text-2xl font-bold font-mono text-white">${vix.value?.toFixed(1) || '—'}</span>
                <span class="ml-2 text-sm ${vix.change >= 0 ? 'text-red-400' : 'text-green-400'}">${vix.change >= 0 ? '+' : ''}${vix.change?.toFixed(2) || '0'}%</span>
            </div>
            <div class="text-right">
                <div class="text-xs ${riskColor} font-semibold">${vix.risk_on ? 'Risk-On' : 'Risk-Off'}</div>
                <div class="text-[9px] text-gray-500">${vix.regime || ''}</div>
            </div>
        </div>`;
}

function buildYieldAnalysis(yields) {
    if (!yields) return '<div class="text-gray-600 text-xs">No yield data</div>';
    const statusColor = yields.inverted ? 'text-red-400' : 'text-green-400';
    return `
        <div class="grid grid-cols-2 gap-2">
            <div class="p-2 rounded-lg bg-white/[0.02]">
                <div class="text-[9px] text-gray-500">2Y</div>
                <div class="text-sm font-mono text-gray-300">${yields['2y_yield']?.toFixed(3) || '—'}%</div>
            </div>
            <div class="p-2 rounded-lg bg-white/[0.02]">
                <div class="text-[9px] text-gray-500">10Y</div>
                <div class="text-sm font-mono text-gray-300">${yields['10y_yield']?.toFixed(3) || '—'}%</div>
            </div>
            <div class="p-2 rounded-lg bg-white/[0.02]">
                <div class="text-[9px] text-gray-500">30Y</div>
                <div class="text-sm font-mono text-gray-300">${yields['30y_yield']?.toFixed(3) || '—'}%</div>
            </div>
            <div class="p-2 rounded-lg bg-white/[0.02]">
                <div class="text-[9px] text-gray-500">2-10</div>
                <div class="text-sm font-mono ${statusColor}">${yields.spread_2_10?.toFixed(3) || '—'}%</div>
            </div>
        </div>
        <div class="mt-2 text-xs ${statusColor} font-semibold">${yields.inverted ? 'Yield curve INVERTED' : 'Normal curve'}</div>`;
}

function buildCorrelationMatrix(correlations) {
    if (!correlations || Object.keys(correlations).length === 0) {
        return '<div class="text-gray-600 text-xs">Loading correlations...</div>';
    }
    return `
        <table class="w-full text-xs">
            <thead>
                <tr class="text-gray-500 border-b border-white/[0.04]">
                    <th class="text-left py-2 px-2">Pair</th>
                    <th class="text-center py-2 px-2">DXY</th>
                    <th class="text-center py-2 px-2">Relationship</th>
                    <th class="text-center py-2 px-2">Strength</th>
                </tr>
            </thead>
            <tbody>
                ${Object.keys(correlations).map(pair => {
                    const c = correlations[pair];
                    const corrColor = c.dxy_correlation < -0.5 ? 'text-red-400' : c.dxy_correlation > 0.5 ? 'text-green-400' : 'text-gray-400';
                    return `
                        <tr class="border-b border-white/[0.03]">
                            <td class="py-2 px-2 text-gray-300">${pair.slice(0, 3)}/<span class="text-gray-500">${pair.slice(3)}</span></td>
                            <td class="text-center py-2 px-2 font-mono ${corrColor}">${c.dxy_correlation?.toFixed(2) || '—'}</td>
                            <td class="text-center py-2 px-2 text-gray-400">${c.relationship || '—'}</td>
                            <td class="text-center py-2 px-2">
                                <span class="px-1.5 py-0.5 rounded ${c.strength === 'strong' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-white/[0.03] text-gray-400'}">${c.strength || '—'}</span>
                            </td>
                        </tr>`;
                }).join('')}
            </tbody>
        </table>`;
}

function buildRegimeBanner(regime) {
    const bgColors = { 'RISK-ON': 'bg-green-500/5 border-green-500/20', 'DEFENSIVE': 'bg-red-500/5 border-red-500/20', 'NEUTRAL': 'bg-yellow-500/5 border-yellow-500/20' };
    const textColors = { 'RISK-ON': 'text-green-400', 'DEFENSIVE': 'text-red-400', 'NEUTRAL': 'text-yellow-400' };
    const bg = bgColors[regime.regime] || bgColors['NEUTRAL'];
    const tc = textColors[regime.regime] || textColors['NEUTRAL'];
    return `
        <div class="p-4 rounded-xl ${bg} border">
            <div class="flex items-center justify-between">
                <div>
                    <div class="text-[10px] text-gray-500 mb-1 font-semibold uppercase tracking-wider">Market Regime</div>
                    <div class="text-xl font-bold ${tc}">${regime.regime || 'NEUTRAL'}</div>
                </div>
                <div class="text-right text-[10px] text-gray-500 font-mono">
                    <div>VIX ${regime.vix?.toFixed(1) || '—'}</div>
                    <div>DXY ${regime.dxy_value?.toFixed(2) || '—'}</div>
                    <div>Spread ${regime.yield_spread?.toFixed(3) || '—'}</div>
                </div>
            </div>
        </div>`;
}

function buildRegimeSignals(signals) {
    if (!signals || signals.length === 0) {
        return '<div class="text-xs text-gray-500 text-center py-4">No regime signals</div>';
    }
    return signals.map(s => `
        <div class="p-2.5 rounded-lg bg-white/[0.02] flex items-start gap-2">
            <span class="text-[9px] px-1.5 py-0.5 rounded flex-shrink-0 ${s.severity === 'high' || s.severity === 'extreme' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}">${s.type}</span>
            <span class="text-xs text-gray-400">${s.message}</span>
        </div>
    `).join('');
}

function buildBiasSummary(regime) {
    const rc = regime.regime === 'RISK-ON' ? 'text-green-400' : regime.regime === 'DEFENSIVE' ? 'text-red-400' : 'text-yellow-400';
    return `
        <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
            <div class="text-sm font-bold ${rc} mb-2">${regime.regime || 'NEUTRAL'}</div>
            <div class="space-y-1.5 text-xs text-gray-500">
                <div class="flex justify-between"><span>Volatility</span><span class="${regime.vix > 20 ? 'text-red-400' : 'text-green-400'}">${regime.vix > 20 ? 'Elevated' : 'Normal'}</span></div>
                <div class="flex justify-between"><span>Yield Curve</span><span class="${regime.yield_spread < 0 ? 'text-red-400' : 'text-green-400'}">${regime.yield_spread < 0 ? 'Inverted' : 'Normal'}</span></div>
                <div class="flex justify-between"><span>Risk Appetite</span><span class="${regime.vix < 15 ? 'text-green-400' : 'text-red-400'}">${regime.vix < 15 ? 'Risk-On' : 'Risk-Off'}</span></div>
            </div>
        </div>`;
}

// ── Refresh All ──────────────────────────────────────────────────────

async function refreshAll() {
    await Promise.all([
        refreshMarketOverview(),
        refreshSetups(),
        refreshSignalMatrix(),
        refreshNewsPreview(),
        refreshRegime(),
        refreshCrossAsset(),
    ]);
}

function updateLastUpdate() {
    const el = document.getElementById('last-update');
    if (el) el.textContent = formatTimestamp();
}

// ── Initialize ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;

    if (path === '/' || path === '') {
        refreshAll();
        refreshInterval = setInterval(refreshAll, 30000);
    }

    if (path === '/signals') {
        refreshSignals();
        refreshSignalSummary();
        refreshInterval = setInterval(() => { refreshSignals(); refreshSignalSummary(); }, 30000);
    }

    if (path === '/news') {
        refreshNews();
        refreshNewsStats();
        refreshInterval = setInterval(() => { refreshNews(); refreshNewsStats(); }, 30000);
    }

    if (path === '/analysis') {
        refreshAnalysis();
        refreshInterval = setInterval(refreshAnalysis, 60000);
    }

    // Bind filters
    const pairFilter = document.getElementById('pair-filter');
    if (pairFilter) pairFilter.addEventListener('change', refreshSignals);

    const currencyFilter = document.getElementById('currency-filter');
    if (currencyFilter) currencyFilter.addEventListener('change', () => {
        const hours = document.querySelector('.time-tab.active');
        refreshNews(hours ? parseInt(hours.dataset.hours) : 72);
    });

    const impactFilter = document.getElementById('impact-filter');
    if (impactFilter) impactFilter.addEventListener('change', () => {
        const hours = document.querySelector('.time-tab.active');
        refreshNews(hours ? parseInt(hours.dataset.hours) : 72);
    });

    document.querySelectorAll('.time-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.time-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            refreshNews(parseInt(this.dataset.hours));
        });
    });
});
