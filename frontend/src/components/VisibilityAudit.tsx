import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Radar, Target, Globe, AlertCircle, Loader2 } from 'lucide-react';

interface AuditProps {
  searchParams: {
    business_name: string;
    website: string;
    industry: string;
    location: string;
    goal: string;
  } | null;
}

interface VisibilityItem {
  name: string;
  score: number;
  evidence_level?: string;
  evidence_summary?: string;
  sources?: string[];
}

interface VisibilityData {
  target: VisibilityItem;
  local_competitors: VisibilityItem[];
  market_leaders: VisibilityItem[];
  insight_summary: string;
  research_coverage?: {
    status?: string;
    provider?: string;
    target_results?: number;
    local_candidates?: number;
    global_candidates?: number;
    target?: string;
    local?: string;
    global?: string;
  };
}

export default function VisibilityAudit({ searchParams }: AuditProps) {
  const [data, setData] = useState<VisibilityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'local' | 'global'>('local');
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    // Only run the audit if a real business name has been entered in the Command Deck
    if (!searchParams || !searchParams.business_name) return;

    const fetchVisibility = async () => {
      setLoading(true);
      setError('');
      try {
        // DYNAMIC URL LOGIC
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
        const response = await fetch(`${API_BASE_URL}/api/visibility-audit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(searchParams),
        });

        const responseText = await response.text();
        let result: any = null;

        try {
          result = responseText ? JSON.parse(responseText) : null;
        } catch {
          result = null;
        }

        if (!response.ok) {
          const backendMessage =
            result?.detail ||
            result?.message ||
            responseText ||
            `Visibility Engine returned HTTP ${response.status}.`;

          throw new Error(backendMessage);
        }

        if (!result) {
          throw new Error('Visibility Engine returned an empty response.');
        }

        setData(result);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchVisibility();
  }, [searchParams, retryCount]);

  // EMPTY STATE (This is what was broken in your pasted code!)
  if (!searchParams || !searchParams.business_name) {
    return (
      <div className="flex flex-col items-center justify-center h-96 border border-white/[0.05] rounded-2xl bg-[#0A0A0C]">
        <AlertCircle className="w-10 h-10 text-zinc-600 mb-4" />
        <h3 className="text-zinc-400 font-mono text-sm uppercase tracking-widest">Awaiting Command Input</h3>
        <p className="text-zinc-600 text-xs mt-2">Run a primary analysis from the Command Deck to generate a visibility footprint.</p>
      </div>
    );
  }

  // LOADING STATE
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 border border-white/[0.05] rounded-2xl bg-[#0A0A0C]">
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4" />
        <h3 className="text-indigo-400 font-mono text-sm uppercase tracking-widest animate-pulse">Scanning Global Footprints...</h3>
      </div>
    );
  }

  // ERROR STATE
  if (error) {
    return (
      <div className="p-6 border border-red-500/20 bg-red-500/5 rounded-2xl text-red-400 text-sm font-mono text-center">
        <div className="mb-4">{error}</div>
        <button
          onClick={() => setRetryCount((count) => count + 1)}
          className="px-4 py-2 rounded-lg border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 text-red-300 transition-colors"
        >
          Retry Live Audit
        </button>
      </div>
    );
  }

  if (!data) return null;

  // Determine which list to show based on the toggle
  const currentList = activeTab === 'local' ? data.local_competitors : data.market_leaders;
  
  // Combine target with the selected list, then sort by score descending
  const chartData = [data.target, ...currentList].sort((a, b) => b.score - a.score);

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-5xl mx-auto pb-20">
      
      {/* HEADER SECTION */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-2">
          <Radar className="w-5 h-5 text-indigo-400" />
          <h2 className="text-2xl font-bold text-white tracking-tight">Digital Visibility Audit</h2>
        </div>
        <p className="text-zinc-400 text-sm">Live web evidence, exact-input competitor discovery, and visibility comparison.</p>
      </div>

      {/* LIVE RESEARCH STATUS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-indigo-500/10 border border-indigo-500/20 p-4 rounded-xl">
          <div className="text-[10px] uppercase tracking-widest text-indigo-400 font-mono mb-1">Research source</div>
          <div className="text-sm text-white font-semibold">{data.research_coverage?.provider || 'DDGS'} • Live web</div>
        </div>
        <div className="bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-xl">
          <div className="text-[10px] uppercase tracking-widest text-emerald-400 font-mono mb-1">Target evidence</div>
          <div className="text-sm text-white font-semibold">{data.research_coverage?.target_results ?? '—'} live results</div>
        </div>
        <div className="bg-amber-500/10 border border-amber-500/20 p-4 rounded-xl">
          <div className="text-[10px] uppercase tracking-widest text-amber-400 font-mono mb-1">Competitor coverage</div>
          <div className="text-sm text-white font-semibold">
            {data.local_competitors.length} local • {data.market_leaders.length} top global
          </div>
        </div>
      </div>

      <div className="bg-indigo-500/10 border border-indigo-500/20 p-5 rounded-xl mb-8">
        <p className="text-indigo-200 text-sm leading-relaxed font-light">
          <strong className="text-indigo-400 font-semibold uppercase text-xs mr-2 font-mono">Live Diagnostic:</strong>
          {data.insight_summary}
        </p>
        <p className="text-zinc-500 text-[11px] mt-3 font-mono">
          Score is an evidence-based live-web visibility estimate — not market share, revenue, or business quality.
        </p>
      </div>

      <div className="bg-[#050507] border border-zinc-800/50 rounded-2xl shadow-2xl p-8">
        
        {/* INTERACTIVE TOGGLE BUTTONS */}
        <div className="flex items-center justify-center gap-4 mb-10 border-b border-zinc-800/50 pb-8">
          <button
            onClick={() => setActiveTab('local')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-mono font-bold transition-all duration-300 ${
              activeTab === 'local' 
                ? 'bg-indigo-600 text-white shadow-[0_0_20px_rgba(79,70,229,0.4)]' 
                : 'bg-zinc-900/50 text-zinc-500 hover:text-zinc-300 border border-zinc-800'
            }`}
          >
            <Target className="w-4 h-4" /> Vs Local Competitors
          </button>
          
          <button
            onClick={() => setActiveTab('global')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-mono font-bold transition-all duration-300 ${
              activeTab === 'global' 
                ? 'bg-emerald-600 text-white shadow-[0_0_20px_rgba(5,150,105,0.4)]' 
                : 'bg-zinc-900/50 text-zinc-500 hover:text-zinc-300 border border-zinc-800'
            }`}
          >
            <Globe className="w-4 h-4" /> Vs Top Global Competitors
          </button>
        </div>

        {/* LIVE VISIBILITY GRAPH */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-white font-semibold text-sm">Live Visibility Comparison</h3>
              <p className="text-zinc-500 text-[11px] mt-1">
                {activeTab === 'local'
                  ? 'Target business vs locally relevant competitors discovered from live search.'
                  : 'Target business vs the strongest globally relevant competitors discovered from live search.'}
              </p>
            </div>
            <span className="text-[10px] uppercase tracking-widest text-zinc-600 font-mono">0–100</span>
          </div>

          {chartData.length === 0 ? (
            <div className="py-16 text-center border border-white/[0.05] rounded-xl bg-zinc-950/40">
              <div className="text-zinc-400 text-sm font-semibold mb-2">
                No verified {activeTab === 'local' ? 'local' : 'global'} competitors found
              </div>
              <div className="text-zinc-600 text-xs max-w-md mx-auto leading-relaxed">
                GrowthPilot will not fabricate a competitor to fill the graph. Broader
                live research or a more specific market input may be required.
              </div>
            </div>
          ) : (
          <div className="space-y-6">
            {chartData.map((item, index) => {
              const isTarget = item.name === data.target.name;
              return (
                <div key={index} className="flex flex-col gap-2">
                  <div className="flex justify-between items-center text-xs font-mono">
                    <span className={`${isTarget ? 'text-indigo-400 font-bold' : 'text-zinc-400'}`}>
                      {index + 1}. {item.name} {isTarget && '(Target)'}
                    </span>
                    <span className={`${isTarget ? 'text-indigo-400' : 'text-zinc-500'}`}>
                      {item.score} / 100
                    </span>
                  </div>
                  <div className="w-full bg-zinc-900 rounded-full h-3 overflow-hidden border border-zinc-800">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}
                      transition={{ duration: 0.9, delay: index * 0.08, ease: "easeOut" }}
                      className={`h-full rounded-full ${
                        isTarget
                          ? 'bg-gradient-to-r from-indigo-600 to-indigo-400'
                          : activeTab === 'local'
                            ? 'bg-gradient-to-r from-zinc-700 to-zinc-500'
                            : 'bg-gradient-to-r from-emerald-700 to-emerald-400'
                      }`}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-zinc-600 font-mono">
                    <span>{item.evidence_level || 'Live evidence'}</span>
                    <span>{item.sources?.length || 0} source URL{(item.sources?.length || 0) === 1 ? '' : 's'}</span>
                  </div>
                </div>
              );
            })}
          </div>
          )}
        </div>

        {chartData.length > 0 && (
          <div className="mt-8 pt-6 border-t border-zinc-800/50">
            <h4 className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono mb-4">
              Evidence Sources
            </h4>
            <div className="space-y-3">
              {chartData.flatMap(item => (item.sources || []).map(source => ({ name: item.name, source }))).map((entry, i) => (
                <a
                  key={i}
                  href={entry.source}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-[11px] text-zinc-500 hover:text-indigo-300 transition-colors break-all"
                >
                  {entry.name} — {entry.source}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}