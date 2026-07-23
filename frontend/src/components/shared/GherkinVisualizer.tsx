import { useTranslation } from 'react-i18next';
import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

export interface GherkinClause {
  keyword: 'Given' | 'When' | 'Then' | 'And' | 'But';
  content: string;
}

export interface GherkinParsed {
  clauses: GherkinClause[];
  examples?: { headers: string[]; rows: string[][] };
  boundary?: string;
  businessMeaning?: string;
}

// Robust parser for Gherkin and custom annotations
export function parseGherkin(text: string): GherkinParsed {
  if (!text) {
    return { clauses: [] };
  }

  let cleanText = text;
  let examples: { headers: string[]; rows: string[][] } | undefined = undefined;
  let boundary: string | undefined = undefined;

  // 1. Extract Examples
  const examplesIndex = cleanText.indexOf('Examples:');
  if (examplesIndex !== -1) {
    const examplesStr = cleanText.substring(examplesIndex + 9).trim();
    cleanText = cleanText.substring(0, examplesIndex).trim();
    try {
      if (examplesStr.startsWith('[') || examplesStr.startsWith('{')) {
        const parsed = JSON.parse(examplesStr);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const first = parsed[0];
          if (first.Headers && first.Rows) {
            examples = { headers: first.Headers, rows: first.Rows };
          } else {
            const headers = Object.keys(first);
            const rows = parsed.map((item: any) => headers.map(h => String(item[h] ?? '')));
            examples = { headers, rows };
          }
        } else if (parsed.Headers && parsed.Rows) {
          examples = { headers: parsed.Headers, rows: parsed.Rows };
        }
      }
    } catch (e) {
      console.warn("Failed to parse Gherkin Examples:", e);
    }
  }

  // 2. Extract Boundary
  const boundaryRegex = /Boundary:\s*([^\n\r,]+)/i;
  const boundaryMatch = cleanText.match(boundaryRegex);
  if (boundaryMatch) {
    boundary = boundaryMatch[1].trim();
    cleanText = cleanText.replace(boundaryRegex, '').trim();
  }

  // 3. Parse clauses
  const clauseRegex = /\b(Given|When|Then|And|But)\b/gi;
  const clauses: GherkinClause[] = [];
  
  let match;
  const matches: { keyword: string; index: number }[] = [];
  while ((match = clauseRegex.exec(cleanText)) !== null) {
    matches.push({ keyword: match[0], index: match.index });
  }

  if (matches.length === 0) {
    // Treat whole text as business meaning if no Gherkin keywords
    return {
      clauses: [],
      boundary,
      examples,
      businessMeaning: cleanText.replace(/^[,.\s]+|[,.\s]+$/g, '').trim()
    };
  }

  for (let i = 0; i < matches.length; i++) {
    const current = matches[i];
    const next = matches[i + 1];
    const start = current.index + current.keyword.length;
    const end = next ? next.index : cleanText.length;
    
    let content = cleanText.substring(start, end).trim();
    content = content.replace(/^[,.\s]+|[,.\s]+$/g, '').trim();
    
    const kw = current.keyword.charAt(0).toUpperCase() + current.keyword.slice(1).toLowerCase();
    clauses.push({
      keyword: kw as any,
      content
    });
  }

  return {
    clauses,
    boundary,
    examples
  };
}

// Stringbuilder back to Gherkin syntax
export function stringifyGherkin(
  clauses: GherkinClause[],
  boundary?: string,
  examples?: { headers: string[]; rows: string[][] }
): string {
  let parts = clauses.map(c => `${c.keyword} ${c.content}`);
  let text = parts.join(', ');

  if (boundary && boundary.trim()) {
    text += `, Boundary: ${boundary.trim()}`;
  }

  if (examples && examples.headers && examples.headers.length > 0 && examples.rows && examples.rows.length > 0) {
    const serialized = { Headers: examples.headers, Rows: examples.rows };
    text += `, Examples: ${JSON.stringify(serialized)}`;
  }

  return text;
}

