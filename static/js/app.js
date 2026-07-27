/* =============================================================
   TRADER — React SPA Frontend
   Professional Trading Signal Framework
   ============================================================= */

const { useState, useEffect, useCallback, useRef, createElement: h } = React;

/* ── Utility ── */
const API_BASE = '/api';
const PAIRS_LIST = ['EURUSD', 'GBPUSD', 'XAUUSD', 'BTCUSD', 'ETHUSD'];

async function fetchJSON(url) {
  const res = await fetch(API_BASE + url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  if (json.status === 'error') throw new Error(json.message || 'API error');
  return json.data;
}

function cls(...parts) { return parts.filter(Boolean).join(' '); }

function fmtPrice(v, pairType = 'forex') {
  if (v == null || v === 0) return '—';
  return pairType === 'forex' ? v.toFixed(5) : v.toFixed(2);
}

function fmtPct(v) {
  if (v == null) return '—';
  const s = v >= 0 ? '+' : '';
  return `${s}${v.toFixed(2)}%`;
}

function fmtScore(v) {
  if (v == null) return '—';
  return Math.round(v).toString();
}

function scoreColor(v) {
  if (v == null) return 'var(--neutral)';
  if (v >= 65) return 'var(--buy)';
  if (v <= 35) return 'var(--sell)';
  return 'var(--neutral)';
}

function directionBadge(dir) {
  const d = (dir || 'NEUTRAL').toUpperCase();
  if (d === 'BUY' || d === 'BULLISH') return 'buy';
  if (d === 'SELL' || d === 'BEARISH') return 'sell';
  return 'neutral';
}

/* ── Loading Spinner ── */
function Loading({ text = 'Loading...' }) {
  return h('div', { className: 'loading' },
    h('div', { className: 'spinner' }),
    text
  );
}

function ErrorMsg({ message }) {
  return message ? h('div', { className: 'error-msg' }, message) : null;
}

function NoData({ text = 'No data available' }) {
  return h('div', { className: 'no-data' }, text);
}

/* ── Navigation ── */
function Nav({ activeTab, onTabChange, theme, onThemeToggle, status }) {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'signals', label: 'Signals' },
    { id: 'news', label: 'News' },
    { id: 'analysis', label: 'Analysis' },
  ];

  return h('nav', { className: 'nav' },
    h('div', { className: 'nav-inner' },
      h('div', { className: 'nav-left' },
        h('div', { className: 'nav-logo' },
          h('span', { className: 'logo-dot' }),
          'TRADER'
        ),
        h('ul', { className: 'nav-links' },
          tabs.map(tab =>
            h('li', { key: tab.id },
              h('a', {
                href: '#',
                className: cls(activeTab === tab.id && 'active'),
                onClick: (e) => { e.preventDefault(); onTabChange(tab.id); }
              }, tab.label)
            )
          )
        )
      ),
      h('div', { className: 'nav-right' },
        h('div', { className: 'nav-status' },
          h('span', { className: cls('dot', status === 'ok' ? 'live' : 'offline') }),
          status === 'ok' ? 'LIVE' : 'OFFLINE'
        ),
        h('button', {
          className: 'theme-toggle',
          onClick: onThemeToggle,
          title: theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
        },
          h('span', { className: 'icon' }, theme === 'dark' ? '\u2600' : '\u263E'),
          theme === 'dark' ? 'LIGHT' : 'DARK'
        )
      )
    )
  );
}

/* ── Market Regime Bar ── */
function RegimeBar({ regime }) {
  if (!regime) return null;
  const dxy = regime.dxy || {};
  const vix = regime.vix || {};
  const yields = regime.yields || {};

  return h('div', { className: 'regime-bar' },
    h('div', { className: 'regime-item' },
      h('div', { className: 'label' }, 'DXY'),
      h('div', { className: 'value', style: { color: 'var(--accent)' } },
        dxy.value != null ? dxy.value.toFixed(2) : '—'
      ),
      h('div', { className: cls('change', (dxy.change || 0) >= 0 ? 'pos' : 'neg') },
        fmtPct(dxy.change)
      )
    ),
    h('div', { className: 'regime-item' },
      h('div', { className: 'label' }, 'VIX'),
      h('div', { className: 'value', style: { color: (vix.value || 0) > 20 ? 'var(--sell)' : 'var(--buy)' } },
        vix.value != null ? vix.value.toFixed(1) : '—'
      ),
      h('div', { className: 'change', style: { color: 'var(--text-tertiary)' } },
        vix.regime ? vix.regime.replace('_', ' ').toUpperCase() : ''
      )
    ),
    h('div', { className: 'regime-item' },
      h('div', { className: 'label' }, '2Y-10Y SPREAD'),
      h('div', { className: 'value', style: { color: yields.inverted ? 'var(--sell)' : 'var(--buy)' } },
        yields.spread_2_10 != null ? yields.spread_2_10.toFixed(3) + '%' : '—'
      ),
      h('div', { className: 'change', style: { color: 'var(--text-tertiary)' } },
        yields.inverted ? 'INVERTED' : 'NORMAL'
      )
    )
  );
}

