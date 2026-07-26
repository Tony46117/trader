/* ── Trading Signals Dashboard — Main Application ───────────── */

const API_BASE = '';
let refreshInterval = null;
let charts = {};

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

function timeSince(dateStr) {
    if (!dateStr || dateStr === '—') return '—';
    return dateStr;
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

// ── API Calls ────────────────────────────────────────────────────────

async function apiFetch(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        const data = await res.json();
        return data;
    } catch (err) {
        console.error(`API error [${endpoint}]:`, err);
        return { status: 'error', message: err.message };
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
        card.className = `pair-card ${cls}-highlight`;

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
    if (countEl) countEl.textContent = `${setups.length} active setups`;

    if (setups.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-8 text-gray-600">
                <svg class="w-10 h-10 mb-2 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span class="text-sm">No active setups above threshold</span>
                <span class="text-xs mt-1">Waiting for clearer signals</span>
            </div>`;
        return;
    }

    container.innerHTML = setups.map((s, i) => {
        const cls = signalClass(s.direction);
        return `
            <div class="flex items-center justify-between p-3 rounded-lg bg-dark-800/50 border border-dark-700/30 fade-in" style="animation-delay: ${i * 50}ms">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full ${cls === 'buy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'} flex items-center justify-center text-xs font-bold">
                        ${s.direction === 'BUY' ? 'B' : 'S'}
                    </div>
                    <div>
                        <div class="text-sm font-semibold text-white">${s.pair_name || s.pair}</div>
                        <div class="text-[10px] text-gray-500">${s.verdict ? s.verdict.substring(0, 60) + '...' : ''}</div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-sm font-bold font-mono ${cls === 'buy' ? 'text-green-400' : 'text-red-400'}">${s.score}</div>
                    <div class="text-[10px] text-gray-500">${s.confidence} · ${s.timing}</div>
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

        const dir = signalClass(unified.direction);
        const price = sig.current_price;

        return `
            <tr class="border-b border-dark-700/20 hover:bg-dark-800/30 transition-colors fade-in">
                <td class="py-2.5 px-2">
                    <span class="font-semibold text-white">${pair.slice(0, 3)}/<span class="text-gray-400">${pair.slice(3)}</span></span>
                    <div class="text-[9px] text-gray-600">${sig.type || ''}</div>
                </td>
                <td class="text-right py-2.5 px-2 font-mono text-sm text-gray-200">${formatPrice(price, pair)}</td>
                <td class="text-center py-2.5 px-2">
                    <div class="text-xs font-mono ${tech.score >= 60 ? 'text-green-400' : tech.score <= 40 ? 'text-red-400' : 'text-gray-400'}">${tech.score || 50}</div>
                    ${components ? `<div class="w-full h-1 bg-dark-700 rounded mt-1"><div class="component-bar ${tech.score >= 60 ? 'buy' : tech.score <= 40 ? 'sell' : 'neutral'}" style="width:${tech.score || 50}%"></div></div>` : ''}
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
                <td class="text-center py-2.5 px-2">
                    <span class="text-[9px] px-1.5 py-0.5 rounded ${sig.timing === 'IMMEDIATE' ? 'bg-green-500/20 text-green-400' : sig.timing === 'SOON' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}">${sig.timing || 'WAIT'}</span>
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
        container.innerHTML = `
            <div class="text-center py-4 text-gray-600 text-xs">
                No upcoming events in the next 48 hours
            </div>`;
        return;
    }

    container.innerHTML = events.map((e, i) => {
        const isHigh = e.impact && (e.impact.toLowerCase().includes('high') || e.impact.toLowerCase().includes('red'));
        const impactClass = isHigh ? 'impact-high' : 'impact-medium';
        return `
            <div class="p-2.5 rounded-lg ${impactClass} mb-1.5 fade-in" style="animation-delay: ${i * 80}ms">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-semibold ${isHigh ? 'text-red-400' : 'text-orange-400'}">${e.currency || ''}</span>
                    <span class="text-[9px] text-gray-500">${e.datetime ? e.datetime.split(' ')[1] : ''}</span>
                </div>
                <div class="text-xs text-gray-300 mt-0.5">${e.event || ''}</div>
                <div class="flex items-center gap-2 mt-1 text-[9px] text-gray-500">
                    <span>F: ${e.forecast || '—'}</span>
                    <span>P: ${e.previous || '—'}</span>
                    ${signalBadge(e.direction, e.direction)}
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
    const bgColor = r.regime_color === 'green' ? 'bg-green-500/10 border-green-500/30' : r.regime_color === 'red' ? 'bg-red-500/10 border-red-500/30' : 'bg-yellow-500/10 border-yellow-500/30';

    container.innerHTML = `
        <div class="p-3 rounded-lg ${bgColor} border">
            <div class="flex items-center justify-between">
                <span class="text-xs font-semibold ${regimeColor}">${r.regime || 'NEUTRAL'}</span>
                <span class="text-[10px] text-gray-500">VIX: ${r.vix?.toFixed(1) || '—'}</span>
            </div>
            <div class="flex justify-between mt-2 text-[10px] text-gray-500">
                <span>DXY: ${r.dxy_value?.toFixed(2) || '—'}</span>
                <span>Yield: ${r.yield_spread?.toFixed(3) || '—'}</span>
            </div>
        </div>
        ${(r.signals || []).slice(0, 2).map(s => `
            <div class="flex items-start gap-2 text-xs text-gray-400 p-2 rounded-lg bg-dark-800/30">
                <span class="text-[9px] px-1.5 py-0.5 rounded ${s.severity === 'high' || s.severity === 'extreme' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}">${s.type}</span>
                <span>${s.message}</span>
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
        <div class="flex items-center justify-between p-2 rounded-lg bg-dark-800/30">
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
        container.innerHTML = `<div class="text-center py-8 text-red-400">Error: ${result.message}</div>`;
        return;
    }

    if (selected === 'all') {
        // Show all pairs as expandable cards
        const data = result.data;
        container.innerHTML = Object.keys(data).map(pair => buildSignalCard(pair, data[pair])).join('');
        // Update S/R quick ref
        updateSRQuickRef(null);
    } else {
        const data = result.data;
        container.innerHTML = buildSignalCard(selected, data);
        updateSRQuickRef(data);
    }

    // Update summary
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

    return `
        <div class="bg-dark-800/40 border border-dark-700/30 rounded-lg p-4 mb-3 fade-in signal-card" data-pair="${pair}">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl ${dir === 'buy' ? 'bg-green-500/20' : dir === 'sell' ? 'bg-red-500/20' : 'bg-gray-500/20'} flex items-center justify-center">
                        <span class="text-lg font-bold ${dir === 'buy' ? 'text-green-400' : dir === 'sell' ? 'text-red-400' : 'text-gray-400'}">${unified.direction === 'BUY' ? '↑' : unified.direction === 'SELL' ? '↓' : '→'}</span>
                    </div>
                    <div>
                        <h4 class="text-sm font-bold text-white">${pair.slice(0, 3)}/<span class="text-gray-400">${pair.slice(3)}</span></h4>
                        <div class="flex items-center gap-2 mt-0.5">
                            ${signalBadge(unified.direction)}
                            <span class="text-[10px] ${conf === 'HIGH' ? 'text-green-400' : conf === 'MEDIUM' ? 'text-yellow-400' : 'text-gray-500'}">${conf}</span>
                            <span class="text-[10px] text-gray-600">${unified.agreement || ''}</span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-bold font-mono ${dir === 'buy' ? 'text-green-400' : dir === 'sell' ? 'text-red-400' : 'text-gray-400'}">${unified.score || 50}</div>
                    <div class="text-[9px] text-gray-600">Unified Score</div>
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
                            <div class="w-full h-1 bg-dark-700 rounded mt-1">
                                <div class="component-bar ${cDir}" style="width: ${c.score}%"></div>
                            </div>
                        </div>`;
                }).join('')}
            </div>

            <!-- Levels -->
            <div class="grid grid-cols-4 gap-3 p-3 rounded-lg bg-dark-900/50">
                <div>
                    <div class="text-[9px] text-gray-600">Entry</div>
                    <div class="text-xs font-mono text-yellow-400 font-semibold">${formatPrice(sig.entry_price, pair)}</div>
                </div>
                <div>
                    <div class="text-[9px] text-gray-600">Stop Loss</div>
                    <div class="text-xs font-mono text-red-400 font-semibold">${formatPrice(sig.stop_loss, pair)}</div>
                </div>
                <div>
                    <div class="text-[9px] text-gray-600">TP1</div>
                    <div class="text-xs font-mono text-green-400 font-semibold">${formatPrice(sig.take_profit_1, pair)}</div>
                </div>
                <div>
                    <div class="text-[9px] text-gray-600">R:R</div>
                    <div class="text-xs font-mono text-gray-300 font-semibold">1:${sig.risk_reward_1?.toFixed(1) || '—'}</div>
                </div>
            </div>

            <!-- CME Levels -->
            ${sig.cme_levels ? `
            <div class="flex gap-3 mt-2 text-[10px] text-gray-500">
                <span>Max Pain: <span class="font-mono text-gray-400">${formatPrice(sig.cme_levels.max_pain, pair)}</span></span>
                <span>R1: <span class="font-mono text-red-400">${formatPrice(sig.cme_levels.primary_resistance, pair)}</span></span>
                <span>S1: <span class="font-mono text-green-400">${formatPrice(sig.cme_levels.primary_support, pair)}</span></span>
            </div>` : ''}

            <!-- Verdict -->
            <div class="mt-2 text-xs text-gray-500 italic">${unified.verdict || ''}</div>
        </div>`;
}

function updateSRQuickRef(signalData) {
    const container = document.getElementById('sr-quick-ref');
    if (!container) return;

    if (!signalData || !signalData.support_levels || !signalData.resistance_levels) {
        container.innerHTML = `
            <h3 class="text-sm font-semibold text-white mb-3">S/R Levels</h3>
            <div class="text-xs text-gray-500 text-center py-4">
                Select a signal to view support & resistance
            </div>`;
        return;
    }

    container.innerHTML = `
        <h3 class="text-sm font-semibold text-white mb-3">S/R Levels</h3>
        <div class="space-y-2">
            <div class="p-2 rounded-lg bg-red-500/5 border border-red-500/20">
                <div class="text-[9px] text-red-400 mb-1">RESISTANCE</div>
                ${(signalData.resistance_levels || []).map(l => `<div class="text-xs font-mono text-gray-300">${formatPrice(l, null)}</div>`).join('')}
            </div>
            <div class="p-2 rounded-lg bg-green-500/5 border border-green-500/20">
                <div class="text-[9px] text-green-400 mb-1">SUPPORT</div>
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
    let buyCount = 0, sellCount = 0, neutralCount = 0;

    Object.values(data).forEach(item => {
        if (item.direction === 'BUY') buyCount++;
        else if (item.direction === 'SELL') sellCount++;
        else neutralCount++;
    });

    container.innerHTML = `
        <div class="p-3 rounded-lg bg-dark-800/30">
            <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-gray-400">Signal Distribution</span>
                <span class="text-[10px] text-gray-600">${buyCount + sellCount + neutralCount} pairs</span>
            </div>
            <div class="flex gap-2">
                <div class="flex-1 p-2 rounded bg-green-500/10 text-center">
                    <div class="text-sm font-bold text-green-400">${buyCount}</div>
                    <div class="text-[9px] text-green-500/70">BUY</div>
                </div>
                <div class="flex-1 p-2 rounded bg-red-500/10 text-center">
                    <div class="text-sm font-bold text-red-400">${sellCount}</div>
                    <div class="text-[9px] text-red-500/70">SELL</div>
                </div>
                <div class="flex-1 p-2 rounded bg-gray-500/10 text-center">
                    <div class="text-sm font-bold text-gray-400">${neutralCount}</div>
                    <div class="text-[9px] text-gray-500/70">HOLD</div>
                </div>
            </div>
        </div>
        <div class="p-3 rounded-lg bg-dark-800/30 mt-2">
            <div class="text-xs text-gray-500 mb-1">Top Pick</div>
            ${buyCount > sellCount
                ? '<span class="text-xs text-green-400">Bullish bias — ' + buyCount + ' buy signals vs ' + sellCount + ' sell</span>'
                : '<span class="text-xs text-red-400">Bearish bias — ' + sellCount + ' sell signals vs ' + buyCount + ' buy</span>'
            }
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
    if (selectedCurrency !== 'all') {
        filtered = filtered.filter(e => e.currency === selectedCurrency);
    }
    if (selectedImpact !== 'all') {
        filtered = filtered.filter(e => e.impact && e.impact.toLowerCase().includes(selectedImpact.toLowerCase()));
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-12 text-gray-600">
                <svg class="w-12 h-12 mb-3 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                                <span class="text-[10px] font-semibold ${isHigh ? 'text-red-400' : 'text-orange-400'}">${e.currency || ''}</span>
                                <span class="text-[9px] text-gray-500">${e.datetime || ''}</span>
                                <span class="text-[9px] text-gray-600">${e.impact || ''}</span>
                            </div>
                            <div class="text-sm text-gray-200 truncate">${e.event || ''}</div>
                            <div class="flex items-center gap-3 mt-0.5 text-[10px] text-gray-500">
                                ${e.forecast ? `<span>Fcast: ${e.forecast}</span>` : ''}
                                ${e.previous ? `<span>Prev: ${e.previous}</span>` : ''}
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
            <div class="flex items-center justify-between p-2.5 rounded-lg bg-dark-800/30">
                <div class="flex items-center gap-2">
                    <span class="w-6 h-4 rounded ${currency === 'USD' ? 'bg-blue-600' : currency === 'EUR' ? 'bg-orange-600' : 'bg-green-600'} text-center text-[9px] leading-4 font-bold text-white">${currency}</span>
                    <span class="text-xs text-gray-400">${stats.total || 0} events</span>
                </div>
                <div class="flex gap-2 text-[10px]">
                    <span class="text-red-400">${stats.high || 0}H</span>
                    <span class="text-orange-400">${stats.medium || 0}M</span>
                    <span class="text-blue-400">${stats.upcoming_24h || 0} upcoming</span>
                </div>
            </div>`;
    }).join('');
}

