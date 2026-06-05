import React, { useState } from 'react';
import axios from 'axios';
import { AnimatePresence } from 'framer-motion';

import Sidebar from './components/Sidebar';
import CommandDeck from './components/CommandDeck';
import IntelligenceMatrix from './components/IntelligenceMatrix';
import VisibilityAudit from './components/VisibilityAudit';
import ExecutiveLedger from './components/ExecutiveLedger';

export default function App() {
  const [currentTab, setCurrentTab] = useState<'workspace' | 'growth' | 'visibility' | 'reports'>('workspace');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any>(null);

  const [formData, setFormData] = useState({
    business_name: '', website: '', industry: '', location: '', goal: ''
  });

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
      const response = await axios.post(`${API_BASE_URL}/api/growth-analysis`, formData);
      setAnalysisResult(response.data);
      setCurrentTab('growth'); 
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Engine timeout or network isolation error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-[#030303] overflow-x-hidden selection:bg-zinc-800 selection:text-white">
      
      <Sidebar currentTab={currentTab} setCurrentTab={setCurrentTab} />

      {/* MOBILE RESPONSIVE FIX: md:ml-72 adds margin ONLY on desktop. pb-32 adds scroll room for the mobile bottom nav. */}
      <main className="flex-1 w-full md:ml-72 p-4 md:p-12 pb-32 md:pb-12 relative min-h-screen">
        <div className="absolute top-[-10%] left-[30%] w-[600px] h-[600px] bg-gradient-to-br from-zinc-800/10 to-transparent rounded-full blur-[140px] pointer-events-none" />

        <AnimatePresence mode="wait">
          
          {currentTab === 'workspace' && (
            <CommandDeck 
              formData={formData} 
              setFormData={setFormData} 
              handleAnalyze={handleAnalyze} 
              isLoading={isLoading} 
              error={error} 
            />
          )}

          {currentTab === 'growth' && (
            <IntelligenceMatrix data={analysisResult} businessName={formData.business_name} />
          )}
          
          {currentTab === 'visibility' && (
            <VisibilityAudit searchParams={formData} />
          )}

          {currentTab === 'reports' && (
            <ExecutiveLedger />
          )}

        </AnimatePresence>
      </main>
    </div>
  );
}