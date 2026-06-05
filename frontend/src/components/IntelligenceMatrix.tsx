import { useState } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Download, Crosshair, Radar, TrendingUp, ShieldAlert, Save, Check, FileText } from 'lucide-react';
// @ts-ignore
import html2pdf from 'html2pdf.js';

interface MatrixProps {
  data: Record<string, unknown> | null;
  businessName?: string;
}

export default function IntelligenceMatrix({ data, businessName = "Unknown Business" }: MatrixProps) {
  const [isSaved, setIsSaved] = useState(false);

  if (!data) return null;

  const metrics = (data.metrics as Record<string, string>) || {};
  const rawReport = (data.report_markdown as string) || '';

  const handleSaveToLedger = () => {
    const existing = JSON.parse(localStorage.getItem('growthpilot_ledger') || '[]');
    const newReport = {
      id: Date.now().toString(),
      date: new Date().toLocaleDateString(),
      name: businessName,
      data: data
    };
    localStorage.setItem('growthpilot_ledger', JSON.stringify([newReport, ...existing]));
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handleDownloadPDF = () => {
    const element = document.getElementById('growthpilot-pdf-content');
    if (!element) return;

    // Temporarily unroll the scroll box and force a hard dark background
    element.classList.remove('max-h-[750px]', 'overflow-y-auto');
    element.classList.add('h-auto', 'overflow-visible', 'bg-[#050507]');

    const opt: any = {
      margin: 0.5,
      filename: `${businessName.replace(/\s+/g, '-')}-Growth-Plan.pdf`,
      image: { type: 'jpeg', quality: 1 },
      html2canvas: { 
        scale: 2, 
        backgroundColor: '#050507', 
        useCORS: true,
        scrollY: 0 
      }, 
      jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' },
      // THE MAGIC FIX: Prevents text slicing and forces each Phase to a new page!
      pagebreak: { mode: ['avoid-all', 'css'], before: '.phase-header' }
    };

    // Generate the PDF, then immediately roll the UI back up
    html2pdf().set(opt).from(element).save().then(() => {
      element.classList.add('max-h-[750px]', 'overflow-y-auto');
      element.classList.remove('h-auto', 'overflow-visible', 'bg-[#050507]');
    });
  };

  const formatReportText = (text: string) => {
    return text.split('\n').map((line, index) => {
      if (line.startsWith('# ===') || line.startsWith('# ')) {
        return <h1 key={index} className="text-3xl font-extrabold tracking-tight text-white border-b border-zinc-800 pb-6 mt-8 mb-8">{line.replace(/[#=]/g, '').trim()}</h1>;
      }
      if (line.startsWith('## Phase')) {
        // ADDED 'phase-header' CLASS HERE TO TRIGGER THE PAGE BREAK
        return <h2 key={index} className="phase-header text-xl font-bold tracking-tight text-indigo-400 mt-12 mb-6 flex items-center gap-3 bg-indigo-500/10 py-3 px-4 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.1)]">{line.replace(/[##*]/g, '').trim()}</h2>;
      }
      if (line.startsWith('### ')) {
        return <h3 key={index} className="text-sm font-bold uppercase tracking-widest font-mono text-zinc-300 mt-8 mb-4 border-l-2 border-emerald-500 pl-3">{line.replace(/[###*]/g, '').trim()}</h3>;
      }
      if (line.trim().startsWith('*') || line.trim().startsWith('-')) {
        return (
          <div key={index} className="flex items-start gap-3 ml-2 my-3 text-zinc-300 text-sm leading-relaxed">
            <span className="text-indigo-500 mt-1.5 shrink-0 text-lg leading-none">•</span>
            <span dangerouslySetInnerHTML={{ __html: line.replace(/^[*-\s]+/, '').replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>') }} />
          </div>
        );
      }
      if (line.trim() === '') return <div key={index} className="h-4" />;
      return <p key={index} className="text-sm text-zinc-300 leading-relaxed font-light mb-6 text-justify" dangerouslySetInnerHTML={{ __html: line.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>') }} />;
    });
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="max-w-7xl mx-auto pb-32 font-sans">
      
      {/* HUD METRICS */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
        {[
          { label: "Market Standing Rank", val: metrics.market_rank || "Calculating...", icon: ShieldAlert, color: "from-amber-500/10 to-amber-500/5 border-amber-500/20 text-amber-400" },
          { label: "AI Recommendation Index", val: metrics.ai_visibility_score ? `${metrics.ai_visibility_score} / 100` : "Scanning...", icon: Radar, color: "from-indigo-500/10 to-indigo-500/5 border-indigo-500/20 text-indigo-400" },
          { label: "Competitor Vulnerability", val: metrics.vulnerability_score ? `${metrics.vulnerability_score} / 100` : "Hunting...", icon: Crosshair, color: "from-rose-500/10 to-rose-500/5 border-rose-500/20 text-rose-400" },
          { label: "Apex Growth Vector", val: metrics.top_opportunity || "Computing...", icon: TrendingUp, color: "from-emerald-500/10 to-emerald-500/5 border-emerald-500/20 text-emerald-400" }
        ].map((m, i) => (
          <div key={i} className={`p-5 rounded-2xl border bg-gradient-to-br ${m.color} backdrop-blur-xl shadow-lg relative overflow-hidden group`}>
            <div className="absolute top-0 right-0 p-4 opacity-20 group-hover:opacity-40 transition-opacity duration-500"><m.icon className="w-12 h-12" /></div>
            <div className="relative z-10 flex flex-col h-full justify-between gap-4">
              <span className="text-[10px] uppercase tracking-widest opacity-80 font-mono font-semibold">{m.label}</span>
              <span className="text-lg font-bold tracking-tight text-white leading-tight">{m.val}</span>
            </div>
          </div>
        ))}
      </div>

      {/* STRATEGY CONSOLE */}
      <div className="bg-[#050507] border border-zinc-800/50 rounded-2xl shadow-2xl overflow-hidden">
        
        {/* HEADER BAR & BUTTONS */}
        <div className="flex items-center justify-between bg-zinc-900/40 border-b border-zinc-800/50 px-8 py-5">
          <div className="flex items-center gap-3">
            <Terminal className="w-4 h-4 text-emerald-500" />
            <span className="text-xs font-mono uppercase tracking-widest text-zinc-300 font-semibold">GrowthPilot Strategic Core</span>
          </div>
          
          <div className="flex gap-3">
            <button 
              onClick={handleSaveToLedger}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono transition-all active:scale-95 ${isSaved ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-[0_0_15px_rgba(79,70,229,0.3)]'}`}
            >
              {isSaved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />} 
              {isSaved ? 'Saved to Ledger' : 'Save to Ledger'}
            </button>
            
            <button 
              onClick={handleDownloadPDF}
              className="flex items-center gap-2 px-4 py-2 bg-white/10 border border-white/20 hover:bg-white/20 rounded-lg text-xs font-mono text-white transition-all active:scale-95"
            >
              <Download className="w-3.5 h-3.5" /> PDF
            </button>

            <button 
              onClick={() => {
                const blob = new Blob([rawReport], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${businessName.replace(/\s+/g, '-')}-Growth-Plan.md`;
                a.click();
              }}
              className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg text-xs font-mono text-white transition-all active:scale-95"
            >
              <FileText className="w-3.5 h-3.5" /> MD
            </button>
          </div>
        </div>

        {/* DOCUMENT VIEW */}
        <div id="growthpilot-pdf-content" className="p-8 md:p-14 max-h-[750px] overflow-y-auto custom-scrollbar transition-all duration-300">
          <div className="prose prose-invert max-w-none">
            {rawReport ? formatReportText(rawReport) : (
              <div className="text-zinc-500 text-sm font-mono flex items-center justify-center py-40 animate-pulse">Awaiting GrowthPilot activation stream...</div>
            )}
          </div>
        </div>

      </div>
    </motion.div>
  );
}