// ── Analysis Page Functions ──────────────────────────────────────────

async function refreshAnalysis() {
    // Cross-asset analysis
    const crossResult = await apiFetch('/api/analysis/cross-asset');
    if (crossResult.status === 'ok' && crossResult.data) {
        const d = crossResult.data;
        updateElement('dxy-analysis', buildDXYAnalysis(d.dxy));
        updateElement('vix-analysis', buildVIXAnalysis(d.vix));
        updateElement('yield-analysis', buildYieldAnalysis(d.yields));
        updateElement('correlation-matrix', buildCorrelationMatrix(d.correlations));
    }

    // Regime
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
    if (!dxy) return '<div class="text-gray-600">No DXY data available</div>';
    const trend = dxy.trend === 'bullish' ? '↑' : '↓';
    const trendColor = dxy.trend === 'bullish' ? 'text-green-400' : 'text-red-400';
    return `
        <div class="flex items-center justify-between">
            <div>
                <span class="text-2xl font-bold font-mono text-white">${dxy.value?.toFixed(2) || '—'}</span>
                <span class="ml-2 ${trendColor}">${trend} ${dxy.change?.toFixed(2) || '0'}%</span>
            </div>
            <div class="text-right">
                <div class="text-xs text-gray-500">Range</div>
                <div class="text-xs font-mono text-gray-400">H: ${dxy.high?.toFixed(2) || '—'} L: ${dxy.low?.toFixed(2) || '—'}</div>
                <div class="text-[9px] ${dxy.strength === 'very_strong' ? 'text-red-400' : dxy.strength === 'strong' ? 'text-orange-400' : 'text-gray-500'}">${dxy.strength || ''}</div>
            </div>
        </div>
        <div class="mt-2 text-xs text-gray-500">DXY ${dxy.trend || 'neutral'} — ${dxy.strength || ''}</div>`;
}