/* ── Pair Card ── */
function PairCard({ pair, data, onClick }) {
  const unified = data?.unified || {};
  const score = unified.score;
  const dir = unified.direction || 'NEUTRAL';
  const conf = unified.confidence || 'LOW';
  const signalState = data?.signal_state || {};
  const isActive = signalState.status === 'ACTIVE';

  const badgeClass = isActive ? 'active' : directionBadge(dir);
  const fillWidth = score != null ? Math.min(100, Math.abs(score - 50) * 2 + 20) : 0;
  const fillColor = dir === 'BUY' ? 'var(--buy)' : dir === 'SELL' ? 'var(--sell)' : 'var(--neutral)';

  return h('div', {
    className: 'pair-card',
    onClick: () => onClick?.(pair, data)
  },
    h('div', { className: 'pair-header' },
      h('div', null,
        h('div', { className: 'pair-name' }, data?.pair_name || pair),
        h('div', { className: 'pair-type' }, data?.type || '')
      ),
      h('div', null,
        isActive
          ? h('span', { className: 'badge badge active' }, 'ACTIVE')
          : h('span', { className: cls('badge badge', badgeClass) }, dir)
      )
    ),
    h('div', { className: 'pair-price', style: { color: scoreColor(score) } },
      fmtPrice(data?.current_price, data?.type)
    ),
    h('div', { className: 'pair-change' },
      h('span', { style: { color: 'var(--text-tertiary)' } }, '24h: '),
      h('span', {
        style: { color: (data?.price_change_24h || 0) >= 0 ? 'var(--buy)' : 'var(--sell)' }
      }, fmtPct(data?.price_change_24h))
    ),
    h('div', { className: 'confidence-bar' },
      h('div', { className: 'fill', style: { width: fillWidth + '%', background: fillColor } })
    ),
    h('div', { className: 'pair-meta' },
      h('div', { className: 'pair-meta-item' },
        'Score: ', h('strong', { style: { color: scoreColor(score) } }, fmtScore(score))
      ),
      h('div', { className: 'pair-meta-item' },
        'RR: ', h('strong', null, data?.risk_reward_1 ? data.risk_reward_1.toFixed(1) : '—')
      ),
      isActive && h('div', { className: 'pair-meta-item' },
        'Status: ', h('strong', { style: { color: 'var(--accent)' } }, 'ACTIVE')
      )
    )
  );
}

/* ── Pairs Grid ── */
function PairsGrid({ overview, onPairClick, title }) {
  const entries = Object.entries(overview || {});

  if (!entries.length) return NoData({ text: 'No market data available' });

  return h('div', null,
    h('div', { className: 'section-title' },
      title || 'Market Overview',
      h('span', { className: 'count' }, entries.length)
    ),
    h('div', { className: 'pairs-grid' },
      entries.map(([pair, data]) =>
        h(PairCard, { key: pair, pair, data, onClick: onPairClick })
      )
    )
  );
}

/* ── Top Setups ── */
function TopSetups({ setups, onPairClick }) {
  if (!setups || !setups.length) return null;

  return h('div', { style: { marginTop: 20 } },
    h('div', { className: 'section-title' },
      'Top Setups',
      h('span', { className: 'count' }, setups.length)
    ),
    h('div', { className: 'pairs-grid' },
      setups.map(s =>
        h(PairCard, {
          key: s.pair,
          pair: s.pair,
          data: {
            pair_name: s.pair_name,
            type: s.type,
            current_price: s.current_price,
            unified: { score: s.score, direction: s.direction, confidence: s.confidence },
            risk_reward_1: s.rr1,
            signal_state: s.signal_state,
            price_change_24h: 0,
          },
          onClick: onPairClick
        })
      )
    )
  );
}

/* ── Dashboard View ── */
function DashboardView({ overview, setups, regime, onPairClick }) {
  return h('div', { className: 'dashboard-grid' },
    h(RegimeBar, { regime }),
    h(PairsGrid, { overview, onPairClick }),
    h(TopSetups, { setups, onPairClick })
  );
}

