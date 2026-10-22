import React, { useState } from 'react';
import {
  Calendar,
  Sparkles,
  Copy,
  Check,
  FolderInput,
  AlertOctagon,
  CheckCircle2,
  FileText,
  RefreshCw,
  FolderOpen,
  UploadCloud,
  FileCode,
  BookOpen,
} from 'lucide-react';
import { api } from '../api';

interface WeeklyProps {
  onModuleImported: () => void;
}

export const WeeklyScreen: React.FC<WeeklyProps> = ({ onModuleImported }) => {
  // Brief generator state
  const [topic, setTopic] = useState('Terraform & Infrastructure as Code');
  const [format, setFormat] = useState('TP guidé');
  const [briefResult, setBriefResult] = useState<string | null>(null);
  const [generatingBrief, setGeneratingBrief] = useState(false);
  const [copied, setCopied] = useState(false);

  // Import module state
  const [importPath, setImportPath] = useState('backend/tests/fixtures/demo_module');
  const [importing, setImporting] = useState(false);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<string[] | null>(null);

  // Drag and drop preview
  const [isDragging, setIsDragging] = useState(false);
  const [droppedModulePreview, setDroppedModulePreview] = useState<{
    id: string;
    title: string;
    skill: string;
    lessonsCount: number;
  } | null>(null);

  const handleGenerateBrief = async () => {
    setGeneratingBrief(true);
    try {
      const res = await api.generateBrief(topic, format);
      setBriefResult(res.brief);
    } catch (err: any) {
      alert(err.message || 'Erreur lors de la génération du brief');
    } finally {
      setGeneratingBrief(false);
    }
  };

  const handleCopy = () => {
    if (!briefResult) return;
    navigator.clipboard.writeText(briefResult);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleImport = async () => {
    setImporting(true);
    setImportSuccess(null);
    setImportErrors(null);

    try {
      const res = await api.importModule(importPath);
      setImportSuccess(`Module '${res.module_id}' importé et validé avec succès !`);
      onModuleImported();
    } catch (err: any) {
      if (err.errors && Array.isArray(err.errors)) {
        setImportErrors(err.errors);
      } else if (err.status === 403) {
        setImportErrors(["L'import de module est réservé à localhost (machine locale)."]);
      } else {
        setImportErrors([err.message || "Erreur lors de l'import"]);
      }
    } finally {
      setImporting(false);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.json')) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const parsed = JSON.parse(event.target?.result as string);
          if (parsed.id && parsed.title) {
            setDroppedModulePreview({
              id: parsed.id,
              title: parsed.title,
              skill: parsed.skill || 'general',
              lessonsCount: Array.isArray(parsed.lessons) ? parsed.lessons.length : 1,
            });
            setImportPath(`content/modules/${parsed.id}`);
          }
        } catch {
          setImportErrors(['Fichier JSON invalide']);
        }
      };
      reader.readAsText(file);
    }
  };

  return (
    <div className="space-y-6 max-w-xl mx-auto pb-12">
      {/* Header : Rituel du Dimanche */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl space-y-2">
        <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-amber-400">
          <Calendar className="w-4 h-4" /> Préparation Hebdomadaire
        </div>
        <h1 className="text-lg font-bold text-slate-100">Rituel du Dimanche & Claude Code</h1>
        <p className="text-xs text-slate-300 leading-relaxed">
          Générez votre brief pour Claude Code afin de créer le module de la semaine suivante, puis importez-le en un clic après vérification automatique.
        </p>
      </div>

      {/* 1. Générateur de Brief pour Claude Code */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-5 shadow-lg space-y-4">
        <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-400" /> 1. Générer le Brief Claude Code
        </h2>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Sujet de la semaine prochaine :
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="ex: Kubernetes Ingress, Terraform, Monitoring Prometheus..."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 font-sans"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Format pédagogique souhaité :
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 font-sans cursor-pointer"
            >
              <option value="TP guidé">TP guidé (Pas-à-pas avec script de validation)</option>
              <option value="Résolution d'incident">Résolution d'incident (Post-mortem & correction)</option>
              <option value="Projet autonome">Projet autonome (Conception d'architecture)</option>
              <option value="Audit & Sécurité">Audit & Sécurité (Hardening & conformité)</option>
            </select>
          </div>

          <button
            onClick={handleGenerateBrief}
            disabled={generatingBrief || !topic}
            className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer shadow-md shadow-indigo-950/40"
          >
            {generatingBrief ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
            <span>Générer le Prompt pour Claude Code</span>
          </button>
        </div>

        {briefResult && (
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-slate-400">Brief prêt à copier :</span>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-xs font-semibold text-amber-400 hover:text-amber-300 bg-slate-950 border border-slate-800 px-2.5 py-1 rounded-lg cursor-pointer transition-all"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copié !' : 'Copier le brief'}</span>
              </button>
            </div>
            <pre className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 font-mono text-[11px] text-slate-300 max-h-56 overflow-y-auto leading-relaxed select-all">
              {briefResult}
            </pre>
          </div>
        )}
      </div>

      {/* 2. Import et Validation de Module (avec Drag & Drop) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-5 shadow-lg space-y-4">
        <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
          <FolderInput className="w-4 h-4 text-emerald-400" /> 2. Importer le module produit
        </h2>
        <p className="text-xs text-slate-300 leading-relaxed">
          Le module est validé rigoureusement (module.json, markdown de cours, QCM sans réponses orphelines, TP et scripts). En cas d'erreur, rien n'est copié.
        </p>

        {/* Zone de Drag and drop */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleFileDrop}
          className={`p-6 border-2 border-dashed rounded-2xl text-center space-y-2 transition-all cursor-pointer ${
            isDragging
              ? 'border-emerald-400 bg-emerald-950/20'
              : 'border-slate-700/80 bg-slate-950/40 hover:border-slate-600'
          }`}
        >
          <UploadCloud className="w-8 h-8 text-slate-400 mx-auto" />
          <div className="text-xs text-slate-300 font-semibold">
            Glissez-déposez un fichier <code className="text-amber-400 font-mono">module.json</code> ici
          </div>
          <p className="text-[10px] text-slate-500">ou spécifiez le chemin du dossier ci-dessous</p>
        </div>

        {droppedModulePreview && (
          <div className="p-3.5 bg-slate-950/90 border border-emerald-600/40 rounded-xl space-y-1.5 text-xs animate-fade-in">
            <div className="flex items-center gap-2 font-bold text-emerald-300">
              <BookOpen className="w-4 h-4" /> Aperçu du module détecté :
            </div>
            <div className="text-slate-200 font-bold">{droppedModulePreview.title}</div>
            <div className="flex gap-2 text-[10px] text-slate-400">
              <span>ID: <code className="text-slate-300 font-mono">{droppedModulePreview.id}</code></span>
              <span>•</span>
              <span>Compétence: <code className="text-indigo-300">{droppedModulePreview.skill}</code></span>
              <span>•</span>
              <span>{droppedModulePreview.lessonsCount} leçons</span>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Chemin du dossier source :
            </label>
            <input
              type="text"
              value={importPath}
              onChange={(e) => setImportPath(e.target.value)}
              placeholder="ex: /tmp/mon_nouveau_module ou content/modules/demo"
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <button
            onClick={handleImport}
            disabled={importing || !importPath}
            className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer shadow-md shadow-emerald-950/40"
          >
            {importing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <FolderOpen className="w-3.5 h-3.5" />}
            <span>Valider et Importer le Module</span>
          </button>
        </div>

        {/* Message de succès */}
        {importSuccess && (
          <div className="p-3.5 bg-emerald-950/40 border border-emerald-700/60 rounded-xl text-xs text-emerald-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{importSuccess}</span>
          </div>
        )}

        {/* Liste des erreurs d'import (422) */}
        {importErrors && importErrors.length > 0 && (
          <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl space-y-2 text-xs text-rose-200">
            <div className="flex items-center gap-2 font-bold text-rose-300">
              <AlertOctagon className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <span>Import refusé : {importErrors.length} anomalie{importErrors.length > 1 ? 's' : ''} détectée{importErrors.length > 1 ? 's' : ''}</span>
            </div>
            <ul className="list-disc list-inside space-y-1 text-slate-300">
              {importErrors.map((err, idx) => (
                <li key={idx} className="font-mono text-[11px]">{err}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