function buildVIXAnalysis(vix) {
    if (!vix) return '<div class="text-gray-600">No VIX data available</div>';
    const riskLabel = vix.risk_on ? 'Risk-On' : 'Risk-Off';
    const riskColor = vix.risk_on ? 'text-green-400' : 'text-red-400';
    return `
        <div class="flex items-center justify-between">
            <div>
                <span class="text-2xl font-bold font-mono text-white">${vix.value?.toFixed(1) || '—'}</span>
                <span class="ml-2 text-sm ${vix.change >= 0 ? 'text-red-400' : 'text-green-400'}">${vix.change >= 0 ? '+' : ''}${vix.change?.toFixed(2) || '0'}%</span>
            </div>
            <div class="text-right">
                <div class="text-xs ${riskColor} font-semibold">${riskLabel}</div>
                <div class="text-[9px] text-gray-500">${vix.regime || ''}</div>
            </div>
        </div>
        <div class="mt-2 flex gap-2 text-[10px]">
            <span class="${vix.value < 15 ? 'text-green-400' : vix.value < 20 ? 'text-yellow-400' : 'text-red-400'}">${vix.value < 12 ? 'Complacent' : vix.value < 20 ? 'Normal' : vix.value < 30 ? 'Fearful' : 'Extreme Fear'}</span>
        </div>`;
}

