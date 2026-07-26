/**
 * Trading Signal Framework — Frontend Application
 * Handles all data fetching, rendering, and live updates.
 */

// ── Utility ──────────────────────────────────────────────────────

function formatPrice(price, pair = 'EURUSD') {
    if (!price || price === 0) return '—';
    const precision = pair.startsWith('BTC') || pair.startsWith('ETH') ? 2 : pair === 'XAUUSD' ? 2 : 5;
    return price.toFixed(precision);
}

function formatChange(change) {
    if (change === undefined || change === null) return '—';
    const prefix = change >= 0 ? '+' : '';
    return `${prefix}${change.toFixed(2)}%`;
}

function timeAgo(datetimeStr) {
    const now = new Date();
    const event = new Date(datetimeStr);
    const diffMs = event - now;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 0) return `${Math.abs(diffMins)}m ago`;
    if (diffMins < 60) return `in ${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `in ${diffHours}h`;
    const diffDays = Math.floor(diffHours / 24);
    return `in ${diffDays}d`;
}

function getDirectionClass(direction) {
    if (!direction) return 'badge-neutral';
    const dir = direction.toUpperCase();
    if (dir === 'BUY' || dir === 'BULLISH') return 'badge-buy';
    if (dir === 'SELL' || dir === 'BEARISH') return 'badge-sell';
    return 'badge-neutral';
}

function getDirectionText(direction) {
    if (!direction) return '—';
    const dir = direction.toUpperCase();
    if (dir === 'BUY' || dir === 'BULLISH') return 'BUY ↑';
    if (dir === 'SELL' || dir === 'BEARISH') return 'SELL ↓';
    if (dir === 'MIXED') return 'MIXED ⇅';
    return dir;
}

function strengthToWidth(strength) {
    return Math.min(100, (strength / 5) * 100);
}

// ── API Fetching ────────────────────────────────────────────────

async function fetchAPI(endpoint) {
    try {
        const res = await fetch(endpoint);
        const data = await res.json();
        return data;
    } catch (err) {
        console.error(`API Error [${endpoint}]:`, err);
        return { status: 'error', message: err.message };
    }
}

// ── Dashboard Page ──────────────────────────────────────────────

async function refreshAll() {
    updateTimestamp();
    await Promise.all([
        refreshMarketOverview(),
        refreshSetups(),
        refreshUnifiedMatrix(),
        refreshRegime(),
        refreshCrossAssetSnapshot(),
        refreshNewsPreview(),
    ]);
}

function updateTimestamp() {
    const el = document.getElementById('last-update');
    if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}

async function refreshMarketOverview() {
    const [priceData, unifiedData] = await Promise.all([
        fetchAPI('/api/prices'),
        fetchAPI('/api/market/overview'),
    ]);

    const prices = priceData.status === 'ok' ? priceData.data : {};
    const unified = unifiedData.status === 'ok' ? unifiedData.data : {};

    Object.entries(prices).forEach(([pair, info]) => {
        const card = document.getElementById(`card-${pair}`);
        if (!card) return;

        const priceEl = card.querySelector('.pair-price');
        const changeEl = card.querySelector('.pair-change');
        const directionEl = card.querySelector('.pair-direction');
        const slEl = card.querySelector('.pair-sl');
        const tpEl = card.querySelector('.pair-tp');

        if (priceEl) priceEl.textContent = formatPrice(info.bid, pair);
        if (changeEl) {
            changeEl.textContent = formatChange(info.change);
            changeEl.className = `text-[11px] font-mono pair-change ${info.change >= 0 ? 'text-green-400' : 'text-red-400'}`;
        }

        // Get direction from unified signal
        const sig = unified[pair] || {};
        if (directionEl) {
            directionEl.textContent = getDirectionText(sig.direction);
            directionEl.className = `text-[10px] font-semibold px-1.5 py-0.5 rounded pair-direction ${getDirectionClass(sig.direction)}`;
        }
        if (slEl) slEl.textContent = formatPrice(sig.sl, pair);
        if (tpEl) tpEl.textContent = formatPrice(sig.tp1, pair);
    });
}

async function refreshSetups() {
    const container = document.getElementById('setups-container');
    const countEl = document.getElementById('setup-count');
    if (!container) return;

    const data = await fetchAPI('/api/signals/setups?min_score=60&max=5');
    if (data.status !== 'ok') {
        container.innerHTML = `<div class="text-center py-8 text-gray-600">Failed to load signals</div>`;
        return;
    }

    const setups = data.data;
    if (countEl) countEl.textContent = `${setups.length} active setup${setups.length !== 1 ? 's' : ''}`;

    if (setups.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8">
                <div class="text-2xl mb-2">🔍</div>
                <div class="text-gray-500 text-sm">No high-quality setups detected</div>
                <div class="text-gray-600 text-xs mt-1">Waiting for stronger confluence signals</div>
            </div>`;
        return;
    }

    container.innerHTML = setups.map(setup => `
        <div class="p-3 rounded-lg ${getDirectionClass(setup.direction)} mb-2 fade-in">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <span class="font-semibold text-sm text-white">${setup.pair_name}</span>
                    <span class="text-[10px] text-gray-500 uppercase">${setup.type}</span>
                    <span class="text-xs font-mono font-bold ${setup.direction === 'BUY' ? 'text-green-400' : 'text-red-400'}">
                        ${getDirectionText(setup.direction)}
                    </span>
                </div>
                <div class="flex items-center gap-2">
                    <!-- Technical + News score badges -->
                    <div class="flex items-center gap-1 text-[9px]">
                        <span class="text-blue-400">T:</span>
                        <span class="font-mono ${setup.tech_score >= 60 ? 'text-green-400' : setup.tech_score <= 40 ? 'text-red-400' : 'text-gray-400'}">${setup.tech_score ?? '—'}</span>
                    </div>
                    <div class="flex items-center gap-1 text-[9px]">
                        <span class="text-yellow-400">N:</span>
                        <span class="font-mono ${setup.news_score >= 60 ? 'text-green-400' : setup.news_score <= 40 ? 'text-red-400' : 'text-gray-400'}">${setup.news_score ?? '—'}</span>
                    </div>
                    <span class="text-[10px] px-1.5 py-0.5 rounded ${
                        setup.confidence === 'HIGH' ? 'bg-green-500/15 text-green-400' :
                        setup.confidence === 'MEDIUM' ? 'bg-yellow-500/15 text-yellow-400' :
                        'bg-gray-500/15 text-gray-400'
                    }">${setup.confidence}</span>
                    <span class="text-[10px] px-1.5 py-0.5 rounded ${
                        setup.timing === 'IMMEDIATE' ? 'bg-yellow-500/15 text-yellow-400' :
                        setup.timing === 'SOON' ? 'bg-blue-500/15 text-blue-400' :
                        'bg-gray-500/15 text-gray-400'
                    }">${setup.timing}</span>
                </div>
            </div>
            <div class="mt-1.5 mb-2 text-[11px] text-gray-400 italic">${setup.verdict}</div>
            <div class="flex items-center gap-4 text-xs">
                <span class="text-gray-500">Price: <span class="text-gray-300 font-mono">${formatPrice(setup.current_price, setup.pair)}</span></span>
                <span class="text-gray-500">Entry: <span class="text-gray-300 font-mono">${formatPrice(setup.entry, setup.pair)}</span></span>
                <span class="text-red-400">SL: <span class="font-mono">${formatPrice(setup.sl, setup.pair)}</span></span>
                <span class="text-green-400">TP1: <span class="font-mono">${formatPrice(setup.tp1, setup.pair)}</span></span>
                <span class="text-green-300">TP2: <span class="font-mono">${formatPrice(setup.tp2, setup.pair)}</span></span>
                <span class="text-gray-500">R:R: <span class="font-mono">${setup.rr1 ?? '—'}</span></span>
            </div>
            <div class="mt-2">
                <div class="strength-bar">
                    <div class="strength-fill ${setup.direction === 'BUY' ? 'buy' : 'sell'}" style="width: ${setup.score}%"></div>
                </div>
                <div class="flex justify-between text-[9px] text-gray-600 mt-0.5">
                    <span>Unified Score: ${setup.score}/100</span>
                </div>
            </div>
        </div>
    `).join('');
}

