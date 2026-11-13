import React, { useState } from 'react';
import { VERSION_CHANGELOG_LIST } from '../engine/demoStructuralProject';

export const VsCodeExportTab: React.FC<{ projectName: string }> = ({ projectName }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const gitCloneCmd = `git clone https://github.com/ittihadista/Xpert-Structural-Design-Studio.git
cd Xpert-Structural-Design-Studio
pip install -r xpert_studio_desktop/requirements.txt
python xpert_studio_desktop/xpert_studio_app.py`;

  return (
    <div className="space-y-6">
      {/* GitHub & VS Code Synchronization Workflow */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              GitHub & VS Code (Antigravity) Synchronization Guide — Xpert Structural Design Studio (v1.0.0)
            </h3>
            <p className="text-xs text-slate-600">
              Complete standalone Python Desktop Studio package located in <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">/xpert_studio_desktop/</code>
            </p>
          </div>
          <span className="px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded text-xs font-mono font-bold">
            Active Project: Stractural-{projectName}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3.5 bg-slate-50 rounded border border-slate-200 space-y-1.5">
            <div className="font-bold text-slate-900">Step 1: Push from AI Studio to GitHub</div>
            <p className="text-slate-600 leading-relaxed">
              Click the <strong>GitHub icon</strong> in the top-right bar of AI Studio and create/push to a clean repository named{' '}
              <code className="font-mono text-slate-900">Xpert-Structural-Design-Studio</code> (Private repository).
            </p>
          </div>

          <div className="p-3.5 bg-slate-50 rounded border border-slate-200 space-y-1.5">
            <div className="font-bold text-slate-900">Step 2: Clone in VS Code</div>
            <p className="text-slate-600 leading-relaxed">
              Open VS Code, press <code className="font-mono text-slate-900">Ctrl+Shift+P</code> →{' '}
              <strong>Git: Clone</strong>, paste your repository URL, and open the cloned folder in VS Code.
            </p>
          </div>

          <div className="p-3.5 bg-slate-50 rounded border border-slate-200 space-y-1.5">
            <div className="font-bold text-slate-900">Step 3: Run Desktop Studio Locally</div>
            <p className="text-slate-600 leading-relaxed">
              Run <code className="font-mono text-slate-900">python xpert_studio_desktop/xpert_studio_app.py</code> to launch the native PyQt6 Desktop Studio.
            </p>
          </div>
        </div>

        <div className="bg-slate-900 text-slate-100 rounded p-3 font-mono text-xs flex items-center justify-between gap-4">
          <pre className="overflow-x-auto">{gitCloneCmd}</pre>
          <button
            type="button"
            onClick={() => handleCopy('clone', gitCloneCmd)}
            className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-semibold shrink-0"
          >
            {copiedId === 'clone' ? 'Copied!' : 'Copy Commands'}
          </button>
        </div>
      </div>

      {/* Desktop Studio Architecture Files Overview */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-3">
        <h4 className="text-sm font-bold text-slate-900">
          Included Desktop Studio Files in <code className="font-mono text-sky-700">/xpert_studio_desktop/</code>
        </h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-100 border-b border-slate-200 font-semibold text-slate-700">
              <tr>
                <th className="p-2.5">File Path</th>
                <th className="p-2.5">Module Role & Engineering Responsibility</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 font-mono">
              <tr>
                <td className="p-2.5 font-bold text-slate-900">/STUDIO_MASTER_BLUEPRINT.md</td>
                <td className="p-2.5 font-sans text-slate-600">
                  Master architectural & engineering specification for Xpert Structural Design Studio (v1.0.0).
                </td>
              </tr>
              <tr>
                <td className="p-2.5 font-bold text-slate-900">/xpert_studio_desktop/xpert_studio_app.py</td>
                <td className="p-2.5 font-sans text-slate-600">
                  PyQt6 Desktop Studio UI: Modal New Project Dialog, Classic Menu Bar & Toolbars (Zero Ribbon), Built-in 2D CAD Canvas, 1-Click Analyze All Beams (F5), and Printable Calculation Report.
                </td>
              </tr>
              <tr>
                <td className="p-2.5 font-bold text-slate-900">/xpert_studio_desktop/xpert_project_io.py</td>
                <td className="p-2.5 font-sans text-slate-600">
                  Workspace & DXF Synchronizer: Creates Stractural-&lt;ProjectName&gt; with &lt;ProjectName&gt;- prefixed files, Green C# tags outside corners, and Orange B# tags at clear-span midpoints.
                </td>
              </tr>
              <tr>
                <td className="p-2.5 font-bold text-slate-900">/xpert_studio_desktop/xpert_structural_engine.py</td>
                <td className="p-2.5 font-sans text-slate-600">
                  ACI 318 Automatic Thickness & Smart Drop-Beam Advisor, Topological Beam Solver, 4-Way Column Framing & P-M Interaction Curves, and ACI 318 Design Engine.
                </td>
              </tr>
              <tr>
                <td className="p-2.5 font-bold text-slate-900">/xpert_studio_desktop/test_studio_engine.py</td>
                <td className="p-2.5 font-sans text-slate-600">
                  Automated Python Unit Test Suite verifying zero duplicate files, non-overlapping tags, smart optimization, and 4-way column framing.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Version Changelog */}
      <div className="bg-white border border-slate-200 rounded p-5 space-y-3">
        <h4 className="text-sm font-bold text-slate-900">Version History & Release Log</h4>
        {VERSION_CHANGELOG_LIST.map((rel) => (
          <div key={rel.version} className="p-3.5 bg-slate-50 rounded border border-slate-200 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-xs text-sky-800 bg-sky-100 px-2 py-0.5 rounded">
                {rel.version}
              </span>
              <span className="font-mono text-xs text-slate-500">{rel.date}</span>
            </div>
            <div className="text-xs font-bold text-slate-900">{rel.title}</div>
            <ul className="list-disc list-inside text-xs text-slate-600 space-y-1">
              {rel.changes.map((c, idx) => (
                <li key={idx}>{c}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
};