function buildYieldAnalysis(yields) {
    if (!yields) return '<div class="text-gray-600">No yield data available</div>';
    const status = yields.inverted ? '⚠️ INVERTED' : '✅ Normal';
    const statusColor = yields.inverted ? 'text-red-400' : 'text-green-400';
    return `
        <div class="grid grid-cols-2 gap-3">
            <div class="p-2 rounded bg-dark-800/30">
                <div class="text-[9px] text-gray-500">2Y Yield</div>
                <div class="text-sm font-mono text-gray-300">${yields['2y_yield']?.toFixed(3) || '—'}%</div>
            </div>
            <div class="p-2 rounded bg-dark-800/30">
                <div class="text-[9px] text-gray-500">10Y Yield</div>
                <div class="text-sm font-mono text-gray-300">${yields['10y_yield']?.toFixed(3) || '—'}%</div>
            </div>
            <div class="p-2 rounded bg-dark-800/30">
                <div class="text-[9px] text-gray-500">30Y Yield</div>
                <div class="text-sm font-mono text-gray-300">${yields['30y_yield']?.toFixed(3) || '—'}%</div>
            </div>
            <div class="p-2 rounded bg-dark-800/30">
                <div class="text-[9px] text-gray-500">2-10 Spread</div>
                <div class="text-sm font-mono ${statusColor}">${yields.spread_2_10?.toFixed(3) || '—'}%</div>
            </div>
        </div>
        <div class="mt-2 text-xs ${statusColor} font-semibold">${status}</div>
        ${yields.inverted ? '<div class="mt-1 text-[10px] text-red-400/70">Yield curve inversion historically precedes recessions — defensive positioning advised.</div>' : ''}`;
}