// ── New Unified Signal Matrix ─────────────────────────────────

async function refreshUnifiedMatrix() {
    const tbody = document.getElementById('unified-signal-body');
    if (!tbody) return;

    const data = await fetchAPI('/api/signals/unified');
    if (data.status !== 'ok') {
        tbody.innerHTML = `<tr><td colspan="11" class="text-center py-8 text-gray-600">Failed to load unified signals</td></tr>`;
        return;
    }

    const signals = data.data;
    const pairs = Object.keys(signals);

    if (pairs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" class="text-center py-8 text-gray-600">No unified signal data available</td></tr>`;
        return;
    }

    tbody.innerHTML = pairs.map(pair => {
        const s = signals[pair];
        if (!s || s.error) {
            return `<tr class="border-b border-dark-700/30">
                <td class="py-2.5 px-2 font-medium text-gray-400">${pair}</td>
                <td colspan="10" class="py-2.5 px-2 text-center text-gray-600">Error: ${s?.error || 'No data'}</td>
            </tr>`;
        }

        const tech = s.technical_signal || {};
        const newsSig = s.news_signal || {};
        const unified = s.unified || {};

        const techScore = tech.score ?? 50;
        const techDir = tech.direction || 'NEUTRAL';
        const newsScore = newsSig.score ?? 50;
        const newsDir = newsSig.direction || 'NEUTRAL';
        const uniDir = unified.direction || 'NEUTRAL';

        return `<tr class="border-b border-dark-700/30 fade-in">
            <td class="py-2.5 px-2">
                <div class="flex items-center gap-2">
                    <span class="font-medium text-white">${pair}</span>
                    <span class="text-[9px] text-gray-600">${s.type || ''}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 text-right font-mono text-gray-300">${formatPrice(s.current_price, pair)}</td>

            <!-- Technical Score + Dir -->
            <td class="py-2.5 px-2 text-center">
                <div class="flex items-center justify-center gap-1">
                    <div class="strength-bar w-12">
                        <div class="strength-fill ${techDir === 'BUY' ? 'buy' : techDir === 'SELL' ? 'sell' : ''}" style="width: ${techScore}%"></div>
                    </div>
                    <span class="font-mono text-[10px] ${techScore >= 60 ? 'text-green-400' : techScore <= 40 ? 'text-red-400' : 'text-gray-400'}">${techScore}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 text-center">
                <span class="text-[9px] px-1.5 py-0.5 rounded font-semibold ${getDirectionClass(techDir)}">${getDirectionText(techDir)}</span>
            </td>

            <!-- News Score + Dir -->
            <td class="py-2.5 px-2 text-center">
                <div class="flex items-center justify-center gap-1">
                    <div class="strength-bar w-12">
                        <div class="strength-fill ${newsDir === 'BUY' ? 'buy' : newsDir === 'SELL' ? 'sell' : ''}" style="width: ${newsScore}%"></div>
                    </div>
                    <span class="font-mono text-[10px] ${newsScore >= 60 ? 'text-green-400' : newsScore <= 40 ? 'text-red-400' : 'text-gray-400'}">${newsScore}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 text-center">
                <span class="text-[9px] px-1.5 py-0.5 rounded font-semibold ${getDirectionClass(newsDir)}">${getDirectionText(newsDir)}</span>
            </td>

            <!-- Unified Verdict -->
            <td class="py-2.5 px-2 text-center">
                <div class="flex flex-col items-center gap-0.5">
                    <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold ${getDirectionClass(uniDir)}">${getDirectionText(uniDir)}</span>
                    <span class="text-[8px] ${unified.confidence === 'HIGH' ? 'text-green-500' : unified.confidence === 'MEDIUM' ? 'text-yellow-500' : 'text-gray-500'}">${unified.confidence || ''}</span>
                    <span class="text-[8px] text-gray-600">${unified.agreement || ''}</span>
                </div>
            </td>

            <td class="py-2.5 px-2 text-right font-mono text-gray-300">${formatPrice(s.entry_price, pair)}</td>
            <td class="py-2.5 px-2 text-right font-mono text-red-400">${formatPrice(s.stop_loss, pair)}</td>
            <td class="py-2.5 px-2 text-right font-mono text-green-400">${formatPrice(s.take_profit_1, pair)}</td>
            <td class="py-2.5 px-2 text-center">
                <span class="text-[10px] px-1.5 py-0.5 rounded ${
                    s.timing === 'IMMEDIATE' ? 'bg-yellow-500/15 text-yellow-400 font-semibold' :
                    s.timing === 'SOON' ? 'bg-blue-500/15 text-blue-400' :
                    'bg-gray-500/15 text-gray-500'
                }">${s.timing || '—'}</span>
            </td>
        </tr>`;
    }).join('');
}

