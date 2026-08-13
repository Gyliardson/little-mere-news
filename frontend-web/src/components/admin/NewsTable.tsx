"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  CheckCircle,
  Edit2,
  ExternalLink,
  Eye,
  Loader2,
  Trash2,
  X,
} from "lucide-react";
import {
  deleteNews,
  updateNews,
} from "@/app/[lang]/[secret_admin]/(dashboard)/news/actions";

interface NewsItem {
  id: string;
  category: string;
  source_name: string;
  source_url: string;
  title_en: string;
  title_pt: string;
  summary_en: string;
  summary_pt: string;
  published_at: string;
}

const t = {
  pt: {
    date: "Data",
    category: "Categoria",
    titleCol: "Título Original (EN)",
    status: "Status",
    actions: "Ações",
    published: "Publicado",
    view: "Visualizar",
    edit: "Editar",
    delete: "Excluir",
    empty: "Nenhuma notícia encontrada no banco.",
    viewTitle: "Detalhes da Notícia",
    titleEn: "Título (EN)",
    titlePt: "Título (PT)",
    summaryEn: "Resumo (EN)",
    summaryPt: "Resumo (PT)",
    source: "Fonte",
    originalLink: "Link Original",
    close: "Fechar",
    editTitle: "Editar Notícia",
    save: "Salvar Alterações",
    saving: "Salvando...",
    editSuccess: "Notícia atualizada com sucesso.",
    editError: "Erro ao atualizar. Tente novamente.",
    deleteTitle: "Confirmar Exclusão",
    deleteMsg:
      "Tem certeza que deseja excluir esta notícia? Esta ação não pode ser desfeita.",
    deleteConfirm: "Sim, Excluir",
    deleting: "Excluindo...",
    cancel: "Cancelar",
    deleteSuccess: "Notícia excluída com sucesso.",
    deleteError: "Erro ao excluir. Tente novamente.",
  },
  en: {
    date: "Date",
    category: "Category",
    titleCol: "Original Title (EN)",
    status: "Status",
    actions: "Actions",
    published: "Published",
    view: "View",
    edit: "Edit",
    delete: "Delete",
    empty: "No news found in the database.",
    viewTitle: "News Details",
    titleEn: "Title (EN)",
    titlePt: "Title (PT)",
    summaryEn: "Summary (EN)",
    summaryPt: "Summary (PT)",
    source: "Source",
    originalLink: "Original Link",
    close: "Close",
    editTitle: "Edit News",
    save: "Save Changes",
    saving: "Saving...",
    editSuccess: "News updated successfully.",
    editError: "Failed to update. Please try again.",
    deleteTitle: "Confirm Deletion",
    deleteMsg: "Are you sure you want to delete this news? This action cannot be undone.",
    deleteConfirm: "Yes, Delete",
    deleting: "Deleting...",
    cancel: "Cancel",
    deleteSuccess: "News deleted successfully.",
    deleteError: "Failed to delete. Please try again.",
  },
};

function Modal({
  open,
  onClose,
  titleId,
  children,
}: {
  open: boolean;
  onClose: () => void;
  titleId: string;
  children: React.ReactNode;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    previousFocus.current = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const focusable = dialog?.querySelector<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab" || !dialog) return;
      const items = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-background-secondary border border-primary/20 rounded-2xl shadow-2xl shadow-primary/10"
      >
        {children}
      </div>
    </div>
  );
}

