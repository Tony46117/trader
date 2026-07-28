/**
 * ══════════════════════════════════════════════════════════
 *   TRADER v2 — React SPA
 *   Forex Trading Signal Framework Frontend
 *   Features: Real-time SSE streaming · CME Levels · 
 *   Clear BUY/SELL signals · Cross-asset analysis
 * ══════════════════════════════════════════════════════════
 */

const { useState, useEffect, useCallback, useRef, createElement: h } = React;

/* ── API Client ────────────────────────────────────────────────── */
const API = {
  async get(url) {
    const res = await fetch(url);
    const json = await res.json();
    if (json.status !== 'ok') throw new Error(json.message || 'API error');
    return json.data;
  },
  async post(url, body = {}) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (json.status !== 'ok') throw new Error(json.message || 'API error');
    return json;
  },
};

/* ── Hooks ─────────────────────────────────────────────────────── */

function usePolling(fn, interval = 30000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function poll() {
      try {
        const result = await fn();
        if (mounted) {
          setData(result);
          setError(null);
        }
      } catch (e) {
        if (mounted) setError(e.message);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    poll();
    const id = setInterval(poll, interval);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  return { data, loading, error };
}

/* ── SSE Hook for Real-Time Prices ─────────────────────────────── */
function useSSEPrices() {
  const [prices, setPrices] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let eventSource;
    let reconnectTimer;
    let mounted = true;

    function connect() {
      eventSource = new EventSource('/api/prices/stream');
      
      eventSource.onopen = () => {
        if (mounted) setConnected(true);
      };

      eventSource.onmessage = (e) => {
        if (mounted) {
          try {
            const data = JSON.parse(e.data);
            setPrices(data);
          } catch (err) {
            // ignore parse errors
          }
        }
      };

      eventSource.onerror = () => {
        if (mounted) {
          setConnected(false);
          eventSource.close();
          // Reconnect after 3s
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      mounted = false;
      if (eventSource) eventSource.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, []);

  return { prices, connected };
}

function usePriceData() {
  return usePolling(() => API.get('/api/market/overview'), 30000);
}

function useSignalsData() {
  return usePolling(() => API.get('/api/signals/unified'), 30000);
}

function useActiveSignals() {
  return usePolling(() => API.get('/api/signals/active'), 15000);
}

function useAnalysisData() {
  return usePolling(() => API.get('/api/analysis/cross-asset'), 30000);
}

function useRegimeData() {
  return usePolling(() => API.get('/api/analysis/regime'), 60000);
}

function useSetupsData() {
  return usePolling(() => API.get('/api/signals/setups?min_score=55&max=5'), 30000);
}

function useNewsEvents() {
  return usePolling(() => API.get('/api/news/upcoming?hours=48'), 60000);
}

function useCMELevels() {
  return usePolling(() => API.get('/api/cme/levels'), 30000);
}

/* ── Utility Components ────────────────────────────────────────── */

function Loading() {
  return h('div', { className: 'loading-container' },
    h('div', { className: 'loading-spinner' }),
    h('span', { style: { color: 'var(--text-secondary)', fontSize: '0.85rem' } }, 'Loading market data...')
  );
}

function ErrorMsg({ message }) {
  return h('div', { className: 'card', style: { textAlign: 'center', padding: '40px' } },
    h('div', { style: { fontSize: '2rem', marginBottom: '8px' } }, '⚠️'),
    h('p', { style: { color: 'var(--accent-red)' } }, message || 'Failed to load data')
  );
}

function ScoreBar({ score, direction }) {
  const dir = (direction || '').toLowerCase();
  const cls = dir === 'buy' ? 'bullish' : dir === 'sell' ? 'bearish' : 'neutral';
  return h('div', { className: 'score-bar' },
    h('div', {
      className: `score-bar-fill ${cls}`,
      style: { width: `${score || 50}%` },
    })
  );
}

function Badge({ text, variant = 'neutral' }) {
  return h('span', { className: `card-badge badge-${variant}` }, text || variant.toUpperCase());
}

function FormatPrice({ value, decimals = 5 }) {
  if (!value && value !== 0) return '—';
  return Number(value).toFixed(decimals);
}

/* ── Big Direction Badge ───────────────────────────────────────── */
function DirectionBadge({ direction, score, size = 'normal' }) {
  const dir = (direction || 'NEUTRAL').toLowerCase();
  const sz = size === 'large' ? { padding: '6px 20px', fontSize: '0.95rem', fontWeight: 800 } : {};
  const cls = `direction-badge dir-${dir}`;
  const icons = { buy: '🚀', sell: '🔻', neutral: '⚪' };
  return h('span', { className: cls, style: { ...sz, letterSpacing: '0.08em' } },
    `${icons[dir] || ''} ${direction || 'NEUTRAL'}`
  );
}

/* ── Price Card (with real-time SSE overlay) ────────────────────── */

function PriceCard({ pair, data, livePrice }) {
  if (!data && !livePrice) return null;

  // Use SSE live price if available, fall back to API data
  const price = livePrice ? livePrice.bid : (data ? data.price : 0);
  const change = livePrice ? livePrice.change : (data ? data.change : 0);
  const dir = livePrice ? 'neutral' : ((data ? data.direction || '' : '')).toLowerCase();
  const changeCls = change >= 0 ? 'positive' : 'negative';
  const cardCls = `price-card ${dir || 'neutral'} ${livePrice ? 'live' : ''}`;
  const hasSignal = data && (data.setup_valid || data.active_signal);

  return h('div', { className: cardCls },
    h('div', { className: 'price-top' },
      h('span', { className: 'price-pair' }, data ? data.name : (pair || '—')),
      h('span', { className: 'price-type' }, livePrice ? '⚡' : (data ? data.type : '—')),
    ),
    h('div', { className: 'price-value' },
      h(FormatPrice, { value: price, decimals: pair && pair.includes('USD') && data && data.type === 'forex' ? 5 : 2 })
    ),
    h('div', { className: `price-change ${changeCls}` },
      `${change >= 0 ? '+' : ''}${(change || 0).toFixed(3)}%`
    ),
    h('div', { className: 'price-source' },
      livePrice ? `🟢 ${livePrice.timestamp || 'LIVE'}` : `Source: ${data ? data.source || 'N/A' : 'N/A'}`
    ),
    h('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', flexWrap: 'wrap' } },
      data && data.direction && data.direction !== 'NEUTRAL'
        ? h(DirectionBadge, { direction: data.direction, score: data.score, size: 'small' })
        : (hasSignal
          ? h('span', { className: `price-signal badge-${dir}` },
              data.active_signal ? '🔵 ACTIVE' : `🎯 ${data.score || '—'}`
            )
          : h('span', { style: { color: 'var(--text-muted)', fontSize: '0.7rem' } }, livePrice ? '—' : 'No setup')
        ),
    ),
  );
}

/* ── Price Ticker (SSE powered) ────────────────────────────────── */

function PriceTicker({ data, livePrices }) {
  if (!data && !livePrices) return h(Loading);
  const pairs = Object.keys(data || {});
  return h('div', { className: 'fade-in' },
    h('div', { className: 'price-grid' },
      ...pairs.map(key => h(PriceCard, {
        key,
        pair: key,
        data: data ? data[key] : null,
        livePrice: livePrices ? livePrices[key] : null,
      }))
    )
  );
}

/* ── Signal Card ──────────────────────────────────────────────────── */

function SignalCard({ pair, data }) {
  if (!data) return null;

  const dir = (data.unified?.direction || data.technical_direction || 'NEUTRAL');
  const score = data.unified?.score || data.technical_score || 50;
  const conf = (data.unified?.confidence || 'LOW').toLowerCase();
  const info = data.pair_name || pair;
  const comp = (data.unified?.components) || {};
  const compKeys = Object.keys(comp).filter(k => comp[k] !== undefined && comp[k] !== null);
  const verdict = data.unified?.verdict || '';

  return h('div', { className: 'signal-card fade-in' },
    h('div', { className: 'signal-card-header' },
      h('div', { className: 'signal-pair-info' },
        h('span', { className: 'signal-pair-name' }, info),
        h('span', { className: 'signal-pair-type' }, data.type || '—'),
      ),
      h(DirectionBadge, { direction: dir, score }),
    ),

    data.setup_valid && (data.entry || data.sl)
      ? h('div', { className: 'signal-levels' },
          h('div', { className: 'signal-level' },
            h('div', { className: 'signal-level-label' }, 'Entry'),
            h('div', { className: 'signal-level-value' },
              h(FormatPrice, { value: data.entry, decimals: data.type === 'forex' ? 5 : 2 })
            ),
          ),
          h('div', { className: 'signal-level' },
            h('div', { className: 'signal-level-label' }, 'Stop Loss'),
            h('div', { className: 'signal-level-value', style: { color: 'var(--accent-red)' } },
              h(FormatPrice, { value: data.sl, decimals: data.type === 'forex' ? 5 : 2 })
            ),
          ),
          h('div', { className: 'signal-level' },
            h('div', { className: 'signal-level-label' }, `TP1 (R:${data.rr1 || '?'})`),
            h('div', { className: 'signal-level-value', style: { color: 'var(--accent-green)' } },
              h(FormatPrice, { value: data.tp1, decimals: data.type === 'forex' ? 5 : 2 })
            ),
          ),
        )
      : null,

    h(ScoreBar, { score, direction: dir }),

    h('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' } },
      h('span', {}, `Confidence: ${conf.toUpperCase()}`),
      h('span', {}, `Score: ${score}  •  ${data.unified?.agreement || verdict}`),
    ),

    compKeys.length > 0
      ? h('div', { style: { display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '8px' } },
          ...compKeys.map(k => {
            const val = comp[k];
            const color = val >= 65 ? 'var(--accent-green)' : val <= 35 ? 'var(--accent-red)' : 'var(--text-muted)';
            return h('span', {
              key: k,
              style: { fontSize: '0.6rem', padding: '2px 6px', borderRadius: '4px', background: 'var(--bg-secondary)', color },
            title: `${k}: ${val}`,
          }, `${k === 'technical' ? '📊' : k === 'news' ? '📰' : k === 'tick' ? '⚡' : k === 'cme' ? '💎' : k === 'social' ? '💬' : k.slice(0,3)} ${val}`);
          })
        )
      : null,

    data.technical_details && data.technical_details.length > 0
      ? h('details', { style: { marginTop: '12px' } },
          h('summary', { style: { cursor: 'pointer', fontSize: '0.75rem', color: 'var(--text-secondary)' } },
            `Indicators (${data.technical_details.length})`
          ),
          h('table', { className: 'indicator-table', style: { marginTop: '8px' } },
            h('thead', {},
              h('tr', {},
                h('th', {}, 'Indicator'),
                h('th', {}, 'Signal'),
                h('th', {}, 'Value'),
                h('th', {}, 'Weight'),
              ),
            ),
            h('tbody', {},
              ...data.technical_details.map((d, i) =>
                h('tr', { key: i },
                  h('td', { style: { fontSize: '0.7rem' } }, d.indicator || '—'),
                  h('td', { className: `indicator-cell ${(d.signal || '').toLowerCase().includes('buy') ? 'buy' : (d.signal || '').toLowerCase().includes('sell') ? 'sell' : 'neutral'}` },
                    d.signal || '—'
                  ),
                  h('td', { style: { fontFamily: 'JetBrains Mono, monospace', fontSize: '0.7rem' } }, d.value || '—'),
                  h('td', { style: { fontSize: '0.7rem', color: 'var(--text-muted)' } }, d.weight || '—'),
                )
              ),
            ),
          ),
        )
      : null,
  );
}