async function refreshRegime() {
    const content = document.getElementById('regime-content');
    if (!content) return;

    const data = await fetchAPI('/api/analysis/regime');
    if (data.status !== 'ok') return;

    const regime = data.data;
    const colors = { 'RISK-ON': 'green', 'NEUTRAL': 'yellow', 'DEFENSIVE': 'red' };
    const color = colors[regime.regime] || 'gray';

    content.innerHTML = `
        <div class="text-center p-4 rounded-lg bg-dark-800/50 border border-${color}-500/20">
            <div class="text-2xl font-bold text-${color}-400 mb-1">${regime.regime}</div>
            <div class="text-[10px] text-gray-500">Current Market Regime</div>
        </div>
        <div class="grid grid-cols-3 gap-2 text-center">
            <div class="p-2 rounded-lg bg-dark-800/50">
                <div class="text-xs font-mono text-gray-300">${regime.vix ? regime.vix.toFixed(1) : '—'}</div>
                <div class="text-[9px] text-gray-600">VIX</div>
            </div>
            <div class="p-2 rounded-lg bg-dark-800/50">
                <div class="text-xs font-mono text-gray-300">${regime.dxy_value ? regime.dxy_value.toFixed(2) : '—'}</div>
                <div class="text-[9px] text-gray-600">DXY</div>
            </div>
            <div class="p-2 rounded-lg bg-dark-800/50">
                <div class="text-xs font-mono ${regime.yield_spread && regime.yield_spread < 0 ? 'text-red-400' : 'text-green-400'}">
                    ${regime.yield_spread ? regime.yield_spread.toFixed(2) : '—'}
                </div>
                <div class="text-[9px] text-gray-600">2Y-10Y</div>
            </div>
        </div>
        ${(regime.signals || []).slice(0, 2).map(s => `
            <div class="p-2 rounded-lg text-[10px] ${
                s.type === 'risk_off' ? 'bg-red-500/5 border-l-2 border-red-500' :
                s.type === 'risk_on' ? 'bg-green-500/5 border-l-2 border-green-500' :
                'bg-yellow-500/5 border-l-2 border-yellow-500'
            }">
                <span class="text-gray-400">${s.message}</span>
            </div>
        `).join('')}
    `;
}

