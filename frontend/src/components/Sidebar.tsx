import { LayoutGrid, TrendingUp, Radar, FileText, Zap } from 'lucide-react';

interface SidebarProps {
  currentTab: 'workspace' | 'growth' | 'visibility' | 'reports';
  setCurrentTab: (tab: 'workspace' | 'growth' | 'visibility' | 'reports') => void;
}

export default function Sidebar({ currentTab, setCurrentTab }: SidebarProps) {
  const tabs = [
    { id: 'workspace', label: 'Command Deck', icon: LayoutGrid },
    { id: 'growth', label: 'Growth Intelligence', icon: TrendingUp },
    { id: 'visibility', label: 'Visibility Audit', icon: Radar },
    { id: 'reports', label: 'Executive Ledger', icon: FileText }
  ] as const;

  return (
    <>
      {/* ======================================= */}
      {/* DESKTOP SIDEBAR (Hidden on mobile)      */}
      {/* ======================================= */}
      <div className="hidden md:flex fixed top-0 left-0 h-screen w-72 bg-[#050507] border-r border-zinc-800/50 flex-col z-50">
        <div className="p-8 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-[0_0_20px_rgba(79,70,229,0.4)]">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold tracking-tight text-lg leading-tight">GrowthPilot AI</h1>
            <p className="text-[#4F46E5] text-[10px] uppercase tracking-widest font-mono font-bold">Mission Control</p>
          </div>
        </div>

        <nav className="flex-1 px-4 space-y-2 mt-4">
          {tabs.map((tab) => {
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentTab(tab.id as any)}
                className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all duration-300 ${
                  isActive 
                    ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.05)]' 
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50 border border-transparent'
                }`}
              >
                <tab.icon className={`w-5 h-5 ${isActive ? 'text-indigo-400' : 'text-zinc-600'}`} />
                <span className="text-sm font-semibold">{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* ======================================= */}
      {/* MOBILE BOTTOM NAV (Hidden on desktop)   */}
      {/* ======================================= */}
      <div className="md:hidden fixed bottom-0 left-0 w-full bg-[#050507]/95 backdrop-blur-xl border-t border-zinc-800/50 z-50 px-2 py-3 pb-safe">
        <div className="flex items-center justify-around">
          {tabs.map((tab) => {
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentTab(tab.id as any)}
                className="flex flex-col items-center gap-1.5 p-2 w-16"
              >
                <div className={`p-2 rounded-xl transition-all duration-300 ${isActive ? 'bg-indigo-500/20' : 'bg-transparent'}`}>
                  <tab.icon className={`w-5 h-5 ${isActive ? 'text-indigo-400' : 'text-zinc-500'}`} />
                </div>
                {/* We split the label to just show the first word on small mobile screens */}
                <span className={`text-[10px] font-semibold tracking-wide text-center leading-none ${isActive ? 'text-indigo-400' : 'text-zinc-600'}`}>
                  {tab.label.split(' ')[0]} 
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}