/* ── Indicator Bias Table ── */
function IndicatorBiasTable({ indicators }) {
  if (!indicators || !indicators.length) {
    return h('div', { className: 'no-data', style: { padding: '12px', fontSize: '0.8rem' } },
      'No indicator data available'
    );
  }

  return h('table', { className: 'indicator-table' },
    h('thead', null,
      h('tr', null,
        h('th', null, 'Indicator'),
        h('th', null, 'Signal'),
        h('th', null, 'Value'),
        h('th', null, 'Bias'),
        h('th', { style: { textAlign: 'right' } }, 'Weight')
      )
    ),
    h('tbody', null,
      indicators.map((ind, i) => {
        const sig = (ind.signal || '').toUpperCase();
        const badgeCls = sig.includes('BUY') ? 'buy' : sig.includes('SELL') ? 'sell' : 'neutral';
        return h('tr', { key: i },
          h('td', { style: { fontWeight: 600 } }, ind.indicator || '—'),
          h('td', null,
            h('span', { className: cls('badge', badgeCls), style: { fontSize: '0.65rem' } },
              ind.signal || '—'
            )
          ),
          h('td', { className: 'value' }, ind.value || '—'),
          h('td', null, ind.reason || '—'),
          h('td', { className: 'weight' }, ind.weight || '—')
        );
      })
    )
  );
}

/* ── Levels Display ── */
function LevelsBox({ data }) {
  return h('div', { className: 'levels-grid' },
    h('div', { className: 'level-box entry' },
      h('div', { className: 'level-label' }, 'Entry'),
      h('div', { className: 'level-value', style: { color: 'var(--accent)' } },
        fmtPrice(data?.entry_price, data?.type)
      ),
      data?.risk_reward_1 ? h('div', { className: 'level-rr' }, `RR 1:${data.risk_reward_1.toFixed(1)}`) : null
    ),
    h('div', { className: 'level-box support' },
      h('div', { className: 'level-label' }, 'Stop Loss'),
      h('div', { className: 'level-value', style: { color: 'var(--sell)' } },
        fmtPrice(data?.stop_loss, data?.type)
      )
    ),
    h('div', { className: 'level-box resistance' },
      h('div', { className: 'level-label' }, 'Take Profit 1'),
      h('div', { className: 'level-value', style: { color: 'var(--buy)' } },
        fmtPrice(data?.take_profit_1, data?.type)
      ),
      data?.risk_reward_1 ? h('div', { className: 'level-rr' },
        `TP2: ${fmtPrice(data?.take_profit_2, data?.type) || '—'}  `
      ) : null
    )
  );
}

/* ── CME Levels Display ── */
function CmeLevelsDisplay({ cmeLevels, cmeSignal }) {
  if (!cmeLevels && !cmeSignal) return null;

  const levels = cmeLevels || {};
  const signal = cmeSignal || {};
  const gamma = signal.gamma_levels || {};

  return h('div', null,
    h('div', { className: 'section-title', style: { fontSize: '0.85rem', marginBottom: 8 } }, 'CME Key Levels'),
    h('div', { className: 'cme-levels' },
      h('div', { className: 'cme-level-item' },
        h('div', { className: 'label' }, 'Primary Resistance'),
        h('div', { className: 'value', style: { color: 'var(--sell)' } },
          levels.primary_resistance != null ? levels.primary_resistance.toFixed(5) : '—'
        )
      ),
      h('div', { className: 'cme-level-item' },
        h('div', { className: 'label' }, 'Primary Support'),
        h('div', { className: 'value', style: { color: 'var(--buy)' } },
          levels.primary_support != null ? levels.primary_support.toFixed(5) : '—'
        )
      ),
      h('div', { className: 'cme-level-item' },
        h('div', { className: 'label' }, 'Max Pain'),
        h('div', { className: 'value', style: { color: 'var(--accent)' } },
          levels.max_pain != null ? levels.max_pain.toFixed(5) : '—'
        )
      ),
      h('div', { className: 'cme-level-item' },
        h('div', { className: 'label' }, 'Put/Call Ratio'),
        h('div', { className: 'value' },
          signal.put_call_ratio != null ? signal.put_call_ratio.toFixed(3) : '—'
        )
      ),
      h('div', { className: 'cme-level-item' },
        h('div', { className: 'label' }, 'Gamma Flip High'),
        h('div', { className: 'value', style: { color: 'var(--sell)' } },
          gamma.high != null ? gamma.high.toFixed(5) : '—'
        )
      ),
      h('div', { className: 'cme-level-item' },
        h('div', { className: 'label' }, 'Gamma Flip Low'),
        h('div', { className: 'value', style: { color: 'var(--buy)' } },
          gamma.low != null ? gamma.low.toFixed(5) : '—'
        )
      )
    )
  );
}