export default function NewsTable({ news, lang }: { news: NewsItem[]; lang: string }) {
  const router = useRouter();
  const isPt = lang === "pt";
  const labels = isPt ? t.pt : t.en;

  const [viewItem, setViewItem] = useState<NewsItem | null>(null);
  const [editItem, setEditItem] = useState<NewsItem | null>(null);
  const [deleteItem, setDeleteItem] = useState<NewsItem | null>(null);
  const [editForm, setEditForm] = useState({
    title_en: "",
    title_pt: "",
    summary_en: "",
    summary_pt: "",
    category: "",
  });
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  const openEdit = (item: NewsItem) => {
    setEditForm({
      title_en: item.title_en,
      title_pt: item.title_pt,
      summary_en: item.summary_en,
      summary_pt: item.summary_pt,
      category: item.category,
    });
    setEditItem(item);
    setFeedback(null);
  };

  const handleSave = async () => {
    if (!editItem) return;
    setLoading(true);
    setFeedback(null);
    const result = await updateNews(editItem.id, editForm);
    setLoading(false);
    if (result.success) {
      setFeedback({ type: "success", msg: labels.editSuccess });
      setTimeout(() => {
        setEditItem(null);
        setFeedback(null);
        router.refresh();
      }, 1000);
    } else {
      setFeedback({ type: "error", msg: labels.editError });
    }
  };

  const handleDelete = async () => {
    if (!deleteItem) return;
    setLoading(true);
    setFeedback(null);
    const result = await deleteNews(deleteItem.id);
    setLoading(false);
    if (result.success) {
      setFeedback({ type: "success", msg: labels.deleteSuccess });
      setTimeout(() => {
        setDeleteItem(null);
        setFeedback(null);
        router.refresh();
      }, 1000);
    } else {
      setFeedback({ type: "error", msg: labels.deleteError });
    }
  };

  return (
    <>
      <div className="bg-background-secondary border border-primary/20 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-primary/20 bg-background">
                <th className="p-4 text-sm font-bold text-foreground">{labels.date}</th>
                <th className="p-4 text-sm font-bold text-foreground">{labels.category}</th>
                <th className="p-4 text-sm font-bold text-foreground">{labels.titleCol}</th>
                <th className="p-4 text-sm font-bold text-foreground text-center">{labels.status}</th>
                <th className="p-4 text-sm font-bold text-foreground text-right">{labels.actions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-primary/10">
              {news.map((item) => (
                <tr key={item.id} className="hover:bg-primary/5 transition-colors">
                  <td className="p-4 text-sm text-foreground-muted whitespace-nowrap">
                    {new Date(item.published_at).toLocaleDateString(isPt ? "pt-BR" : "en-US")}
                  </td>
                  <td className="p-4">
                    <span className="px-2 py-1 text-xs font-bold uppercase tracking-wider text-background bg-accent rounded-full">
                      {item.category}
                    </span>
                  </td>
                  <td className="p-4 text-sm font-medium text-foreground max-w-xs truncate">{item.title_en}</td>
                  <td className="p-4 text-center">
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-green-400 bg-green-400/10 px-2 py-1 rounded-md">
                      <CheckCircle className="w-3 h-3" aria-hidden="true" /> {labels.published}
                    </span>
                  </td>
                  <td className="p-4 flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setViewItem(item)}
                      className="p-2 text-foreground-muted hover:text-accent hover:bg-accent/10 rounded-lg transition-colors"
                      aria-label={`${labels.view}: ${item.title_en}`}
                    >
                      <Eye className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => openEdit(item)}
                      className="p-2 text-foreground-muted hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
                      aria-label={`${labels.edit}: ${item.title_en}`}
                    >
                      <Edit2 className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDeleteItem(item);
                        setFeedback(null);
                      }}
                      className="p-2 text-foreground-muted hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                      aria-label={`${labels.delete}: ${item.title_en}`}
                    >
                      <Trash2 className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              ))}
              {news.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-foreground-muted">{labels.empty}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={!!viewItem} onClose={() => setViewItem(null)} titleId="view-news-title">
        {viewItem && (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 id="view-news-title" className="text-xl font-bold text-foreground">{labels.viewTitle}</h2>
              <button type="button" onClick={() => setViewItem(null)} aria-label={labels.close} className="p-2 hover:bg-primary/10 rounded-lg transition-colors">
                <X className="w-5 h-5 text-foreground-muted" aria-hidden="true" />
              </button>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-1 text-xs font-bold uppercase tracking-wider text-background bg-accent rounded-full">{viewItem.category}</span>
              <span className="text-sm text-foreground-muted">
                {new Date(viewItem.published_at).toLocaleDateString(isPt ? "pt-BR" : "en-US", { day: "2-digit", month: "long", year: "numeric" })}
              </span>
            </div>
            <dl className="space-y-4">
              <div><dt className="text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">{labels.titleEn}</dt><dd className="text-foreground font-medium">{viewItem.title_en}</dd></div>
              <div><dt className="text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">{labels.titlePt}</dt><dd className="text-foreground font-medium">{viewItem.title_pt}</dd></div>
              <div><dt className="text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">{labels.summaryEn}</dt><dd className="text-sm text-foreground-muted leading-relaxed">{viewItem.summary_en}</dd></div>
              <div><dt className="text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">{labels.summaryPt}</dt><dd className="text-sm text-foreground-muted leading-relaxed">{viewItem.summary_pt}</dd></div>
            </dl>
            <div className="flex items-center justify-between pt-2 border-t border-primary/10">
              <div><p className="text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">{labels.source}</p><p className="text-sm text-foreground">{viewItem.source_name}</p></div>
              <a href={viewItem.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:text-accent-secondary transition-colors">
                {labels.originalLink}<ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </a>
            </div>
            <div className="flex justify-end pt-2"><button type="button" onClick={() => setViewItem(null)} className="px-6 py-2.5 bg-primary/10 hover:bg-primary/20 text-foreground font-medium rounded-xl transition-colors">{labels.close}</button></div>
          </div>
        )}
      </Modal>

      <Modal open={!!editItem} onClose={() => !loading && setEditItem(null)} titleId="edit-news-title">
        {editItem && (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 id="edit-news-title" className="text-xl font-bold text-foreground">{labels.editTitle}</h2>
              <button type="button" onClick={() => !loading && setEditItem(null)} aria-label={labels.close} className="p-2 hover:bg-primary/10 rounded-lg transition-colors">
                <X className="w-5 h-5 text-foreground-muted" aria-hidden="true" />
              </button>
            </div>
            {feedback && (
              <div role="status" className={`flex items-center gap-2 p-3 rounded-xl text-sm ${feedback.type === "success" ? "bg-green-400/10 border border-green-400/30 text-green-400" : "bg-red-400/10 border border-red-400/30 text-red-400"}`}>
                {feedback.type === "success" ? <CheckCircle className="w-4 h-4 shrink-0" aria-hidden="true" /> : <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />}
                <span>{feedback.msg}</span>
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label htmlFor="edit-category" className="block text-sm font-medium text-foreground-muted mb-1">{labels.category}</label>
                <select id="edit-category" value={editForm.category} onChange={(e) => setEditForm({ ...editForm, category: e.target.value })} disabled={loading} className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50">
                  <option value="IA">IA</option><option value="Gaming">Gaming</option><option value="Dev">Dev</option><option value="Hardware">Hardware</option><option value="Security">Security</option>
                </select>
              </div>
              <div><label htmlFor="edit-title-en" className="block text-sm font-medium text-foreground-muted mb-1">{labels.titleEn}</label><input id="edit-title-en" type="text" value={editForm.title_en} onChange={(e) => setEditForm({ ...editForm, title_en: e.target.value })} disabled={loading} className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50" /></div>
              <div><label htmlFor="edit-title-pt" className="block text-sm font-medium text-foreground-muted mb-1">{labels.titlePt}</label><input id="edit-title-pt" type="text" value={editForm.title_pt} onChange={(e) => setEditForm({ ...editForm, title_pt: e.target.value })} disabled={loading} className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50" /></div>
              <div><label htmlFor="edit-summary-en" className="block text-sm font-medium text-foreground-muted mb-1">{labels.summaryEn}</label><textarea id="edit-summary-en" rows={4} value={editForm.summary_en} onChange={(e) => setEditForm({ ...editForm, summary_en: e.target.value })} disabled={loading} className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-50" /></div>
              <div><label htmlFor="edit-summary-pt" className="block text-sm font-medium text-foreground-muted mb-1">{labels.summaryPt}</label><textarea id="edit-summary-pt" rows={4} value={editForm.summary_pt} onChange={(e) => setEditForm({ ...editForm, summary_pt: e.target.value })} disabled={loading} className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-50" /></div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => !loading && setEditItem(null)} disabled={loading} className="px-6 py-2.5 bg-primary/10 hover:bg-primary/20 text-foreground font-medium rounded-xl transition-colors disabled:opacity-50">{labels.cancel}</button>
              <button type="button" onClick={handleSave} disabled={loading} className="px-6 py-2.5 bg-primary hover:bg-accent text-background font-bold rounded-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
                {loading ? <><Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />{labels.saving}</> : labels.save}
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!deleteItem} onClose={() => !loading && setDeleteItem(null)} titleId="delete-news-title">
        {deleteItem && (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 id="delete-news-title" className="text-xl font-bold text-red-400">{labels.deleteTitle}</h2>
              <button type="button" onClick={() => !loading && setDeleteItem(null)} aria-label={labels.close} className="p-2 hover:bg-primary/10 rounded-lg transition-colors"><X className="w-5 h-5 text-foreground-muted" aria-hidden="true" /></button>
            </div>
            {feedback && (
              <div role="status" className={`flex items-center gap-2 p-3 rounded-xl text-sm ${feedback.type === "success" ? "bg-green-400/10 border border-green-400/30 text-green-400" : "bg-red-400/10 border border-red-400/30 text-red-400"}`}>
                {feedback.type === "success" ? <CheckCircle className="w-4 h-4 shrink-0" aria-hidden="true" /> : <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />}<span>{feedback.msg}</span>
              </div>
            )}
            <p className="text-foreground-muted">{labels.deleteMsg}</p>
            <div className="p-4 bg-background rounded-xl border border-primary/10"><p className="text-sm font-medium text-foreground truncate">{deleteItem.title_en}</p><p className="text-xs text-foreground-muted mt-1">{deleteItem.source_name} - {new Date(deleteItem.published_at).toLocaleDateString(isPt ? "pt-BR" : "en-US")}</p></div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => !loading && setDeleteItem(null)} disabled={loading} className="px-6 py-2.5 bg-primary/10 hover:bg-primary/20 text-foreground font-medium rounded-xl transition-colors disabled:opacity-50">{labels.cancel}</button>
              <button type="button" onClick={handleDelete} disabled={loading} className="px-6 py-2.5 bg-red-500 hover:bg-red-400 text-white font-bold rounded-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
                {loading ? <><Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />{labels.deleting}</> : labels.deleteConfirm}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