/* ── Active Signal Panel ─────────────────────────────────────────── */

function ActiveSignalPanel({ signals }) {
  if (!signals || Object.keys(signals).length === 0) {
    return h('div', { className: 'card fade-in' },
      h('div', { className: 'card-header' },
        h('span', { className: 'card-title' }, 'Active Signals'),
      ),
      h('p', { style: { color: 'var(--text-muted)', textAlign: 'center', padding: '20px' } },
        'No active trading signals. New signals are generated automatically when conditions align.'
      ),
    );
  }

  return h('div', { className: 'fade-in' },
    h('div', { className: 'card-header', style: { marginBottom: '12px' } },
      h('span', { className: 'card-title' }, 'Active Signals'),
      h(Badge, { text: `${Object.keys(signals).length} Active`, variant: 'high' }),
    ),
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px' } },
      ...Object.entries(signals).map(([pair, signal]) =>
        h('div', { key: pair, className: 'active-signal-card fade-in' },
          h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' } },
            h('span', { style: { fontWeight: 700, fontSize: '1.1rem' } },
              signal.pair_name || pair
            ),
            h(DirectionBadge, { direction: signal.direction || 'NEUTRAL' }),
          ),
          h('div', { className: 'active-signal-grid' },
            h('div', { className: 'active-level' },
              h('div', { className: 'active-level-label' }, 'Entry'),
              h('div', { className: 'active-level-value' }, signal.entry || '—'),
            ),
            h('div', { className: 'active-level' },
              h('div', { className: 'active-level-label' }, 'Stop Loss'),
              h('div', { className: 'active-level-value', style: { color: 'var(--accent-red)' } }, signal.sl || '—'),
            ),
            h('div', { className: 'active-level' },
              h('div', { className: 'active-level-label' }, `TP (R:${signal.rr1 || '?'})`),
              h('div', { className: 'active-level-value', style: { color: 'var(--accent-green)' } }, signal.tp1 || '—'),
            ),
          ),
          h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' } },
            h('span', {}, `Score: ${signal.score || '—'}  |  Confidence: ${(signal.confidence || '').toUpperCase()}`),
            h('button', {
              className: 'btn btn-danger btn-sm',
              onClick: async () => {
                try {
                  await API.post(`/api/signals/close/${pair}`);
                  window.location.reload();
                } catch (e) { alert(e.message); }
              },
            }, h('i', { className: 'fas fa-times' }), ' Close'),
          ),
        )
      ),
    ),
  );
}

