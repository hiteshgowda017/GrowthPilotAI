import { motion } from 'framer-motion';
import { LayoutDashboard, TrendingUp, Compass, FileText, Zap } from 'lucide-react';

type TabName = 'workspace' | 'growth' | 'visibility' | 'reports';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: TabName) => void;
}

export default function Sidebar({ currentTab, setCurrentTab }: SidebarProps) {
  const tabs = [
    { id: 'workspace', label: 'Command Deck', icon: LayoutDashboard },
    { id: 'growth', label: 'Growth Intelligence', icon: TrendingUp },
    { id: 'visibility', label: 'Visibility Audit', icon: Compass },
    { id: 'reports', label: 'Executive Ledger', icon: FileText },
  ] as const;

  return (
    <aside className="w-72 fixed h-screen border-r border-white/[0.04] bg-[#050507]/80 backdrop-blur-3xl z-50 flex flex-col justify-between p-6">
      <div>
        <div className="flex items-center gap-3 px-2 py-3 mb-12 group cursor-pointer">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-blue-500 to-purple-500 flex items-center justify-center shadow-[0_0_30px_rgba(99,102,241,0.3)] relative overflow-hidden">
            <div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <Zap className="w-5 h-5 text-white fill-white/10" />
          </div>
          <div>
            <span className="font-extrabold text-base tracking-tight block bg-clip-text text-transparent bg-gradient-to-r from-white to-zinc-400">
              GrowthPilot AI
            </span>
            <span className="text-[10px] text-indigo-400/80 font-mono tracking-widest uppercase mt-0.5 block">
              Mission Control
            </span>
          </div>
        </div>
        
        <nav className="space-y-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentTab(tab.id as TabName)}
                className={`w-full flex items-center gap-3.5 px-4 py-3.5 rounded-xl text-sm font-medium transition-all duration-300 relative group ${
                  isActive ? 'text-white' : 'text-zinc-500 hover:text-zinc-200'
                }`}
              >
                {isActive && (
                  <motion.div 
                    layoutId="navGlow" 
                    className="absolute inset-0 bg-gradient-to-r from-indigo-500/15 to-purple-500/5 rounded-xl border border-indigo-500/30 shadow-[inset_0_0_12px_rgba(99,102,241,0.2)]" 
                  />
                )}
                <Icon className={`w-4 h-4 relative z-10 transition-colors duration-300 ${isActive ? 'text-indigo-400' : 'group-hover:text-zinc-300'}`} />
                <span className="relative z-10 tracking-wide">{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04] flex items-center gap-3">
        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
        <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-widest">Engine Online</span>
      </div>
    </aside>
  );
}