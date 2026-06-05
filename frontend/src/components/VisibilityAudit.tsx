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

interface VisibilityData {
  target: { name: string; score: number };
  local_competitors: { name: string; score: number }[];
  market_leaders: { name: string; score: number }[];
  insight_summary: string;
}

export default function VisibilityAudit({ searchParams }: AuditProps) {
  const [data, setData] = useState<VisibilityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'local' | 'global'>('local');

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

        if (!response.ok) throw new Error('Visibility Engine failed to respond or was rate-limited.');
        const result = await response.json();
        setData(result);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchVisibility();
  }, [searchParams]);

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
        {error}
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
        <p className="text-zinc-400 text-sm">Aggregated search engine footprint and social media dominance index.</p>
      </div>

      {/* AI INSIGHT SUMMARY */}
      <div className="bg-indigo-500/10 border border-indigo-500/20 p-5 rounded-xl mb-8">
        <p className="text-indigo-200 text-sm leading-relaxed font-light">
          <strong className="text-indigo-400 font-semibold uppercase text-xs mr-2 font-mono">AI Diagnostic:</strong>
          {data.insight_summary}
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
            <Target className="w-4 h-4" /> Vs Local Independent Competitors
          </button>
          
          <button
            onClick={() => setActiveTab('global')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-mono font-bold transition-all duration-300 ${
              activeTab === 'global' 
                ? 'bg-emerald-600 text-white shadow-[0_0_20px_rgba(5,150,105,0.4)]' 
                : 'bg-zinc-900/50 text-zinc-500 hover:text-zinc-300 border border-zinc-800'
            }`}
          >
            <Globe className="w-4 h-4" /> Vs Macro Market Leaders
          </button>
        </div>

        {/* NATIVE TAILWIND BAR CHART */}
        <div className="space-y-6">
          {chartData.map((item, index) => {
            const isTarget = item.name === data.target.name;
            return (
              <div key={index} className="flex flex-col gap-2">
                <div className="flex justify-between items-center text-xs font-mono">
                  <span className={`${isTarget ? 'text-indigo-400 font-bold' : 'text-zinc-400'}`}>
                    {index + 1}. {item.name} {isTarget && '(You)'}
                  </span>
                  <span className={`${isTarget ? 'text-indigo-400' : 'text-zinc-500'}`}>
                    {item.score} / 100
                  </span>
                </div>
                
                {/* Chart Track */}
                <div className="w-full bg-zinc-900 rounded-full h-3 overflow-hidden border border-zinc-800">
                  {/* Chart Fill (Animated) */}
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${item.score}%` }}
                    transition={{ duration: 1, delay: index * 0.1, ease: "easeOut" }}
                    className={`h-full rounded-full ${
                      isTarget 
                        ? 'bg-gradient-to-r from-indigo-600 to-indigo-400' 
                        : 'bg-gradient-to-r from-zinc-700 to-zinc-500'
                    }`}
                  />
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </motion.div>
  );
}