// Highlight variables like @variable and <parameter>
export function renderHighlightedText(content: string) {
  if (!content) return '';
  const regex = /(<[^>]+>|@[a-zA-Z0-9_.-]+)/g;
  const parts = content.split(regex);
  if (parts.length === 1) return content;

  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith('<') && part.endsWith('>')) {
          const varName = part.slice(1, -1);
          return (
            <span key={index} className="inline-flex items-center px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200/50 mx-0.5 font-mono text-[10px] font-bold">
              {varName}
            </span>
          );
        } else if (part.startsWith('@')) {
          const varName = part.slice(1);
          return (
            <span key={index} className="inline-flex items-center px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200/50 mx-0.5 font-mono text-[10px] font-bold">
              @{varName}
            </span>
          );
        }
        return part;
      })}
    </>
  );
}

// Structured Gherkin Visualizer Renderer
export const GherkinVisualRenderer: React.FC<{
  text: string;
  title: string;
  badge?: string;
  statusBadge?: React.ReactNode;
  rightBadges?: React.ReactNode[];
  onClick?: () => void;
}> = ({ text, title, badge, statusBadge, rightBadges, onClick }) => {
  const { t } = useTranslation();
  const parsed = parseGherkin(text);
  const { clauses, examples, boundary, businessMeaning } = parsed;

  // Group clauses logically to match standard Given / When / Then layout
  const givenClauses: GherkinClause[] = [];
  const whenClauses: GherkinClause[] = [];
  const thenClauses: GherkinClause[] = [];

  let currentCategory: 'Given' | 'When' | 'Then' | null = null;

  for (const clause of clauses) {
    if (clause.keyword === 'Given') {
      currentCategory = 'Given';
      givenClauses.push(clause);
    } else if (clause.keyword === 'When') {
      currentCategory = 'When';
      whenClauses.push(clause);
    } else if (clause.keyword === 'Then') {
      currentCategory = 'Then';
      thenClauses.push(clause);
    } else if (clause.keyword === 'And' || clause.keyword === 'But') {
      if (currentCategory === 'Given') {
        givenClauses.push(clause);
      } else if (currentCategory === 'When') {
        whenClauses.push(clause);
      } else if (currentCategory === 'Then') {
        thenClauses.push(clause);
      } else {
        // Fallback if leading clause is And/But
        givenClauses.push(clause);
      }
    }
  }

  return (
    <div 
      onClick={onClick}
      className={`border border-slate-200 rounded-2xl bg-white shadow-sm p-4 hover:shadow-md hover:border-indigo-300 transition-all select-text ${
        onClick ? 'cursor-pointer' : ''
      }`}
    >
      {/* Header Badges */}
      <div className="flex flex-wrap justify-between items-center gap-2 mb-3.5 pb-2.5 border-b border-slate-100/80">
        <div className="flex items-center gap-2">
          {badge && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[9px] font-extrabold uppercase tracking-wider bg-purple-50 text-purple-600 border border-purple-100">
              {badge}
            </span>
          )}
          <span className="font-extrabold text-slate-800 text-xs tracking-tight">{title}</span>
          {statusBadge}
        </div>
        
        {rightBadges && rightBadges.length > 0 && (
          <div className="flex items-center gap-1.5">
            {rightBadges.map((rb, idx) => (
              <div key={idx} className="inline-flex items-center">
                {rb}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Structured Card Grid */}
      {clauses.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {/* GIVEN Column */}
          <div className="bg-slate-50/40 border border-slate-200 rounded-xl p-3 space-y-2">
            <span className="text-[10px] text-slate-500 font-extrabold uppercase tracking-wider block">GIVEN</span>
            {givenClauses.length > 0 ? (
              givenClauses.map((c, i) => {
                const isMain = c.keyword === 'Given';
                return (
                  <div 
                    key={i} 
                    className={`text-xs leading-relaxed flex items-start ${
                      isMain 
                        ? 'text-slate-700 font-semibold mt-1' 
                        : 'text-slate-500 font-medium pl-3 border-l border-slate-200/60 ml-1 mt-0.5'
                    }`}
                  >
                    {isMain ? (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-sky-400 mr-1.5 mt-1.5 shrink-0" />
                    ) : (
                      <span className={`inline-block w-1 h-1 rounded-full mr-1.5 mt-1.5 shrink-0 ${
                        c.keyword === 'But' ? 'bg-rose-350' : 'bg-slate-350'
                      }`} />
                    )}
                    <div>
                      {!isMain && (
                        <span className="text-[9px] font-extrabold uppercase mr-1 text-slate-400 font-mono tracking-wider">
                          {c.keyword}
                        </span>
                      )}
                      {renderHighlightedText(c.content)}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-xs text-slate-400 italic">{t('gherkinVisualizer.noGiven')}</div>
            )}
          </div>

          {/* WHEN Column */}
          <div className="bg-slate-50/40 border border-slate-200 rounded-xl p-3 space-y-2">
            <span className="text-[10px] text-slate-500 font-extrabold uppercase tracking-wider block">WHEN</span>
            {whenClauses.length > 0 ? (
              whenClauses.map((c, i) => {
                const isMain = c.keyword === 'When';
                return (
                  <div 
                    key={i} 
                    className={`text-xs leading-relaxed flex items-start ${
                      isMain 
                        ? 'text-slate-700 font-semibold mt-1' 
                        : 'text-slate-500 font-medium pl-3 border-l border-slate-200/60 ml-1 mt-0.5'
                    }`}
                  >
                    {isMain ? (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-violet-400 mr-1.5 mt-1.5 shrink-0" />
                    ) : (
                      <span className={`inline-block w-1 h-1 rounded-full mr-1.5 mt-1.5 shrink-0 ${
                        c.keyword === 'But' ? 'bg-rose-350' : 'bg-slate-350'
                      }`} />
                    )}
                    <div>
                      {!isMain && (
                        <span className="text-[9px] font-extrabold uppercase mr-1 text-slate-400 font-mono tracking-wider">
                          {c.keyword}
                        </span>
                      )}
                      {renderHighlightedText(c.content)}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-xs text-slate-400 italic">{t('gherkinVisualizer.noWhen')}</div>
            )}
          </div>

          {/* THEN Column */}
          <div className="bg-slate-50/40 border border-slate-200 rounded-xl p-3 space-y-2">
            <span className="text-[10px] text-slate-500 font-extrabold uppercase tracking-wider block">THEN</span>
            {thenClauses.length > 0 ? (
              thenClauses.map((c, i) => {
                const isMain = c.keyword === 'Then';
                return (
                  <div 
                    key={i} 
                    className={`text-xs leading-relaxed flex items-start ${
                      isMain 
                        ? 'text-slate-800 font-bold mt-1' 
                        : 'text-slate-600 font-semibold pl-3 border-l border-slate-200/60 ml-1 mt-0.5'
                    }`}
                  >
                    {isMain ? (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 mt-1.5 shrink-0" />
                    ) : (
                      <span className={`inline-block w-1 h-1 rounded-full mr-1.5 mt-1.5 shrink-0 ${
                        c.keyword === 'But' ? 'bg-rose-350' : 'bg-slate-350'
                      }`} />
                    )}
                    <div>
                      {!isMain && (
                        <span className="text-[9px] font-extrabold uppercase mr-1 text-slate-400 font-mono tracking-wider">
                          {c.keyword}
                        </span>
                      )}
                      {renderHighlightedText(c.content)}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-xs text-slate-400 italic">{t('gherkinVisualizer.noThen')}</div>
            )}
          </div>
        </div>
      ) : (
        /* Regular Business Meaning View */
        <div className="mb-4 bg-slate-50/40 border border-slate-100 rounded-xl p-3 hover:bg-slate-50 transition-colors">
          <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block mb-1">{t('gherkinVisualizer.businessMeaning')}</span>
          <p className="text-xs text-slate-700 font-medium leading-relaxed">
            {businessMeaning || t('gherkinVisualizer.emptyDemand')}
          </p>
        </div>
      )}

      {/* Examples Grid Table */}
      {examples && examples.headers && examples.headers.length > 0 && (
        <div className="mb-4 overflow-hidden border border-slate-100 rounded-xl shadow-inner">
          <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-100">
            <span className="text-[9px] text-slate-400 font-extrabold uppercase tracking-wider block">{t('gherkinVisualizer.examples')}</span>
          </div>
          <div className="overflow-x-auto max-h-[160px] overflow-y-auto">
            <table className="min-w-full divide-y divide-slate-100 text-[10px] text-left">
              <thead className="bg-slate-50/80 sticky top-0">
                <tr>
                  {examples.headers.map((h, idx) => (
                    <th key={idx} className="px-3 py-1.5 font-bold text-slate-500 tracking-wider font-mono">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-100 font-mono">
                {examples.rows.map((row, rowIdx) => (
                  <tr key={rowIdx} className="hover:bg-slate-50/60 transition-colors">
                    {row.map((cell, cellIdx) => (
                      <td key={cellIdx} className="px-3 py-1.5 text-slate-600 font-medium">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Boundary Highlighting Banner */}
      {boundary && (
        <div className="border border-amber-100 rounded-xl bg-amber-50/30 px-3.5 py-2 flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-100 text-amber-700 font-bold text-[10px] leading-none shrink-0">!</span>
          <div className="text-[10px] text-amber-800/90 font-bold select-text leading-tight">
            Boundary: <span className="font-semibold">{boundary}</span>
          </div>
        </div>
      )}
    </div>
  );
};

// Structured Gherkin Visual Editor Form
export const GherkinVisualEditor: React.FC<{
  initialText: string;
  onChange: (newText: string) => void;
}> = ({ initialText, onChange }) => {
  const { t } = useTranslation();
  const [clauses, setClauses] = useState<GherkinClause[]>([]);
  const [boundary, setBoundary] = useState('');
  const [examplesHeaders, setExamplesHeaders] = useState<string[]>([]);
  const [examplesRows, setExamplesRows] = useState<string[][]>([]);

  // Load from initialText on mount/change
  useEffect(() => {
    const parsed = parseGherkin(initialText);
    setClauses(parsed.clauses.length > 0 ? parsed.clauses : [
      { keyword: 'Given', content: '' },
      { keyword: 'When', content: '' },
      { keyword: 'Then', content: '' }
    ]);
    setBoundary(parsed.boundary || '');
    if (parsed.examples) {
      setExamplesHeaders(parsed.examples.headers);
      setExamplesRows(parsed.examples.rows);
    } else {
      setExamplesHeaders([]);
      setExamplesRows([]);
    }
  }, [initialText]);

  // Sync back to parent when states change
  const triggerSync = (
    cList: GherkinClause[],
    bVal: string,
    eHeaders: string[],
    eRows: string[][]
  ) => {
    const exObj = eHeaders.length > 0 && eRows.length > 0 ? { headers: eHeaders, rows: eRows } : undefined;
    const finalStr = stringifyGherkin(cList, bVal, exObj);
    onChange(finalStr);
  };

  const handleClauseChange = (idx: number, field: keyof GherkinClause, val: string) => {
    const updated = clauses.map((c, i) => i === idx ? { ...c, [field]: val } : c);
    setClauses(updated);
    triggerSync(updated, boundary, examplesHeaders, examplesRows);
  };

  const addClause = () => {
    const updated = [...clauses, { keyword: 'And' as any, content: '' }];
    setClauses(updated);
    triggerSync(updated, boundary, examplesHeaders, examplesRows);
  };

  const removeClause = (idx: number) => {
    const updated = clauses.filter((_, i) => i !== idx);
    setClauses(updated);
    triggerSync(updated, boundary, examplesHeaders, examplesRows);
  };

  const handleBoundaryChange = (val: string) => {
    setBoundary(val);
    triggerSync(clauses, val, examplesHeaders, examplesRows);
  };

  // Examples Manipulation
  const addExampleColumn = () => {
    const colName = `arg_${examplesHeaders.length + 1}`;
    const newHeaders = [...examplesHeaders, colName];
    const newRows = examplesRows.length > 0 ? examplesRows.map(row => [...row, '']) : [['']];
    setExamplesHeaders(newHeaders);
    setExamplesRows(newRows);
    triggerSync(clauses, boundary, newHeaders, newRows);
  };

  const addExampleRow = () => {
    if (examplesHeaders.length === 0) {
      const newHeaders = ['', ''];
      const newRows = [['', '']];
      setExamplesHeaders(newHeaders);
      setExamplesRows(newRows);
      triggerSync(clauses, boundary, newHeaders, newRows);
      return;
    }
    const newRow = Array(examplesHeaders.length).fill('');
    const newRows = [...examplesRows, newRow];
    setExamplesRows(newRows);
    triggerSync(clauses, boundary, examplesHeaders, newRows);
  };

  const updateExampleHeader = (idx: number, val: string) => {
    const newHeaders = examplesHeaders.map((h, i) => i === idx ? val : h);
    setExamplesHeaders(newHeaders);
    triggerSync(clauses, boundary, newHeaders, examplesRows);
  };

  const updateExampleCell = (rowIdx: number, colIdx: number, val: string) => {
    const newRows = examplesRows.map((row, r) => 
      r === rowIdx ? row.map((cell, c) => c === colIdx ? val : cell) : row
    );
    setExamplesRows(newRows);
    triggerSync(clauses, boundary, examplesHeaders, newRows);
  };

  const removeExampleRow = (rowIdx: number) => {
    const newRows = examplesRows.filter((_, r) => r !== rowIdx);
    setExamplesRows(newRows);
    triggerSync(clauses, boundary, examplesHeaders, newRows);
  };

  const removeExampleColumn = (colIdx: number) => {
    const newHeaders = examplesHeaders.filter((_, c) => c !== colIdx);
    const newRows = examplesRows.map(row => row.filter((_, c) => c !== colIdx));
    setExamplesHeaders(newHeaders);
    setExamplesRows(newRows);
    triggerSync(clauses, boundary, newHeaders, newRows);
  };

  return (
    <div className="space-y-4">
      {/* Clauses Section */}
      <div className="space-y-2.5">
        <div className="flex justify-between items-center">
          <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">{t('gherkinVisualizer.clauseConfig')}</span>
          <button 
            type="button" 
            onClick={addClause}
            className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold border border-indigo-200 bg-indigo-50/30 hover:bg-indigo-50 px-2 py-0.5 rounded-lg transition-all"
          >
            {t('gherkinVisualizer.addClause')}
          </button>
        </div>

        <div className="space-y-2 select-none">
          {clauses.map((clause, idx) => (
            <div key={idx} className="flex gap-2 items-center bg-slate-50/50 border border-slate-100 rounded-xl p-2 shadow-inner">
              <select
                value={clause.keyword}
                onChange={(e) => handleClauseChange(idx, 'keyword', e.target.value as any)}
                className="text-xs bg-white border border-slate-200 rounded-lg py-1 px-2.5 font-bold text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 font-mono shadow-sm"
              >
                <option value="Given">Given</option>
                <option value="When">When</option>
                <option value="Then">Then</option>
                <option value="And">And</option>
                <option value="But">But</option>
              </select>
              
              <input
                type="text"
                value={clause.content}
                placeholder={t('gherkinVisualizer.clausePlaceholder', { kw: clause.keyword })}
                onChange={(e) => handleClauseChange(idx, 'content', e.target.value)}
                className="grow text-xs bg-white border border-slate-200 rounded-lg py-1 px-3 text-slate-700 font-medium placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm"
              />

              <button
                type="button"
                onClick={() => removeClause(idx)}
                title={t('gherkinVisualizer.deleteClauseTooltip')}
                className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-400 hover:text-rose-500 border border-slate-200 bg-white hover:bg-rose-50 transition-all text-xs"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Examples Grid Section */}
      <div className="space-y-2.5">
        <div className="flex justify-between items-center">
          <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">{t('gherkinVisualizer.examplesTitle')}</span>
          <div className="flex gap-1.5">
            {examplesHeaders.length > 0 && (
              <button 
                type="button" 
                onClick={addExampleColumn}
                className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold border border-slate-200 bg-white hover:bg-slate-50 px-2 py-0.5 rounded-lg transition-all"
              >
                {t('gherkinVisualizer.addVarCol')}
              </button>
            )}
            <button 
              type="button" 
              onClick={addExampleRow}
              className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold border border-indigo-200 bg-indigo-50/30 hover:bg-indigo-50 px-2 py-0.5 rounded-lg transition-all"
            >
              {examplesHeaders.length > 0 ? t('gherkinVisualizer.addTestRow') : t('gherkinVisualizer.enableTestTable')}
            </button>
          </div>
        </div>

        {examplesHeaders.length > 0 && (
          <div className="border border-slate-200 rounded-xl overflow-hidden shadow-inner max-h-[220px] overflow-y-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs font-mono select-none">
              <thead className="bg-slate-50">
                <tr>
                  {examplesHeaders.map((header, colIdx) => (
                    <th key={colIdx} className="px-2 py-1.5 border-r border-slate-200 last:border-0">
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          value={header}
                          onChange={(e) => updateExampleHeader(colIdx, e.target.value)}
                          placeholder={t('gherkinVisualizer.varName')}
                          className="w-full text-[10px] font-bold text-slate-600 bg-transparent border-0 focus:ring-0 focus:outline-none p-0 text-center font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => removeExampleColumn(colIdx)}
                          title={t('gherkinVisualizer.deleteVarColTooltip')}
                          className="text-[9px] text-slate-300 hover:text-rose-500 font-bold leading-none p-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </th>
                  ))}
                  <th className="w-8 px-2 py-1.5 text-center">{t('gherkinVisualizer.operation')}</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-100">
                {examplesRows.map((row, rowIdx) => (
                  <tr key={rowIdx} className="hover:bg-slate-50/50">
                    {row.map((cell, colIdx) => (
                      <td key={colIdx} className="px-2 py-1.5 border-r border-slate-200 last:border-r-0">
                        <input
                          type="text"
                          value={cell}
                          onChange={(e) => updateExampleCell(rowIdx, colIdx, e.target.value)}
                          placeholder={t('gherkinVisualizer.inputValue')}
                          className="w-full text-[10px] text-slate-700 bg-transparent border-0 focus:ring-0 focus:outline-none p-0 font-medium font-mono"
                        />
                      </td>
                    ))}
                    <td className="px-2 py-1.5 text-center">
                      <button
                        type="button"
                        onClick={() => removeExampleRow(rowIdx)}
                        title={t('gherkinVisualizer.deleteTestRowTooltip')}
                        className="text-[10px] text-slate-400 hover:text-rose-500 font-bold p-0.5"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Boundary Input Section */}
      <div className="space-y-1.5">
        <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider block">{t('gherkinVisualizer.boundaryRulesLabel')}</span>
        <input
          type="text"
          value={boundary}
          placeholder={t('gherkinVisualizer.boundaryRulesPlaceholder')}
          onChange={(e) => handleBoundaryChange(e.target.value)}
          className="w-full text-xs bg-white border border-slate-200 rounded-lg py-1.5 px-3 text-slate-700 font-semibold placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm"
        />
      </div>
    </div>
  );
};