function buildCorrelationMatrix(correlations) {
    if (!correlations || Object.keys(correlations).length === 0) {
        return '<div class="text-gray-600">Loading correlations...</div>';
    }
    return `
        <div class="overflow-x-auto">
            <table class="w-full text-xs">
                <thead>
                    <tr class="text-gray-500 border-b border-dark-700/30">
                        <th class="text-left py-2 px-2">Pair</th>
                        <th class="text-center py-2 px-2">DXY Corr</th>
                        <th class="text-center py-2 px-2">Relationship</th>
                        <th class="text-center py-2 px-2">Strength</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.keys(correlations).map(pair => {
                        const c = correlations[pair];
                        const corrColor = c.dxy_correlation < -0.5 ? 'text-red-400' : c.dxy_correlation > 0.5 ? 'text-green-400' : 'text-gray-400';
                        return `
                            <tr class="border-b border-dark-700/10">
                                <td class="py-2 px-2 text-gray-300">${pair.slice(0, 3)}/<span class="text-gray-500">${pair.slice(3)}</span></td>
                                <td class="text-center py-2 px-2 font-mono ${corrColor}">${c.dxy_correlation?.toFixed(2) || '—'}</td>
                                <td class="text-center py-2 px-2 text-gray-400">${c.relationship || '—'}</td>
                                <td class="text-center py-2 px-2">
                                    <span class="px-1.5 py-0.5 rounded ${c.strength === 'strong' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}">${c.strength || '—'}</span>
                                </td>
                            </tr>`;
                    }).join('')}
                </tbody>
            </table>
            <div class="text-[9px] text-gray-600 mt-2">DXY correlation: negative = inverse relationship (typical for USD pairs)</div>
        </div>`;
}

