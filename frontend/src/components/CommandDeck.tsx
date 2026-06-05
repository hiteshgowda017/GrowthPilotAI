import { useState } from 'react';
import type { FormEvent } from 'react';
import { motion } from 'framer-motion';
import { Briefcase, Globe, Search, MapPin, Target, Loader2, ChevronRight, AlertTriangle } from 'lucide-react';

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } }
};

interface CommandDeckProps {
  formData: any;
  setFormData: (data: any) => void;
  handleAnalyze: (e: FormEvent) => void;
  isLoading: boolean;
  error: string | null;
}

export default function CommandDeck({ formData, setFormData, handleAnalyze, isLoading, error }: CommandDeckProps) {
  const [focusedField, setFocusedField] = useState<string | null>(null);

  return (
    <motion.div 
      key="workspace" 
      initial="hidden" animate="show" exit={{ opacity: 0 }}
      className="max-w-4xl mx-auto space-y-12 pt-6 pb-20 font-sans"
    >
      <motion.div variants={itemVariants} className="space-y-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="h-2 w-2 rounded-full bg-zinc-400" />
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">System Architecture Online</span>
        </div>
        <h1 className="text-5xl md:text-6xl font-medium tracking-tight text-white leading-tight">
          Accelerate Valuation. <br />Compute Market Gaps.
        </h1>
        <p className="text-zinc-400 text-lg max-w-2xl leading-relaxed">
          GrowthPilot scans the global web index to reveal missing feature voids, competitor metrics, and strategic dominance playbooks.
        </p>
      </motion.div>

      <motion.div 
        variants={itemVariants} 
        className="bg-[#0A0A0A] rounded-2xl p-8 md:p-10 border border-white/[0.06]"
      >
        <form onSubmit={handleAnalyze} className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { label: "Target Corporation Name", icon: Briefcase, key: "business_name", placeholder: "e.g. Stripe" },
              { label: "Production Domain URL", icon: Globe, key: "website", placeholder: "stripe.com" },
              { label: "Market Vertical / Sector", icon: Search, key: "industry", placeholder: "Fintech Payments" },
              { label: "Geographic Vector Hub", icon: MapPin, key: "location", placeholder: "San Francisco, CA" }
            ].map((f) => (
              <div key={f.key} className="space-y-2.5">
                <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">
                  {f.label}
                </label>
                <div className="relative group">
                  <f.icon className={`absolute left-4 top-4 w-4 h-4 transition-colors duration-200 ${focusedField === f.key ? 'text-white' : 'text-zinc-600'}`} />
                  <input 
                    required 
                    type="text" 
                    placeholder={f.placeholder}
                    onFocus={() => setFocusedField(f.key)}
                    onBlur={() => setFocusedField(null)}
                    className="w-full bg-zinc-900/50 border border-white/[0.04] rounded-xl pl-12 pr-4 py-3.5 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500 focus:bg-zinc-900 transition-all duration-200"
                    value={formData[f.key]} 
                    onChange={e => setFormData({...formData, [f.key]: e.target.value})}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-2.5">
            <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">
              Primary Operational Objective
            </label>
            <div className="relative group">
              <Target className={`absolute left-4 top-4 w-4 h-4 transition-colors duration-200 ${focusedField === 'goal' ? 'text-white' : 'text-zinc-600'}`} />
              <textarea 
                required 
                rows={3} 
                placeholder="Describe user acquisition thresholds or monetization target layers..."
                onFocus={() => setFocusedField('goal')}
                onBlur={() => setFocusedField(null)}
                className="w-full bg-zinc-900/50 border border-white/[0.04] rounded-xl pl-12 pr-4 py-4 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500 focus:bg-zinc-900 transition-all duration-200 resize-none leading-relaxed"
                value={formData.goal} 
                onChange={e => setFormData({...formData, goal: e.target.value})}
              />
            </div>
          </div>

          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium rounded-xl flex items-center gap-3">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
            </motion.div>
          )}

          <div className="pt-2">
            <button
              type="submit" 
              disabled={isLoading}
              className="w-full bg-white text-black font-semibold py-4 px-6 rounded-xl hover:bg-zinc-200 active:scale-[0.99] transition-all duration-200 flex items-center justify-center gap-2.5 disabled:opacity-50 disabled:active:scale-100 text-sm tracking-wide"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-black" />
                  <span>Processing Analysis...</span>
                </>
              ) : (
                <>
                  <span>Execute Intelligence Command Loop</span>
                  <ChevronRight className="w-4 h-4 text-black" />
                </>
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}