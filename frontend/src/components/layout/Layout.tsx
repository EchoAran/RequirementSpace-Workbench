import React from 'react';
import { LeftNav } from './LeftNav';
import { TopBar } from './TopBar';

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 font-sans text-slate-900">
      <LeftNav />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-x-hidden overflow-y-auto w-full flex">
          {children}
        </main>
      </div>
    </div>
  );
}