function buildRegimeBanner(regime) {
    const bgColors = { 'RISK-ON': 'bg-green-500/10 border-green-500/30', 'DEFENSIVE': 'bg-red-500/10 border-red-500/30', 'NEUTRAL': 'bg-yellow-500/10 border-yellow-500/30' };
    const textColors = { 'RISK-ON': 'text-green-400', 'DEFENSIVE': 'text-red-400', 'NEUTRAL': 'text-yellow-400' };
    const bg = bgColors[regime.regime] || bgColors['NEUTRAL'];
    const tc = textColors[regime.regime] || textColors['NEUTRAL'];
    return `
        <div class="p-4 rounded-lg ${bg} border">
            <div class="flex items-center justify-between">
                <div>
                    <div class="text-xs text-gray-500 mb-1">Current Market Regime</div>
                    <div class="text-xl font-bold ${tc}">${regime.regime || 'NEUTRAL'}</div>
                </div>
                <div class="text-right text-[10px] text-gray-500">
                    <div>VIX: ${regime.vix?.toFixed(1) || '—'}</div>
                    <div>DXY: ${regime.dxy_value?.toFixed(2) || '—'}</div>
                    <div>Spread: ${regime.yield_spread?.toFixed(3) || '—'}</div>
                </div>
            </div>
        </div>`;
}

function buildRegimeSignals(signals) {
    if (!signals || signals.length === 0) {
        return '<div class="text-xs text-gray-500 text-center py-4">No regime signals</div>';
    }
    return signals.map(s => `
        <div class="p-2.5 rounded-lg bg-dark-800/30 flex items-start gap-2">
            <span class="text-[9px] px-1.5 py-0.5 rounded flex-shrink-0 ${s.severity === 'high' || s.severity === 'extreme' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}">${s.type}</span>
            <span class="text-xs text-gray-400">${s.message}</span>
        </div>
    `).join('');
}

function buildBiasSummary(regime) {
    const rc = regime.regime === 'RISK-ON' ? 'text-green-400' : regime.regime === 'DEFENSIVE' ? 'text-red-400' : 'text-yellow-400';
    return `
        <div class="p-3 rounded-lg bg-dark-800/30">
            <div class="text-sm font-semibold ${rc}">${regime.regime || 'NEUTRAL'}</div>
            <div class="mt-2 space-y-1 text-xs text-gray-500">
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
    // Check which page we're on
    const path = window.location.pathname;

    if (path === '/' || path === '') {
        refreshAll();
        // Auto-refresh every 30 seconds
        refreshInterval = setInterval(refreshAll, 30000);
    }

    if (path === '/signals') {
        refreshSignals();
        refreshSignalSummary();
        refreshInterval = setInterval(refreshSignals, 30000);
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

    // Time tabs
    document.querySelectorAll('.time-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.time-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            refreshNews(parseInt(this.dataset.hours));
        });
    });
});