/* ── CME Levels Panel ────────────────────────────────────────────── */

function CMELevelsPanel() {
  const { data: levels, loading, error } = useCMELevels();

  if (loading) return null;
  if (error || !levels) return null;

  const pairs = Object.entries(levels).filter(([k, v]) => v && !v.error);

  return h('div', { className: 'fade-in' },
    h('div', { className: 'card-header', style: { marginBottom: '16px', marginTop: '20px' } },
      h('span', { className: 'card-title' }, '💎 CME Options — Key Levels & Volume Profile'),
      h(Badge, { text: `${pairs.length} Pairs`, variant: 'high' }),
    ),
    h('div', { className: 'cme-levels-grid' },
      ...pairs.map(([pair, data]) => {
        const current = data.current_price || 0;
        const supports = data.supports || [];
        const resistances = data.resistances || [];
        const maxPain = data.max_pain;

        return h('div', { key: pair, className: 'cme-levels-card' },
          h('div', { className: 'cme-levels-header' },
            h('div', {},
              h('span', { style: { fontWeight: 700, fontSize: '1rem' } }, pair),
              h('span', { style: { display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)' } },
              'Max Pain: ', h(FormatPrice, { value: maxPain }), '  |  Current: ', h(FormatPrice, { value: current })
            ),
            ),
            h('span', {
              style: {
                padding: '2px 10px',
                borderRadius: '100px',
                fontSize: '0.7rem',
                fontWeight: 600,
                background: data.pc_sentiment === 'bullish' ? 'var(--accent-green-dim)' :
                           data.pc_sentiment === 'bearish' ? 'var(--accent-red-dim)' : 'rgba(255,255,255,0.05)',
                color: data.pc_sentiment === 'bullish' ? 'var(--accent-green)' :
                       data.pc_sentiment === 'bearish' ? 'var(--accent-red)' : 'var(--text-secondary)',
              }
            }, `P/C: ${data.put_call_ratio_oi || '—'}`),
          ),

          // Support Levels
          h('div', { className: 'cme-section' },
            h('div', { className: 'cme-section-title' }, '🛡️ Support Levels'),
            supports.length > 0
              ? h('div', { className: 'cme-level-list' },
                  ...supports.map((s, i) =>
                    h('div', { key: i, className: `cme-level-row ${s.strength === 'MAJOR' ? 'major' : ''}` },
                      h('span', { className: 'cme-level-price' },
                        h(FormatPrice, { value: s.price, decimals: pair.includes('USD') ? 5 : 2 })
                      ),
                      h('span', { className: 'cme-level-detail' },
                        `OI: ${(s.total_oi || 0).toLocaleString()}`
                      ),
                      h('span', { className: 'cme-level-detail' },
                        `C:${(s.call_volume || 0).toLocaleString()} P:${(s.put_volume || 0).toLocaleString()}`
                      ),
                      h('span', {
                        className: 'cme-level-badge',
                        style: {
                          color: s.pc_ratio < 0.85 ? 'var(--accent-green)' :
                                 s.pc_ratio > 1.15 ? 'var(--accent-red)' : 'var(--text-muted)',
                        }
                      }, `P/C:${s.pc_ratio || '—'}`),
                    )
                  )
                )
              : h('div', { style: { color: 'var(--text-muted)', fontSize: '0.75rem', padding: '8px' } }, 'No significant levels'),
          ),

          // Resistance Levels
          h('div', { className: 'cme-section' },
            h('div', { className: 'cme-section-title' }, '🔴 Resistance Levels'),
            resistances.length > 0
              ? h('div', { className: 'cme-level-list' },
                  ...resistances.map((s, i) =>
                    h('div', { key: i, className: `cme-level-row ${s.strength === 'MAJOR' ? 'major' : ''}` },
                      h('span', { className: 'cme-level-price' },
                        h(FormatPrice, { value: s.price, decimals: pair.includes('USD') ? 5 : 2 })
                      ),
                      h('span', { className: 'cme-level-detail' },
                        `OI: ${(s.total_oi || 0).toLocaleString()}`
                      ),
                      h('span', { className: 'cme-level-detail' },
                        `C:${(s.call_volume || 0).toLocaleString()} P:${(s.put_volume || 0).toLocaleString()}`
                      ),
                      h('span', {
                        className: 'cme-level-badge',
                        style: {
                          color: s.pc_ratio < 0.85 ? 'var(--accent-green)' :
                                 s.pc_ratio > 1.15 ? 'var(--accent-red)' : 'var(--text-muted)',
                        }
                      }, `P/C:${s.pc_ratio || '—'}`),
                    )
                  )
                )
              : h('div', { style: { color: 'var(--text-muted)', fontSize: '0.75rem', padding: '8px' } }, 'No significant levels'),
          ),

          // Volume Summary
          h('div', { style: { marginTop: '12px', padding: '8px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-secondary)' } },
            h('span', {}, `Total Call OI: ${(data.total_call_oi || 0).toLocaleString()}`),
            h('span', {}, `Total Put OI: ${(data.total_put_oi || 0).toLocaleString()}`),
            h('span', {}, `Vol Ratio: ${data.put_call_ratio_vol || '—'}`),
          ),
        );
      }),
    ),
  );
}

/* ── Analysis Panel ────────────────────────────────────────────────── */

function AnalysisPanel() {
  const { data: analysis, loading: al, error: ae } = useAnalysisData();
  const { data: regime, loading: rl, error: re } = useRegimeData();

  if (al || rl) return h(Loading);
  if (ae || re) return h(ErrorMsg, { message: ae || re });

  return h('div', { className: 'fade-in' },
    regime
      ? h('div', { className: 'card', style: { marginBottom: '16px' } },
          h('div', { className: 'card-header' },
            h('span', { className: 'card-title' }, 'Market Regime'),
          ),
          h('div', {
            className: `regime-badge ${(regime.regime || '').toLowerCase()}`,
          },
            regime.regime === 'RISK_ON' ? '🚀 ' : regime.regime === 'RISK_OFF' ? '🛡️ ' : '⚖️ ',
            regime.description || '—'
          ),
        )
      : null,

    analysis
      ? h('div', { className: 'analysis-grid' },
          h('div', { className: 'card' },
            h('div', { className: 'card-header' },
              h('span', { className: 'card-title' }, '🇺🇸 US Dollar Index'),
            ),
            h('div', { className: 'analysis-item' },
              h('span', { className: 'analysis-label' }, 'Value'),
              h('span', { className: 'analysis-value' }, (analysis.dxy?.value || 0).toFixed(2)),
            ),
            h('div', { className: 'analysis-item' },
              h('span', { className: 'analysis-label' }, 'Change'),
              h('span', { className: `analysis-value ${analysis.dxy?.trend === 'bullish' ? 'bullish' : 'bearish'}` },
                `${analysis.dxy?.change >= 0 ? '+' : ''}${(analysis.dxy?.change || 0).toFixed(2)}%`
              ),
            ),
            h('div', { className: 'analysis-item' },
              h('span', { className: 'analysis-label' }, 'Implication'),
              h('span', { style: { fontSize: '0.75rem', textAlign: 'right', maxWidth: '60%', color: 'var(--text-secondary)' } },
                analysis.dxy?.implication || '—'
              ),
            ),
          ),

          h('div', { className: 'card' },
            h('div', { className: 'card-header' },
              h('span', { className: 'card-title' }, '🌊 VIX — Volatility'),
            ),
            h('div', { className: 'analysis-item' },
              h('span', { className: 'analysis-label' }, 'Value'),
              h('span', { className: 'analysis-value' }, (analysis.vix?.value || 0).toFixed(2)),
            ),
            h('div', { className: 'analysis-item' },
              h('span', { className: 'analysis-label' }, 'Regime'),
              h('span', { className: 'analysis-value' }, (analysis.vix?.regime || '—').toUpperCase()),
            ),
            h('div', { className: 'analysis-item' },
              h('span', { className: 'analysis-label' }, 'Implication'),
              h('span', { style: { fontSize: '0.75rem', textAlign: 'right', maxWidth: '60%', color: 'var(--text-secondary)' } },
                analysis.vix?.implication || '—'
              ),
            ),
          ),

          h('div', { className: 'card', style: { gridColumn: '1 / -1' } },
            h('div', { className: 'card-header' },
              h('span', { className: 'card-title' }, '🏦 US Treasury Yields'),
            ),
            h('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '12px' } },
              ['US5Y', 'US10Y', 'US30Y'].map(key => {
                const y = analysis.yields?.[key] || {};
                return h('div', { key, className: 'signal-level' },
                  h('div', { className: 'signal-level-label' }, key.replace('US', '') + 'Y'),
                  h('div', { className: 'signal-level-value' },
                    `${(y.value || 0).toFixed(2)}%`
                  ),
                  h('div', { style: { fontSize: '0.65rem', color: y.trend === 'bullish' ? 'var(--accent-green)' : 'var(--accent-red)' } },
                    `${y.change >= 0 ? '+' : ''}${(y.change || 0).toFixed(2)}%`
                  ),
                );
              }),
            ),
            h('div', { style: { fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center' } },
              `Curve: ${(analysis.yields?.curve || '—').toUpperCase()} — ${analysis.yields?.implication || '—'}`
            ),
          ),
        )
      : h(ErrorMsg, { message: 'No analysis data' }),
  );
}

/* ── Top Setups Panel ──────────────────────────────────────────────── */

function TopSetupsPanel() {
  const { data: setups, loading, error } = useSetupsData();

  if (loading) return null;
  if (error) return null;
  if (!setups || Object.keys(setups).length === 0) return null;

  return h('div', { className: 'card fade-in', style: { marginBottom: '20px' } },
    h('div', { className: 'card-header' },
      h('span', { className: 'card-title' }, '🏆 Top Trading Setups'),
      h(Badge, { text: `${Object.keys(setups).length} Available`, variant: 'high' }),
    ),
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px' } },
      ...Object.entries(setups).map(([pair, data]) => {
        const dir = (data.unified?.direction || '').toLowerCase();
        return h('div', { key: pair, style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' } },
          h('div', {},
            h('div', { style: { fontWeight: 600, fontSize: '0.9rem' } }, data.pair_name || pair),
            h('div', { style: { fontSize: '0.7rem', color: 'var(--text-muted)' } },
              `Score: ${data.unified?.score || '—'}  •  R:R ${data.rr1 || '?'}:1`
            ),
          ),
          h('div', { style: { display: 'flex', alignItems: 'center', gap: '8px' } },
            h(DirectionBadge, { direction: data.unified?.direction || '—' }),
            h('span', { className: 'mono', style: { color: 'var(--text-muted)', fontSize: '0.8rem' } },
              data.unified?.confidence || '—'
            ),
          ),
        );
      }),
    ),
  );
}

/* ── News Events Panel ────────────────────────────────────────────── */

function NewsEventsPanel() {
  const { data: events, loading, error } = useNewsEvents();

  if (loading) return null;
  if (error || !events || events.length === 0) return null;

  const highImpact = events.filter(e => e.impact === 'HIGH').slice(0, 4);
  if (highImpact.length === 0) return null;

  return h('div', { className: 'card fade-in', style: { marginBottom: '16px' } },
    h('div', { className: 'card-header' },
      h('span', { className: 'card-title' }, '📰 Upcoming High-Impact News'),
      h(Badge, { text: `${events.length} Events`, variant: 'high' }),
    ),
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
      ...highImpact.map((evt, i) =>
        h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' } },
          h('div', { style: { flex: 1 } },
            h('div', { style: { fontWeight: 600, fontSize: '0.85rem' } }, evt.event),
            h('div', { style: { fontSize: '0.7rem', color: 'var(--text-muted)' } },
              `${evt.currency} • ${evt.impact} • ${evt.datetime || evt.date + ' ' + evt.time}`
            ),
          ),
          h('div', { style: { display: 'flex', alignItems: 'center', gap: '6px' } },
            h('span', {
              style: { fontSize: '0.7rem', fontWeight: 600, color: evt.direction === 'bullish' ? 'var(--accent-green)' : evt.direction === 'bearish' ? 'var(--accent-red)' : 'var(--text-secondary)' }
            }, (evt.direction || '').toUpperCase()),
            h('span', { style: { fontSize: '0.65rem', color: 'var(--text-muted)' } }, evt.status === 'upcoming' ? '⏳' : '🔴'),
          ),
        )
      ),
    ),
  );
}

/* ── Signals View ────────────────────────────────────────────────── */

function SignalsView() {
  const { data: signals, loading, error } = useSignalsData();
  const { data: active } = useActiveSignals();

  return h('div', { className: 'fade-in' },
    h(ActiveSignalPanel, { signals: active }),
    h(NewsEventsPanel),
    h(TopSetupsPanel),
    h(CMELevelsPanel),
    signals
      ? h('div', { style: { marginTop: '20px' } },
          h('div', { className: 'card-header', style: { marginBottom: '12px' } },
            h('span', { className: 'card-title' }, 'All Pairs — Unified Signals'),
          ),
          h('div', { className: 'signal-grid' },
            ...Object.entries(signals).map(([pair, data]) =>
              h(SignalCard, { key: pair, pair, data })
            )
          ),
        )
      : loading ? h(Loading) : h(ErrorMsg, { message: error }),
  );
}

/* ── Dashboard View ──────────────────────────────────────────────── */

function DashboardView() {
  const { data: prices, loading, error } = usePriceData();
  const { data: active } = useActiveSignals();
  const { data: regime } = useRegimeData();
  const { prices: livePrices, connected: sseConnected } = useSSEPrices();

  if (loading) return h(Loading);
  if (error) return h(ErrorMsg, { message: error });

  return h('div', { className: 'fade-in' },
    h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' } },
      h('span', { className: 'card-title', style: { fontSize: '0.75rem' } }, 'Market Overview'),
      h('span', {
        style: {
          fontSize: '0.65rem',
          padding: '2px 8px',
          borderRadius: '100px',
          background: sseConnected ? 'var(--accent-green-dim)' : 'rgba(255,71,87,0.1)',
          color: sseConnected ? 'var(--accent-green)' : 'var(--accent-red)',
          fontWeight: 600,
        }
      }, sseConnected ? '🟢 LIVE' : '🔴 RECONNECTING'),
    ),
    h(PriceTicker, { data: prices, livePrices }),

    active && Object.keys(active).length > 0
      ? h(ActiveSignalPanel, { signals: active })
      : null,

    regime
      ? h('div', { style: { display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap' } },
          h('div', { className: 'card', style: { flex: 1, minWidth: '200px' } },
            h('div', { className: 'card-header' },
              h('span', { className: 'card-title' }, 'Market Regime'),
            ),
            h('div', {
              className: `regime-badge ${(regime.regime || '').toLowerCase()}`,
              style: { margin: 0 },
            },
              regime.regime === 'RISK_ON' ? '🚀 ' : regime.regime === 'RISK_OFF' ? '🛡️ ' : '⚖️ ',
              regime.description
            ),
          ),
          h('div', { className: 'card', style: { flex: 1, minWidth: '200px' } },
            h('div', { className: 'card-header' },
              h('span', { className: 'card-title' }, 'Cross-Asset'),
            ),
            h('div', { style: { display: 'flex', gap: '16px', flexWrap: 'wrap' } },
              h('span', { style: { fontSize: '0.85rem' } }, `VIX: ${((regime.vix || 0)).toFixed(1)}`),
              h('span', { style: { fontSize: '0.85rem' } }, `10Y: ${((regime.us10y || 0)).toFixed(2)}%`),
              h('span', { style: { fontSize: '0.85rem', color: regime.dxy_trend === 'bearish' ? 'var(--accent-green)' : 'var(--accent-red)' } },
                `DXY: ${(regime.dxy_trend || '').toUpperCase()}`
              ),
            ),
          ),
        )
      : null,

    h(TopSetupsPanel),
  );
}

/* ── Analysis View ──────────────────────────────────────────────── */

function AnalysisView() {
  return h('div', { className: 'fade-in' },
    h('div', { className: 'card-header', style: { marginBottom: '16px' } },
      h('span', { className: 'card-title' }, 'Cross-Asset Analysis'),
    ),
    h(AnalysisPanel),
  );
}

/* ── CME Levels View ───────────────────────────────────────────── */

function CMELevelsView() {
  return h('div', { className: 'fade-in' },
    h(CMELevelsPanel),
  );
}

/* ── App Root ──────────────────────────────────────────────────── */

function App() {
  const [view, setView] = useState('dashboard');

  const navItems = [
    { id: 'dashboard', icon: 'fas fa-chart-line', label: 'Dashboard' },
    { id: 'signals', icon: 'fas fa-bolt', label: 'Signals' },
    { id: 'analysis', icon: 'fas fa-globe', label: 'Analysis' },
    { id: 'cme', icon: 'fas fa-diamond', label: 'CME Levels' },
  ];

  return h('div', { className: 'app-container' },
    h('header', { className: 'header' },
      h('div', { className: 'header-brand' },
        h('span', { className: 'icon' }, '📈'),
        h('span', {}, 'Trader'),
        h('span', { style: { fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 400 } }, 'v2'),
      ),
      h('nav', { className: 'header-nav' },
        ...navItems.map(item =>
          h('button', {
            key: item.id,
            className: view === item.id ? 'active' : '',
            onClick: () => setView(item.id),
          },
            h('i', { className: item.icon }),
            h('span', { className: 'mobile-hide' }, ' ', item.label),
          )
        ),
      ),
      h('div', { className: 'header-status' },
        h('span', { className: 'status-dot live' }),
        h('span', { style: { fontSize: '0.75rem', color: 'var(--text-secondary)' } }, 'LIVE'),
      ),
    ),

    h('main', { className: 'main-content' },
      view === 'dashboard' ? h(DashboardView) :
      view === 'signals' ? h(SignalsView) :
      view === 'analysis' ? h(AnalysisView) :
      view === 'cme' ? h(CMELevelsView) :
      h(DashboardView),
    ),
  );
}

/* ── Mount ──────────────────────────────────────────────────────── */

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(h(App));
