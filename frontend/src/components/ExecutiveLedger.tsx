import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Trash2, Calendar, Building2, ChevronRight, Terminal } from 'lucide-react';
import IntelligenceMatrix from './IntelligenceMatrix';

interface SavedReport {
  id: string;
  date: string;
  name: string;
  data: any;
}

export default function ExecutiveLedger() {
  const [reports, setReports] = useState<SavedReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<SavedReport | null>(null);

  useEffect(() => {
    const saved = JSON.parse(localStorage.getItem('growthpilot_ledger') || '[]');
    setReports(saved);
  }, []);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = reports.filter(r => r.id !== id);
    setReports(updated);
    localStorage.setItem('growthpilot_ledger', JSON.stringify(updated));
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-5xl mx-auto pb-20 relative">
      
      {/* Header */}
      {!selectedReport && (
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <h2 className="text-2xl font-bold text-white tracking-tight">Executive Ledger</h2>
          </div>
          <p className="text-zinc-400 text-sm">Historical repository of all generated corporate intelligence reports.</p>
        </div>
      )}

      {/* Empty State */}
      {reports.length === 0 && !selectedReport && (
        <div className="flex flex-col items-center justify-center h-96 border border-white/[0.05] rounded-2xl bg-[#0A0A0C]">
          <Database className="w-10 h-10 text-zinc-700 mb-4" />
          <h3 className="text-zinc-400 font-mono text-sm uppercase tracking-widest">Storage Node Empty</h3>
          <p className="text-zinc-600 text-xs mt-2">Generate and save a report from the Command Deck to populate the ledger.</p>
        </div>
      )}

      {/* List State */}
      {!selectedReport && reports.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          <AnimatePresence>
            {reports.map((report) => (
              <motion.div 
                key={report.id}
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                onClick={() => setSelectedReport(report)}
                className="group flex items-center justify-between p-6 bg-[#050507] border border-zinc-800/50 hover:border-indigo-500/30 hover:bg-indigo-500/5 rounded-2xl cursor-pointer transition-all duration-300"
              >
                <div className="flex items-center gap-6">
                  <div className="w-12 h-12 rounded-xl bg-zinc-900 flex items-center justify-center border border-zinc-800 group-hover:border-indigo-500/30 group-hover:text-indigo-400 transition-colors">
                    <Building2 className="w-5 h-5 text-zinc-500 group-hover:text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white mb-1 group-hover:text-indigo-100 transition-colors">{report.name}</h3>
                    <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
                      <Calendar className="w-3.5 h-3.5" /> {report.date}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <button 
                    onClick={(e) => handleDelete(report.id, e)}
                    className="p-2 text-zinc-600 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                    title="Delete Record"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                  <div className="p-2 text-zinc-600 group-hover:text-indigo-400 transition-colors">
                    <ChevronRight className="w-5 h-5" />
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* View Mode Overlay (Scroll Fix Applied) */}
      {selectedReport && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full">
          
          <div className="flex items-center justify-between mb-8 pb-6 border-b border-zinc-800/50">
            <div>
              <button 
                onClick={() => setSelectedReport(null)}
                className="text-indigo-400 hover:text-indigo-300 text-sm font-mono flex items-center gap-2 mb-3 transition-colors"
              >
                <ChevronRight className="w-4 h-4 rotate-180" /> Return to Ledger
              </button>
              <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
                <Terminal className="w-5 h-5 text-zinc-500" /> {selectedReport.name} Archive
              </h2>
            </div>
          </div>

          {/* Pointer events restored so you can scroll freely! */}
          <div className="mt-4 pb-20"> 
            <IntelligenceMatrix data={selectedReport.data} businessName={selectedReport.name} />
          </div>
          
        </motion.div>
      )}

    </motion.div>
  );
}