/* ── Component Score Bar ── */
function ComponentScoreBar({ name, score }) {
  const dir = score >= 60 ? 'BUY' : score <= 40 ? 'SELL' : 'NEUTRAL';
  const fill = dir === 'BUY' ? score : dir === 'SELL' ? 100 - score : Math.abs(score - 50) * 2;
  const color = dir === 'BUY' ? 'var(--buy)' : dir === 'SELL' ? 'var(--sell)' : 'var(--neutral)';

  return h('div', { style: { marginBottom: 6 } },
    h('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: 2 } },
      h('span', { style: { fontWeight: 600 } }, name),
      h('span', { style: { fontFamily: 'var(--font-mono)', color } }, `${fmtScore(score)} ${dir}`)
    ),
    h('div', { className: 'confidence-bar', style: { height: 4 } },
      h('div', { className: 'fill', style: { width: Math.min(100, fill * 1.2) + '%', background: color } })
    )
  );
}

/* ── Signal Detail Panel (Modal) ── */
function SignalDetailPanel({ pair, data, onClose }) {
  if (!data) return null;

  const unified = data.unified || {};
  const tech = data.technical_signal || {};
  const news = data.news_signal || {};
  const tick = data.tick_signal || {};
  const cme = data.cme_signal || {};
  const social = data.social_signal || {};
  const components = unified.components || {};
  const signalState = data.signal_state || {};
  const dir = unified.direction || 'NEUTRAL';
  const badgeCls = directionBadge(dir);

  return h('div', { className: 'detail-panel-overlay', onClick: (e) => { if (e.target === e.currentTarget) onClose(); } },
    h('div', { className: 'detail-panel' },
      h('div', { className: 'detail-panel-header' },
        h('h2', null,
          data.pair_name || pair,
          h('span', { className: cls('badge', badgeCls) }, dir),
          signalState.status === 'ACTIVE' && h('span', { className: 'badge active' }, 'ACTIVE SIGNAL'),
          signalState.status && signalState.status !== 'ACTIVE' && signalState.status !== 'NO_SIGNAL' &&
            h('span', { className: cls('badge', badgeCls === 'buy' ? 'buy' : 'sell') }, signalState.status)
        ),
        h('button', { className: 'detail-panel-close', onClick: onClose }, '\u2715')
      ),
      h('div', { className: 'detail-panel-body' },
        /* Signal State */
        signalState.status && signalState.status !== 'NO_SIGNAL' && h('div', { className: 'signal-state-bar' },
          h('div', { className: 'signal-state-item' },
            h('div', { className: 'label' }, 'Status'),
            h('div', { className: 'value', style: { color: 'var(--accent)' } }, signalState.status)
          ),
          h('div', { className: 'signal-state-item' },
            h('div', { className: 'label' }, 'Created'),
            h('div', { className: 'value', style: { fontSize: '0.75rem' } }, signalState.created_at || '—')
          ),
          signalState.closed_at && h('div', { className: 'signal-state-item' },
            h('div', { className: 'label' }, 'Closed'),
            h('div', { className: 'value', style: { fontSize: '0.75rem' } }, signalState.closed_at)
          ),
          signalState.pips_result ? h('div', { className: 'signal-state-item' },
            h('div', { className: 'label' }, 'Pips'),
            h('div', { className: 'value', style: { color: signalState.pips_result > 0 ? 'var(--buy)' : 'var(--sell)' } },
              signalState.pips_result > 0 ? '+' : '', signalState.pips_result
            )
          ) : null
        ),

        /* Price & Verdict */
        h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } },
          h('div', null,
            h('div', { style: { fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontWeight: 600 } }, 'Current Price'),
            h('div', { style: { fontFamily: 'var(--font-mono)', fontSize: '1.4rem', fontWeight: 700, color: scoreColor(unified.score) } },
              fmtPrice(data.current_price, data.type)
            )
          ),
          h('div', { style: { textAlign: 'right' } },
            h('div', { style: { fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', fontWeight: 600 } }, 'Confidence'),
            h('div', { style: { fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700, color: unified.confidence === 'HIGH' ? 'var(--buy)' : unified.confidence === 'MEDIUM' ? '#d97706' : 'var(--text-tertiary)' } },
              unified.confidence || '—'
            )
          )
        ),

        unified.verdict && h('div', { className: 'verdict-text' }, unified.verdict),

        /* Signal Levels */
        h(LevelsBox, { data }),

        h('div', { className: 'section-divider' }),

        /* Component Scores */
        h('div', { className: 'section-title', style: { fontSize: '0.85rem', marginBottom: 8 } }, 'Signal Components'),
        h('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 } },
          h(ComponentScoreBar, { name: 'Technical', score: components.technical }),
          h(ComponentScoreBar, { name: 'News', score: components.news }),
          h(ComponentScoreBar, { name: 'Tick Data', score: components.tick }),
          h(ComponentScoreBar, { name: 'CME', score: components.cme }),
          h('div', { style: { gridColumn: '1 / -1' } },
            h(ComponentScoreBar, { name: 'Social Sentiment', score: components.social })
          )
        ),

        h('div', { className: 'section-divider' }),

        /* Indicator Bias */
        h('div', { className: 'section-title', style: { fontSize: '0.85rem', marginBottom: 8 } },
          'Indicator Bias',
          h('span', { className: 'count' }, (tech.indicators || []).length)
        ),
        h(IndicatorBiasTable, { indicators: tech.indicators }),

        h('div', { className: 'section-divider' }),

        /* CME Levels */
        h(CmeLevelsDisplay, { cmeLevels: data.cme_levels, cmeSignal: cme }),

        h('div', { className: 'section-divider' }),

        /* All Signal Sources */
        h('div', { className: 'signal-detail-grid' },
          /* Technical */
          h('div', { className: 'panel' },
            h('div', { style: { fontWeight: 700, fontSize: '0.85rem', marginBottom: 8 } }, 'Technical Analysis'),
            h('div', { style: { fontSize: '0.8rem', marginBottom: 4 } },
              'RSI: ', h('strong', null, tech.rsi != null ? tech.rsi.toFixed(1) : '—'),
              ' | ATR: ', h('strong', null, tech.atr != null ? tech.atr.toFixed(5) : '—')
            ),
            h('div', { style: { fontSize: '0.75rem', color: 'var(--text-tertiary)' } },
              `Direction: ${tech.direction || 'NEUTRAL'}  |  Score: ${fmtScore(tech.score)}`
            )
          ),

          /* News */
          h('div', { className: 'panel' },
            h('div', { style: { fontWeight: 700, fontSize: '0.85rem', marginBottom: 8 } }, 'News Events'),
            h('div', { style: { fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: 6 } },
              `${news.events_analyzed || 0} events analyzed`
            ),
            news.top_events && news.top_events.slice(0, 3).map((ev, i) =>
              h('div', { key: i, style: { fontSize: '0.75rem', padding: '4px 0', borderTop: '1px solid var(--border-light)' } },
                h('div', { style: { fontWeight: 600 } }, ev.event),
                h('div', { style: { color: 'var(--text-muted)' } }, `${ev.datetime || ''} — ${ev.impact || ''}`)
              )
            )
          ),

          /* Tick */
          h('div', { className: 'panel' },
            h('div', { style: { fontWeight: 700, fontSize: '0.85rem', marginBottom: 8 } }, 'Tick Data'),
            h('div', { style: { fontSize: '0.8rem', lineHeight: 1.8 } },
              h('div', null, 'Momentum: ', h('strong', null, fmtScore(tick.score)),
                h('span', { className: cls('badge', directionBadge(tick.direction)), style: { marginLeft: 6, fontSize: '0.6rem' } }, tick.direction || '—')
              ),
              h('div', null, 'Micro Trend: ', h('strong', null, tick.micro_trend || '—')),
              h('div', null, 'Liquidity: ', h('strong', null, tick.liquidity_score != null ? tick.liquidity_score + '/10' : '—'))
            )
          ),

          /* CME */
          h('div', { className: 'panel' },
            h('div', { style: { fontWeight: 700, fontSize: '0.85rem', marginBottom: 8 } }, 'CME Futures & Options'),
            h('div', { style: { fontSize: '0.8rem', lineHeight: 1.8 } },
              h('div', null, 'Assessment: ', h('strong', {
                style: { color: cme.assessment === 'bullish' ? 'var(--buy)' : cme.assessment === 'bearish' ? 'var(--sell)' : 'var(--neutral)' }
              }, (cme.assessment || 'neutral').toUpperCase())),
              h('div', null, 'Conviction: ', h('strong', null, (cme.conviction || 'low').toUpperCase())),
              h('div', null, 'Max Pain: ', h('strong', { style: { fontFamily: 'var(--font-mono)' } },
                cme.max_pain != null ? cme.max_pain.toFixed(5) : '—'
              ))
            )
          ),

          /* Social */
          h('div', { className: 'panel full-width' },
            h('div', { style: { fontWeight: 700, fontSize: '0.85rem', marginBottom: 8 } }, 'Social Sentiment'),
            h('div', { style: { fontSize: '0.8rem', lineHeight: 1.8, display: 'flex', gap: 24 } },
              h('div', null, 'Classification: ',
                h('strong', { style: { color: social.classification === 'bullish' ? 'var(--buy)' : social.classification === 'bearish' ? 'var(--sell)' : 'var(--neutral)' } },
                  (social.classification || 'neutral').toUpperCase()
                )
              ),
              h('div', null, 'Volume: ', h('strong', null, social.mention_volume || 0)),
              h('div', null, 'Consensus: ', h('strong', null, (social.consensus || 'mixed').replace('_', ' ').toUpperCase()))
            )
          )
        ),

        /* Support / Resistance */
        h('div', { className: 'section-divider' }),
        h('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 } },
          h('div', null,
            h('div', { className: 'section-title', style: { fontSize: '0.85rem', marginBottom: 6 } }, 'Support Levels'),
            (data.support_levels || []).map((s, i) =>
              h('div', { key: i, style: { fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--buy)', padding: '2px 0' } },
                fmtPrice(s, data.type)
              )
            )
          ),
          h('div', null,
            h('div', { className: 'section-title', style: { fontSize: '0.85rem', marginBottom: 6 } }, 'Resistance Levels'),
            (data.resistance_levels || []).map((r, i) =>
              h('div', { key: i, style: { fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--sell)', padding: '2px 0' } },
                fmtPrice(r, data.type)
              )
            )
          )
        )
      )
    )
  );
}

/* ── Signals View ── */
function SignalsView({ signals, onPairClick }) {
  const entries = Object.entries(signals || {});
  const withSignals = entries.filter(([, d]) => {
    const dir = d?.unified?.direction || 'NEUTRAL';
    return dir !== 'NEUTRAL';
  });
  const neutral = entries.filter(([, d]) => {
    const dir = d?.unified?.direction || 'NEUTRAL';
    return dir === 'NEUTRAL';
  });

  return h('div', null,
    withSignals.length > 0 && h('div', null,
      h('div', { className: 'section-title' },
        'Active Signals',
        h('span', { className: 'count' }, withSignals.length)
      ),
      h('div', { className: 'pairs-grid' },
        withSignals.map(([pair, data]) =>
          h(PairCard, { key: pair, pair, data, onClick: onPairClick })
        )
      )
    ),

    neutral.length > 0 && h('div', { style: { marginTop: 20 } },
      h('div', { className: 'section-title' },
        'Neutral / No Setup',
        h('span', { className: 'count' }, neutral.length)
      ),
      h('div', { className: 'pairs-grid' },
        neutral.map(([pair, data]) =>
          h(PairCard, { key: pair, pair, data, onClick: onPairClick })
        )
      )
    ),

    !entries.length && h(NoData, { text: 'No signal data available' })
  );
}

/* ── News Calendar View ── */
function NewsView({ events }) {
  if (!events || !events.length) return h(NoData, { text: 'No upcoming news events' });

  const now = new Date();

  return h('div', null,
    h('div', { className: 'section-title' },
      'Economic Calendar',
      h('span', { className: 'count' }, events.length)
    ),
    h('div', { className: 'news-list' },
      h('div', { className: 'news-header' },
        h('span', null, 'Date'),
        h('span', null, 'Impact'),
        h('span', null, 'Event'),
        h('span', { style: { textAlign: 'right' } }, 'Actual'),
        h('span', { style: { textAlign: 'right' } }, 'Forecast'),
        h('span', { style: { textAlign: 'right' } }, 'Prev')
      ),
      events.slice(0, 50).map((ev, i) => {
        const impact = (ev.impact || '').toLowerCase();
        let impactClass = 'low';
        if (impact.includes('high') || impact.includes('red')) impactClass = 'high';
        else if (impact.includes('medium') || impact.includes('orange')) impactClass = 'medium';

        const evTime = ev.datetime ? new Date(ev.datetime) : null;
        const isSoon = evTime && ((evTime - now) / 1000 / 60 / 60) < 2;

        return h('div', {
          key: i,
          className: 'news-event',
          style: isSoon ? { background: 'var(--accent-light)' } : {}
        },
          h('span', { className: 'event-date' }, ev.date || ev.datetime || '—'),
          h('span', { className: cls('event-impact', impactClass) },
            impactClass === 'high' ? 'HIGH' : impactClass === 'medium' ? 'MED' : 'LOW'
          ),
          h('span', { className: 'event-name' }, ev.event || '—'),
          h('span', { className: 'event-actual', style: { textAlign: 'right' } }, ev.actual || '—'),
          h('span', { className: 'event-forecast', style: { textAlign: 'right' } }, ev.forecast || '—'),
          h('span', { className: 'event-forecast', style: { textAlign: 'right' } }, ev.previous || '—')
        );
      })
    )
  );
}

/* ── Cross-Asset Analysis View ── */
function AnalysisView({ analysis, cmeAll, regime }) {
  const dxy = analysis?.dxy || {};
  const vix = analysis?.vix || {};
  const yields = analysis?.yields || {};
  const correlations = analysis?.correlations || {};

  return h('div', null,
    /* Market Regime */
    h(RegimeBar, { regime }),

    /* Cross Asset Grid */
    h('div', { className: 'section-title', style: { marginTop: 20 } }, 'Cross-Asset Data'),
    h('div', { className: 'asset-grid' },
      h('div', { className: 'asset-card' },
        h('div', { className: 'asset-name' }, 'US Dollar Index'),
        h('div', { className: 'asset-value', style: { color: 'var(--accent)' } },
          dxy.value != null ? dxy.value.toFixed(2) : '—'
        ),
        h('div', { className: cls('asset-change', (dxy.change || 0) >= 0 ? 'pos' : 'neg') },
          fmtPct(dxy.change),
          ' | ', dxy.strength ? dxy.strength.replace('_', ' ').toUpperCase() : ''
        )
      ),
      h('div', { className: 'asset-card' },
        h('div', { className: 'asset-name' }, 'VIX'),
        h('div', { className: 'asset-value', style: { color: (vix.value || 0) > 20 ? 'var(--sell)' : 'var(--buy)' } },
          vix.value != null ? vix.value.toFixed(1) : '—'
        ),
        h('div', { className: 'change', style: { color: 'var(--text-tertiary)', fontSize: '0.85rem', fontFamily: 'var(--font-mono)', marginTop: 2 } },
          vix.regime ? vix.regime.replace('_', ' ').toUpperCase() : ''
        )
      ),
      h('div', { className: 'asset-card' },
        h('div', { className: 'asset-name' }, '10Y Yield'),
        h('div', { className: 'asset-value' },
          yields['10y_yield'] != null ? yields['10y_yield'].toFixed(2) + '%' : '—'
        )
      ),
      h('div', { className: 'asset-card' },
        h('div', { className: 'asset-name' }, '2Y Yield'),
        h('div', { className: 'asset-value' },
          yields['2y_yield'] != null ? yields['2y_yield'].toFixed(2) + '%' : '—'
        )
      ),
      h('div', { className: 'asset-card' },
        h('div', { className: 'asset-name' }, '30Y Yield'),
        h('div', { className: 'asset-value' },
          yields['30y_yield'] != null ? yields['30y_yield'].toFixed(2) + '%' : '—'
        )
      ),
      h('div', { className: 'asset-card' },
        h('div', { className: 'asset-name' }, 'Yield Curve'),
        h('div', { className: 'asset-value', style: { color: yields.inverted ? 'var(--sell)' : 'var(--buy)', fontSize: '1rem' } },
          yields.inverted ? 'INVERTED' : 'NORMAL'
        ),
        h('div', { className: 'change', style: { color: 'var(--text-tertiary)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', marginTop: 2 } },
          yields.spread_2_10 != null ? `${yields.spread_2_10.toFixed(3)}%` : ''
        )
      )
    ),

    /* Correlations */
    h('div', { className: 'section-title', style: { marginTop: 20 } }, 'Pair Correlations'),
    h('div', { className: 'pairs-grid' },
      Object.entries(correlations || {}).map(([pair, corr]) =>
        h('div', { key: pair, className: 'pair-card', style: { cursor: 'default' } },
          h('div', { className: 'pair-name' }, pair),
          h('div', { style: { marginTop: 8 } },
            h('div', { style: { fontSize: '0.8rem' } },
              'DXY Correlation: ',
              h('strong', {
                style: {
                  fontFamily: 'var(--font-mono)',
                  color: (corr.dxy_correlation || 0) < -0.3 ? 'var(--sell)' : (corr.dxy_correlation || 0) > 0.3 ? 'var(--buy)' : 'var(--neutral)'
                }
              }, (corr.dxy_correlation || 0).toFixed(3))
            ),
            h('div', { style: { fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 2 } },
              `Relationship: ${(corr.relationship || 'neutral').toUpperCase()}  |  Strength: ${(corr.strength || 'none').toUpperCase()}`
            ),
            corr.estimated && h('div', { style: { fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2, fontStyle: 'italic' } },
              '* Estimated'
            )
          )
        )
      )
    ),

    /* CME Levels for all pairs */
    cmeAll && Object.keys(cmeAll).length > 0 && h('div', { style: { marginTop: 20 } },
      h('div', { className: 'section-title' }, 'CME Futures Overview'),
      h('div', { className: 'pairs-grid' },
        Object.entries(cmeAll).map(([pair, cmeData]) =>
          h('div', { key: pair, className: 'pair-card', style: { cursor: 'default' } },
            h('div', { className: 'pair-name' }, pair),
            h('div', { style: { display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' } },
              h('div', { style: { fontSize: '0.75rem' } },
                'Assessment: ',
                h('strong', {
                  style: { color: cmeData.assessment === 'bullish' ? 'var(--buy)' : cmeData.assessment === 'bearish' ? 'var(--sell)' : 'var(--neutral)' }
                }, (cmeData.assessment || 'neutral').toUpperCase())
              ),
              h('div', { style: { fontSize: '0.75rem' } },
                'Positioning: ',
                h('strong', null, (cmeData.futures?.positioning || '—').replace('_', ' ').toUpperCase())
              ),
              h('div', { style: { fontSize: '0.75rem' } },
                'Max Pain: ',
                h('strong', { style: { fontFamily: 'var(--font-mono)', fontSize: '0.7rem' } },
                  cmeData.options?.max_pain != null ? cmeData.options.max_pain.toFixed(5) : '—'
                )
              )
            )
          )
        )
      )
    )
  );
}

/* ── Main App ── */
function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [theme, setTheme] = useState('dark');
  const [status, setStatus] = useState('loading');
  const [overview, setOverview] = useState(null);
  const [signals, setSignals] = useState(null);
  const [setups, setSetups] = useState(null);
  const [news, setNews] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [regime, setRegime] = useState(null);
  const [cmeAll, setCmeAll] = useState(null);
  const [error, setError] = useState(null);
  const [detailPair, setDetailPair] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef(null);

  /* Load all data */
  const loadAll = useCallback(async () => {
    try {
      const [ov, sigs, setupsData, newsData, crossAsset, marketRegime, cme] = await Promise.all([
        fetchJSON('/market/overview').catch(() => ({})),
        fetchJSON('/signals/unified').catch(() => ({})),
        fetchJSON('/signals/setups?min_score=55').catch(() => []),
        fetchJSON('/news/upcoming?hours=72').catch(() => []),
        fetchJSON('/analysis/cross-asset').catch(() => ({})),
        fetchJSON('/analysis/regime').catch(() => ({})),
        fetchJSON('/cme').catch(() => ({})),
      ]);

      setOverview(ov);
      setSignals(sigs);
      setSetups(setupsData);
      setNews(newsData);
      setAnalysis(crossAsset);
      setRegime(marketRegime);
      setCmeAll(cme);
      setStatus('ok');
      setError(null);
    } catch (err) {
      setError(err.message);
      setStatus('error');
    } finally {
      setLoading(false);
    }
  }, []);

  /* Load detail data for a pair */
  const loadDetail = useCallback(async (pair) => {
    try {
      const data = await fetchJSON(`/signals/unified/${pair}`);
      return data;
    } catch (err) {
      return null;
    }
  }, []);

  /* Open detail panel */
  const openDetail = useCallback(async (pair, data) => {
    if (!data) {
      const d = await loadDetail(pair);
      setDetailPair(pair);
      setDetailData(d);
    } else {
      setDetailPair(pair);
      setDetailData(data);
    }
  }, [loadDetail]);

  const closeDetail = useCallback(() => {
    setDetailPair(null);
    setDetailData(null);
  }, []);

  /* Auto-refresh */
  useEffect(() => {
    loadAll();
    intervalRef.current = setInterval(loadAll, 30000);
    return () => clearInterval(intervalRef.current);
  }, [loadAll]);

  /* Theme */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme(t => t === 'dark' ? 'light' : 'dark');
  }, []);

  /* Loading state */
  if (loading) {
    return h('div', { className: 'app' },
      h(Nav, { activeTab, onTabChange: setActiveTab, theme, onThemeToggle: toggleTheme, status }),
      h('div', { className: 'main-content' },
        h(Loading, { text: 'Loading market data...' })
      )
    );
  }

  return h('div', { className: 'app' },
    h(Nav, { activeTab, onTabChange: setActiveTab, theme, onThemeToggle: toggleTheme, status }),

    h('div', { className: 'main-content' },
      h(ErrorMsg, { message: error }),

      activeTab === 'dashboard' && h(DashboardView, {
        overview,
        setups,
        regime,
        onPairClick: openDetail
      }),

      activeTab === 'signals' && h(SignalsView, {
        signals,
        onPairClick: openDetail
      }),

      activeTab === 'news' && h(NewsView, { events: news }),

      activeTab === 'analysis' && h(AnalysisView, {
        analysis,
        cmeAll,
        regime
      })
    ),

    /* Detail Panel */
    detailPair && h(SignalDetailPanel, {
      pair: detailPair,
      data: detailData,
      onClose: closeDetail
    })
  );
}

/* ── Mount ── */
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(h(App));