async function refreshCrossAssetSnapshot() {
    const container = document.getElementById('cross-asset-snapshot');
    if (!container) return;

    const data = await fetchAPI('/api/analysis/cross-asset');
    if (data.status !== 'ok') return;

    const analysis = data.data;
    const items = [];

    if (analysis.dxy && analysis.dxy.value) {
        items.push({
            name: 'DXY',
            value: analysis.dxy.value.toFixed(2),
            change: analysis.dxy.change,
            trend: analysis.dxy.trend,
        });
    }
    if (analysis.vix && analysis.vix.value) {
        items.push({
            name: 'VIX',
            value: analysis.vix.value.toFixed(2),
            change: analysis.vix.change,
            regime: analysis.vix.regime,
        });
    }
    if (analysis.yields && analysis.yields['10y_yield']) {
        items.push({
            name: 'US10Y',
            value: `${analysis.yields['10y_yield'].toFixed(2)}%`,
            spread: analysis.yields.spread_2_10,
            inverted: analysis.yields.inverted,
        });
    }

    if (items.length === 0) {
        container.innerHTML = `<div class="text-center py-6 text-gray-600 text-xs">Cross-asset data loading...</div>`;
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="flex items-center justify-between p-2.5 rounded-lg bg-dark-800/30 text-xs">
            <span class="font-medium text-gray-300">${item.name}</span>
            <div class="text-right">
                <div class="font-mono text-gray-200">${item.value}</div>
                ${item.change !== undefined ? `
                    <div class="text-[10px] font-mono ${item.change >= 0 ? 'text-green-400' : 'text-red-400'}">
                        ${formatChange(item.change)}
                    </div>
                ` : ''}
                ${item.inverted !== undefined ? `
                    <div class="text-[10px] ${item.inverted ? 'text-red-400' : 'text-green-400'}">
                        ${item.inverted ? '⚠️ Inverted' : 'Normal'}
                    </div>
                ` : ''}
                ${item.regime ? `
                    <div class="text-[10px] text-gray-500">${item.regime}</div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

async function refreshNewsPreview() {
    const container = document.getElementById('news-preview');
    if (!container) return;

    const data = await fetchAPI('/api/news/upcoming?hours=48');
    if (data.status !== 'ok') return;

    const events = (data.data || []).slice(0, 4);

    if (events.length === 0) {
        container.innerHTML = `<div class="text-center py-6 text-gray-600 text-xs">No upcoming events in 48h</div>`;
        return;
    }

    container.innerHTML = events.map(event => `
        <div class="p-2.5 rounded-lg ${event.impact && event.impact.includes('High') ? 'impact-red' : 'impact-orange'} mb-2 text-xs">
            <div class="flex items-center justify-between mb-1">
                <span class="font-medium text-gray-300">${event.event}</span>
                <span class="text-[9px] px-1 py-0.5 rounded ${
                    event.direction === 'bullish' ? 'bg-green-500/10 text-green-400' :
                    event.direction === 'bearish' ? 'bg-red-500/10 text-red-400' :
                    'bg-gray-500/10 text-gray-400'
                }">${event.direction ? event.direction.toUpperCase() : '—'}</span>
            </div>
            <div class="flex justify-between text-[10px] text-gray-500">
                <span>${event.currency} · ${event.datetime}</span>
                <span>${event.impact}</span>
            </div>
        </div>
    `).join('');
}

// ── Signals Page ────────────────────────────────────────────────

async function refreshSignals() {
    const container = document.getElementById('signal-detail-container');
    const summaryEl = document.getElementById('signal-summary');
    const srEl = document.getElementById('sr-quick-ref');
    if (!container) return;

    const data = await fetchAPI('/api/signals/unified');
    if (data.status !== 'ok') {
        container.innerHTML = `<div class="text-center py-8 text-gray-600">Failed to load signals</div>`;
        return;
    }

    const signals = data.data;
    const filter = document.getElementById('pair-filter');
    const selected = filter ? filter.value : 'all';

    const entries = Object.entries(signals);
    const filtered = selected === 'all'
        ? entries
        : entries.filter(([k]) => k === selected);

    if (filtered.length === 0) {
        container.innerHTML = `<div class="text-center py-8 text-gray-600">No signals available${selected !== 'all' ? ` for ${selected}` : ''}</div>`;
        return;
    }

    // Render detailed unified signal cards
    container.innerHTML = filtered.map(([pair, signal]) => {
        if (!signal || signal.error) {
            return `<div class="text-center py-4 text-gray-600">Error loading ${pair}</div>`;
        }

        const tech = signal.technical_signal || {};
        const newsSig = signal.news_signal || {};
        const unified = signal.unified || {};
        const techDetails = tech.indicators || [];
        const topEvents = newsSig.top_events || [];

        return `
        <div class="p-4 rounded-xl bg-dark-800/50 border border-dark-700/50 mb-3 fade-in">
            <!-- Signal Header -->
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg ${getDirectionClass(unified.direction)} flex items-center justify-center text-xs font-bold">
                        ${unified.direction === 'BUY' ? '↑' : unified.direction === 'SELL' ? '↓' : '—'}
                    </div>
                    <div>
                        <h4 class="text-sm font-semibold text-white">${signal.pair_name}</h4>
                        <span class="text-[10px] text-gray-500">${signal.type || ''}</span>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-bold text-white font-mono">${formatPrice(signal.current_price, pair)}</div>
                    <div class="text-[10px] font-mono ${signal.price_change_24h >= 0 ? 'text-green-400' : 'text-red-400'}">
                        24h: ${formatChange(signal.price_change_24h)}
                    </div>
                </div>
            </div>

            <!-- Verdict Banner -->
            <div class="mb-3 p-2 rounded-lg ${getDirectionClass(unified.direction)} text-center text-[11px]">
                <span class="font-semibold">${unified.verdict || ''}</span>
                <span class="ml-2 text-[9px] ${unified.confidence === 'HIGH' ? 'text-green-400' : unified.confidence === 'MEDIUM' ? 'text-yellow-400' : 'text-gray-400'}">
                    [${unified.confidence || 'LOW'} confidence]
                </span>
            </div>

            <!-- Entry/SL/TP Grid -->
            <div class="grid grid-cols-5 gap-2 mb-4">
                <div class="p-2 rounded-lg bg-dark-900/50 text-center">
                    <div class="text-[9px] text-gray-600 mb-1">Entry</div>
                    <div class="text-xs font-mono text-white font-semibold">${formatPrice(signal.entry_price, pair)}</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-900/50 text-center">
                    <div class="text-[9px] text-gray-600 mb-1">Stop Loss</div>
                    <div class="text-xs font-mono text-red-400">${formatPrice(signal.stop_loss, pair)}</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-900/50 text-center">
                    <div class="text-[9px] text-gray-600 mb-1">TP1 🎯</div>
                    <div class="text-xs font-mono text-green-400">${formatPrice(signal.take_profit_1, pair)}</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-900/50 text-center">
                    <div class="text-[9px] text-gray-600 mb-1">TP2 🎯</div>
                    <div class="text-xs font-mono text-green-300">${formatPrice(signal.take_profit_2, pair)}</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-900/50 text-center">
                    <div class="text-[9px] text-gray-600 mb-1">R:R</div>
                    <div class="text-xs font-mono text-yellow-400">1:${signal.risk_reward_1?.toFixed(1) || '—'}</div>
                </div>
            </div>

            <!-- Two-column: Technical + News -->
            <div class="grid grid-cols-2 gap-3 mb-3">
                <!-- Technical Column -->
                <div class="p-3 rounded-lg bg-dark-900/50">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-blue-400 text-xs font-semibold">📊 Technical</span>
                        <span class="text-[10px] font-mono ${tech.score >= 60 ? 'text-green-400' : tech.score <= 40 ? 'text-red-400' : 'text-gray-400'}">
                            Score: ${tech.score ?? '—'}/100
                        </span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded ${getDirectionClass(tech.direction)}">
                            ${getDirectionText(tech.direction)}
                        </span>
                    </div>
                    <div class="space-y-1">
                        ${techDetails.map(ind => `
                            <div class="flex items-center gap-2 text-[10px]">
                                <span class="w-1.5 h-1.5 rounded-full ${
                                    ind.signal && ind.signal.includes('BUY') ? 'bg-green-400' :
                                    ind.signal && ind.signal.includes('SELL') ? 'bg-red-400' :
                                    'bg-gray-500'
                                }"></span>
                                <span class="text-gray-400">${ind.indicator || ''}</span>
                                <span class="text-gray-500">${ind.reason || ''}</span>
                            </div>
                        `).join('') || '<div class="text-[10px] text-gray-600">No technical indicators available</div>'}
                    </div>
                    ${tech.summary && tech.summary.rsi ? `
                        <div class="mt-2 pt-2 border-t border-dark-700/30 text-[9px] text-gray-600">
                            RSI: ${tech.summary.rsi}
                        </div>
                    ` : ''}
                </div>

                <!-- News Column -->
                <div class="p-3 rounded-lg bg-dark-900/50">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-yellow-400 text-xs font-semibold">📰 News</span>
                        <span class="text-[10px] font-mono ${newsSig.score >= 60 ? 'text-green-400' : newsSig.score <= 40 ? 'text-red-400' : 'text-gray-400'}">
                            Score: ${newsSig.score ?? '—'}/100
                        </span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded ${getDirectionClass(newsSig.direction)}">
                            ${getDirectionText(newsSig.direction)}
                        </span>
                    </div>
                    <div class="space-y-1">
                        ${topEvents.map(evt => `
                            <div class="p-1.5 rounded text-[10px] ${evt.impact && evt.impact.includes('High') ? 'bg-red-500/5 border-l-2 border-red-500' : 'bg-orange-500/5 border-l-2 border-orange-500'}">
                                <div class="flex items-center justify-between">
                                    <span class="text-gray-300 truncate">${evt.event || ''}</span>
                                    <span class="text-[8px] ${evt.direction === 'bullish' ? 'text-green-400' : evt.direction === 'bearish' ? 'text-red-400' : 'text-gray-500'}">
                                        ${(evt.direction || '').toUpperCase()}
                                    </span>
                                </div>
                                <div class="text-gray-600 text-[8px]">${evt.currency || ''} · ${evt.datetime || ''}</div>
                            </div>
                        `).join('') || `<div class="text-[10px] text-gray-600">${newsSig.note || 'No news events'}</div>`}
                    </div>
                    <div class="mt-2 text-[9px] text-gray-600">
                        ${newsSig.events_analyzed || 0} events analyzed
                    </div>
                </div>
            </div>

            <!-- Unified Score Bar -->
            <div class="strength-bar">
                <div class="strength-fill ${unified.direction === 'BUY' ? 'buy' : 'sell'}" style="width: ${unified.score || 50}%"></div>
            </div>
            <div class="flex justify-between mt-1 text-[9px] text-gray-600">
                <span>Unified Score: ${unified.score || 50}/100 · ${unified.agreement || ''}</span>
                <span>Timing: ${signal.timing || '—'}</span>
            </div>
        </div>`;
    }).join('');

    // Update summary
    if (summaryEl) {
        const buyCount = Object.values(signals).filter(s => s?.unified?.direction === 'BUY').length;
        const sellCount = Object.values(signals).filter(s => s?.unified?.direction === 'SELL').length;
        const neutralCount = Object.values(signals).filter(s => !s?.unified?.direction || s.unified.direction === 'NEUTRAL').length;

        summaryEl.innerHTML = `
            <div class="grid grid-cols-2 gap-2">
                <div class="p-2.5 rounded-lg bg-green-500/5 text-center">
                    <div class="text-lg font-bold text-green-400">${buyCount}</div>
                    <div class="text-[9px] text-gray-500">BUY</div>
                </div>
                <div class="p-2.5 rounded-lg bg-red-500/5 text-center">
                    <div class="text-lg font-bold text-red-400">${sellCount}</div>
                    <div class="text-[9px] text-gray-500">SELL</div>
                </div>
            </div>
            <div class="mt-2 p-2 rounded-lg bg-dark-800/50 text-center">
                <div class="text-xs text-gray-400">${neutralCount} Neutral</div>
            </div>
        `;
    }

    // Update S/R quick reference
    if (srEl) {
        const firstSignal = filtered[0]?.[1];
        if (firstSignal && firstSignal.support_levels) {
            srEl.innerHTML = `
                <h3 class="text-sm font-semibold text-white mb-3">S/R: ${firstSignal.pair}</h3>
                <div class="space-y-2 text-xs">
                    <div>
                        <div class="text-gray-500 mb-1">Resistance</div>
                        ${(firstSignal.resistance_levels || []).map(r => `
                            <div class="flex items-center gap-2 p-1.5">
                                <div class="w-8 h-0.5 rounded bg-red-500/50"></div>
                                <span class="font-mono text-red-400">${r}</span>
                            </div>
                        `).join('') || '<div class="text-gray-600">—</div>'}
                    </div>
                    <div>
                        <div class="text-gray-500 mb-1">Support</div>
                        ${(firstSignal.support_levels || []).map(s => `
                            <div class="flex items-center gap-2 p-1.5">
                                <div class="w-8 h-0.5 rounded bg-green-500/50"></div>
                                <span class="font-mono text-green-400">${s}</span>
                            </div>
                        `).join('') || '<div class="text-gray-600">—</div>'}
                    </div>
                </div>
            `;
        }
    }
}

// ── News Page ────────────────────────────────────────────────────

async function refreshNews() {
    const container = document.getElementById('news-container');
    const statsEl = document.getElementById('news-stats');
    if (!container) return;

    const hours = parseInt(document.querySelector('.time-tab.active')?.dataset?.hours || '72');
    const currencyFilter = document.getElementById('currency-filter')?.value || 'all';
    const impactFilter = document.getElementById('impact-filter')?.value || 'all';

    const data = await fetchAPI(`/api/news/upcoming?hours=${hours}`);
    if (data.status !== 'ok') {
        container.innerHTML = `<div class="text-center py-8 text-gray-600">Failed to load news data</div>`;
        return;
    }

    let events = data.data || [];

    // Apply filters
    if (currencyFilter !== 'all') {
        events = events.filter(e => e.currency === currencyFilter);
    }
    if (impactFilter === 'High') {
        events = events.filter(e => e.impact && e.impact.includes('High'));
    } else if (impactFilter === 'Medium') {
        events = events.filter(e => e.impact && e.impact.includes('Medium'));
    }

    if (events.length === 0) {
        container.innerHTML = `<div class="text-center py-12 text-gray-600">
            <div class="text-2xl mb-2">📅</div>
            <div class="text-sm">No upcoming ${impactFilter !== 'all' ? impactFilter : ''} events found</div>
            <div class="text-xs text-gray-600 mt-1">Try a wider time range or different filter</div>
        </div>`;
        return;
    }

    container.innerHTML = events.map(event => `
        <div class="p-3 rounded-lg ${event.impact && event.impact.includes('High') ? 'impact-red' : 'impact-orange'} mb-2 fade-in">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-semibold text-gray-200">${event.event}</span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded ${
                            event.impact && event.impact.includes('High') ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                        }">${event.impact}</span>
                    </div>
                    <div class="flex items-center gap-3 text-[10px] text-gray-500 mb-1">
                        <span>${event.currency}</span>
                        <span>${event.datetime}</span>
                        ${event.status === 'live' ? '<span class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>LIVE</span>' : ''}
                    </div>
                </div>
                <div class="text-right ml-3">
                    ${event.direction ? `
                        <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                            event.direction === 'bullish' ? 'badge-buy' :
                            event.direction === 'bearish' ? 'badge-sell' : 'badge-neutral'
                        }">${event.direction.toUpperCase()}</span>
                    ` : ''}
                </div>
            </div>

            <!-- Forecast data -->
            <div class="grid grid-cols-3 gap-2 mt-2 text-[10px]">
                <div class="p-1.5 rounded bg-dark-800/50 text-center">
                    <div class="text-gray-600">Previous</div>
                    <div class="font-mono text-gray-300">${event.previous || '—'}</div>
                </div>
                <div class="p-1.5 rounded bg-dark-800/50 text-center">
                    <div class="text-gray-600">Forecast</div>
                    <div class="font-mono text-gray-300">${event.forecast || '—'}</div>
                </div>
                <div class="p-1.5 rounded bg-dark-800/50 text-center">
                    <div class="text-gray-600">Actual</div>
                    <div class="font-mono ${event.actual && event.actual !== '-' ? 'text-yellow-400' : 'text-gray-600'}">${event.actual || 'Pending'}</div>
                </div>
            </div>

            <!-- Reasoning -->
            ${event.reasoning ? `
                <div class="mt-1.5 text-[9px] text-gray-600 italic">${event.reasoning}</div>
            ` : ''}

            <!-- Affected pairs -->
            <div class="mt-1.5 flex gap-1">
                ${(event.affected_pairs || []).map(p => `
                    <span class="text-[8px] px-1.5 py-0.5 rounded bg-dark-800 text-gray-500">${p}</span>
                `).join('')}
            </div>
        </div>
    `).join('') || `<div class="text-center py-8 text-gray-600">No events found</div>`;

    // Update stats
    if (statsEl) {
        const statsData = await fetchAPI('/api/news/summary');
        if (statsData.status === 'ok') {
            const stats = statsData.data;
            statsEl.innerHTML = Object.entries(stats).map(([currency, info]) => `
                <div class="p-2.5 rounded-lg bg-dark-800/30 flex items-center justify-between text-xs">
                    <div>
                        <span class="font-semibold text-gray-300">${currency}</span>
                        <span class="text-gray-600 ml-1">${info.upcoming_24h} upcoming</span>
                    </div>
                    <div class="flex gap-2">
                        <span class="text-red-400 font-mono">${info.high}h</span>
                        <span class="text-orange-400 font-mono">${info.medium}m</span>
                    </div>
                </div>
            `).join('');
        }
    }
}

// ── Analysis Page ────────────────────────────────────────────────

async function refreshAnalysis() {
    const data = await fetchAPI('/api/analysis/cross-asset');
    const regimeData = await fetchAPI('/api/analysis/regime');

    if (data.status !== 'ok' && regimeData.status !== 'ok') return;

    const analysis = data.data || {};
    const regime = regimeData.data || {};

    // Regime Banner
    const banner = document.getElementById('regime-banner');
    if (banner && regime.regime) {
        const colorMap = { 'RISK-ON': 'green', 'NEUTRAL': 'yellow', 'DEFENSIVE': 'red' };
        const color = colorMap[regime.regime] || 'gray';
        banner.innerHTML = `
            <div class="flex items-center justify-between p-4 rounded-lg bg-${color}-500/5 border border-${color}-500/20">
                <div>
                    <div class="text-2xl font-bold text-${color}-400">${regime.regime}</div>
                    <div class="text-xs text-gray-500">Current Market Regime Assessment</div>
                </div>
                <div class="text-right text-xs text-gray-500">
                    Updated: ${analysis.timestamp || '—'}
                </div>
            </div>
        `;
    }

    // DXY Analysis
    const dxyEl = document.getElementById('dxy-analysis');
    if (dxyEl && analysis.dxy) {
        const d = analysis.dxy;
        dxyEl.innerHTML = `
            <div class="grid grid-cols-2 gap-3">
                <div class="p-3 rounded-lg bg-dark-800/50">
                    <div class="text-2xl font-bold font-mono text-white">${d.value?.toFixed(2) || '—'}</div>
                    <div class="text-xs ${d.change >= 0 ? 'text-green-400' : 'text-red-400'}">${formatChange(d.change)}</div>
                </div>
                <div class="p-3 rounded-lg bg-dark-800/50">
                    <div class="text-sm text-gray-300">
                        <span class="font-semibold capitalize">${d.trend}</span>
                    </div>
                    <div class="text-xs text-gray-600 capitalize mt-1">
                        Dollar is <span class="${d.strength === 'very_strong' || d.strength === 'strong' ? 'text-green-400' : 'text-gray-400'}">${d.strength?.replace('_', ' ')}</span>
                    </div>
                </div>
            </div>
        `;
    }

    // VIX Analysis
    const vixEl = document.getElementById('vix-analysis');
    if (vixEl && analysis.vix) {
        const v = analysis.vix;
        const regimeLabels = {
            'extreme_fear': { label: 'Extreme Fear 🚨', color: 'red' },
            'fear': { label: 'Fear ⚠️', color: 'yellow' },
            'neutral': { label: 'Neutral ✅', color: 'blue' },
            'complacency': { label: 'Complacency 😴', color: 'green' },
        };
        const regimeInfo = regimeLabels[v.regime] || { label: 'Unknown', color: 'gray' };
        vixEl.innerHTML = `
            <div class="grid grid-cols-2 gap-3">
                <div class="p-3 rounded-lg bg-dark-800/50">
                    <div class="text-2xl font-bold font-mono text-white">${v.value?.toFixed(2) || '—'}</div>
                    <div class="text-xs text-${regimeInfo.color}-400 font-semibold">${regimeInfo.label}</div>
                </div>
                <div class="p-3 rounded-lg bg-dark-800/50 flex flex-col justify-center">
                    <div class="text-xs text-gray-500">Sentiment</div>
                    <div class="text-sm text-gray-300">
                        ${v.risk_on ? '🟢 Risk-On Mode' : '🔴 Risk-Off Mode'}
                    </div>
                </div>
            </div>
        `;
    }

    // Yield Analysis
    const yieldEl = document.getElementById('yield-analysis');
    if (yieldEl && analysis.yields) {
        const y = analysis.yields;
        yieldEl.innerHTML = `
            <div class="grid grid-cols-4 gap-2 mb-3">
                <div class="p-2 rounded-lg bg-dark-800/50 text-center">
                    <div class="text-[9px] text-gray-600">2Y</div>
                    <div class="text-xs font-mono text-white">${y['2y_yield']?.toFixed(3) || '—'}%</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-800/50 text-center">
                    <div class="text-[9px] text-gray-600">5Y</div>
                    <div class="text-xs font-mono text-white">${y['5y_yield']?.toFixed(3) || '—'}%</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-800/50 text-center">
                    <div class="text-[9px] text-gray-600">10Y</div>
                    <div class="text-xs font-mono text-white">${y['10y_yield']?.toFixed(3) || '—'}%</div>
                </div>
                <div class="p-2 rounded-lg bg-dark-800/50 text-center">
                    <div class="text-[9px] text-gray-600">30Y</div>
                    <div class="text-xs font-mono text-white">${y['30y_yield']?.toFixed(3) || '—'}%</div>
                </div>
            </div>
            <div class="p-3 rounded-lg ${y.inverted ? 'bg-red-500/5 border-l-2 border-red-500' : 'bg-green-500/5 border-l-2 border-green-500'}">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold ${y.inverted ? 'text-red-400' : 'text-green-400'}">
                        2Y-10Y Spread: ${y.spread_2_10?.toFixed(3) || '—'}%
                    </span>
                    <span class="text-[10px] text-gray-500">
                        ${y.inverted ? '🔴 INVERTED — Recession Signal' : '🟢 Normal Yield Curve'}
                    </span>
                </div>
            </div>
        `;
    }

    // Correlation Matrix
    const corrEl = document.getElementById('correlation-matrix');
    if (corrEl && analysis.correlations) {
        corrEl.innerHTML = `
            <div class="space-y-2">
                ${Object.entries(analysis.correlations).map(([pair, corr]) => `
                    <div class="flex items-center justify-between p-2 rounded-lg bg-dark-800/30 text-xs">
                        <span class="font-medium text-gray-300">${pair}</span>
                        <div class="flex items-center gap-3">
                            <span class="text-gray-500">${corr.relationship}</span>
                            <span class="font-mono ${corr.dxy_correlation < 0 ? 'text-red-400' : 'text-green-400'}">
                                ${corr.dxy_correlation?.toFixed(3) || '—'}
                            </span>
                            <span class="text-[10px] px-1.5 py-0.5 rounded ${
                                corr.strength === 'strong' ? 'bg-yellow-500/10 text-yellow-400' :
                                corr.strength === 'moderate' ? 'bg-blue-500/10 text-blue-400' :
                                'bg-gray-500/10 text-gray-400'
                            }">${corr.strength}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // Regime Signals
    const signalsEl = document.getElementById('regime-signals');
    if (signalsEl && regime.signals) {
        signalsEl.innerHTML = regime.signals.map(s => `
            <div class="p-2.5 rounded-lg text-xs ${
                s.type === 'risk_off' ? 'bg-red-500/5 border-l-2 border-red-500' :
                s.type === 'risk_on' ? 'bg-green-500/5 border-l-2 border-green-500' :
                s.type === 'warning' ? 'bg-yellow-500/5 border-l-2 border-yellow-500' :
                'bg-blue-500/5 border-l-2 border-blue-500'
            } mb-2">
                <div class="text-gray-300">${s.message}</div>
                <div class="text-[9px] text-gray-600 mt-0.5 capitalize">${s.severity} priority</div>
            </div>
        `).join('') || '<div class="text-center py-4 text-gray-600 text-xs">No regime signals detected</div>';
    }

    // Bias Summary
    const biasEl = document.getElementById('bias-summary');
    if (biasEl) {
        const dxyTrend = analysis.dxy?.trend || 'neutral';
        const vixVal = analysis.vix?.value || 15;
        const yieldInv = analysis.yields?.inverted || false;

        let biasText = '';
        let biasColor = '';

        if (dxyTrend === 'bullish' && vixVal < 15 && !yieldInv) {
            biasText = 'Strong Dollar, Low Vol — Favor USD longs on pullbacks';
            biasColor = 'green';
        } else if (dxyTrend === 'bearish' && vixVal > 20) {
            biasText = 'Weak Dollar, High Vol — Look for USD shorts, XAUUSD longs';
            biasColor = 'yellow';
        } else if (yieldInv) {
            biasText = 'Inverted Curve — DEFENSIVE. Favor safe havens, reduce risk exposure';
            biasColor = 'red';
        } else {
            biasText = 'Mixed signals — Wait for clearer confluence before committing';
            biasColor = 'gray';
        }

        biasEl.innerHTML = `
            <div class="p-4 rounded-lg bg-${biasColor}-500/5 border border-${biasColor}-500/20 text-center">
                <div class="text-xs text-gray-300 leading-relaxed">${biasText}</div>
            </div>
        `;
    }
}

// ── Event Listeners ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Determine which page we're on
    const path = window.location.pathname;

    if (path === '/' || path === '') {
        refreshAll();
        // Auto-refresh every 60 seconds
        setInterval(refreshAll, 60000);
    } else if (path === '/signals') {
        refreshSignals();
        document.getElementById('pair-filter')?.addEventListener('change', refreshSignals);
        setInterval(refreshSignals, 60000);
    } else if (path === '/news') {
        refreshNews();
        document.getElementById('currency-filter')?.addEventListener('change', refreshNews);
        document.getElementById('impact-filter')?.addEventListener('change', refreshNews);
        document.querySelectorAll('.time-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.time-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                refreshNews();
            });
        });
        setInterval(refreshNews, 30000);
    } else if (path === '/analysis') {
        refreshAnalysis();
        setInterval(refreshAnalysis, 120000);
    }
});
