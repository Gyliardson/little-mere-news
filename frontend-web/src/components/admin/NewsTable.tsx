"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Edit2, Eye, Trash2, CheckCircle, X,
  Loader2, AlertCircle, ExternalLink,
} from "lucide-react";
import { updateNews, deleteNews } from "@/app/[lang]/[secret_admin]/(dashboard)/news/actions";

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
    // View Modal
    viewTitle: "Detalhes da Notícia",
    titleEn: "Título (EN)",
    titlePt: "Título (PT)",
    summaryEn: "Resumo (EN)",
    summaryPt: "Resumo (PT)",
    source: "Fonte",
    originalLink: "Link Original",
    close: "Fechar",
    // Edit Modal
    editTitle: "Editar Notícia",
    save: "Salvar Alterações",
    saving: "Salvando...",
    editSuccess: "Notícia atualizada com sucesso.",
    editError: "Erro ao atualizar. Tente novamente.",
    // Delete Modal
    deleteTitle: "Confirmar Exclusão",
    deleteMsg: "Tem certeza que deseja excluir esta notícia? Esta ação não pode ser desfeita.",
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
    // View Modal
    viewTitle: "News Details",
    titleEn: "Title (EN)",
    titlePt: "Title (PT)",
    summaryEn: "Summary (EN)",
    summaryPt: "Summary (PT)",
    source: "Source",
    originalLink: "Original Link",
    close: "Close",
    // Edit Modal
    editTitle: "Edit News",
    save: "Save Changes",
    saving: "Saving...",
    editSuccess: "News updated successfully.",
    editError: "Failed to update. Please try again.",
    // Delete Modal
    deleteTitle: "Confirm Deletion",
    deleteMsg: "Are you sure you want to delete this news? This action cannot be undone.",
    deleteConfirm: "Yes, Delete",
    deleting: "Deleting...",
    cancel: "Cancel",
    deleteSuccess: "News deleted successfully.",
    deleteError: "Failed to delete. Please try again.",
  },
};

// Reusable Modal Shell
function Modal({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-background-secondary border border-primary/20 rounded-2xl shadow-2xl shadow-primary/10">
        {children}
      </div>
    </div>
  );
}

export default function NewsTable({
  news,
  lang,
}: {
  news: NewsItem[];
  lang: string;
}) {
  const router = useRouter();
  const isPt = lang === "pt";
  const labels = isPt ? t.pt : t.en;

  // Modal state
  const [viewItem, setViewItem] = useState<NewsItem | null>(null);
  const [editItem, setEditItem] = useState<NewsItem | null>(null);
  const [deleteItem, setDeleteItem] = useState<NewsItem | null>(null);

  // Edit form state
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
      {/* Table */}
      <div className="bg-background-secondary border border-primary/20 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-primary/20 bg-background">
                <th className="p-4 text-sm font-bold text-foreground">
                  {labels.date}
                </th>
                <th className="p-4 text-sm font-bold text-foreground">
                  {labels.category}
                </th>
                <th className="p-4 text-sm font-bold text-foreground">
                  {labels.titleCol}
                </th>
                <th className="p-4 text-sm font-bold text-foreground text-center">
                  {labels.status}
                </th>
                <th className="p-4 text-sm font-bold text-foreground text-right">
                  {labels.actions}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-primary/10">
              {news.map((item) => (
                <tr
                  key={item.id}
                  className="hover:bg-primary/5 transition-colors"
                >
                  <td className="p-4 text-sm text-foreground-muted whitespace-nowrap">
                    {new Date(item.published_at).toLocaleDateString(
                      isPt ? "pt-BR" : "en-US"
                    )}
                  </td>
                  <td className="p-4">
                    <span className="px-2 py-1 text-xs font-bold uppercase tracking-wider text-background bg-accent rounded-full">
                      {item.category}
                    </span>
                  </td>
                  <td className="p-4 text-sm font-medium text-foreground max-w-xs truncate">
                    {item.title_en}
                  </td>
                  <td className="p-4 text-center">
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-green-400 bg-green-400/10 px-2 py-1 rounded-md">
                      <CheckCircle className="w-3 h-3" />{" "}
                      {labels.published}
                    </span>
                  </td>
                  <td className="p-4 flex items-center justify-end gap-2">
                    <button
                      onClick={() => setViewItem(item)}
                      className="p-2 text-foreground-muted hover:text-accent hover:bg-accent/10 rounded-lg transition-colors"
                      title={labels.view}
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => openEdit(item)}
                      className="p-2 text-foreground-muted hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
                      title={labels.edit}
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setDeleteItem(item);
                        setFeedback(null);
                      }}
                      className="p-2 text-foreground-muted hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                      title={labels.delete}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {news.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="p-8 text-center text-foreground-muted"
                  >
                    {labels.empty}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* View Modal */}
      <Modal open={!!viewItem} onClose={() => setViewItem(null)}>
        {viewItem && (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-foreground">
                {labels.viewTitle}
              </h2>
              <button
                onClick={() => setViewItem(null)}
                className="p-2 hover:bg-primary/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-foreground-muted" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <span className="px-2 py-1 text-xs font-bold uppercase tracking-wider text-background bg-accent rounded-full">
                {viewItem.category}
              </span>
              <span className="text-sm text-foreground-muted">
                {new Date(viewItem.published_at).toLocaleDateString(
                  isPt ? "pt-BR" : "en-US",
                  { day: "2-digit", month: "long", year: "numeric" }
                )}
              </span>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">
                  {labels.titleEn}
                </label>
                <p className="text-foreground font-medium">{viewItem.title_en}</p>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">
                  {labels.titlePt}
                </label>
                <p className="text-foreground font-medium">{viewItem.title_pt}</p>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">
                  {labels.summaryEn}
                </label>
                <p className="text-sm text-foreground-muted leading-relaxed">
                  {viewItem.summary_en}
                </p>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">
                  {labels.summaryPt}
                </label>
                <p className="text-sm text-foreground-muted leading-relaxed">
                  {viewItem.summary_pt}
                </p>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-primary/10">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-foreground-muted mb-1">
                    {labels.source}
                  </label>
                  <p className="text-sm text-foreground">{viewItem.source_name}</p>
                </div>
                <a
                  href={viewItem.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:text-accent-secondary transition-colors"
                >
                  {labels.originalLink}
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setViewItem(null)}
                className="px-6 py-2.5 bg-primary/10 hover:bg-primary/20 text-foreground font-medium rounded-xl transition-colors"
              >
                {labels.close}
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Edit Modal */}
      <Modal open={!!editItem} onClose={() => !loading && setEditItem(null)}>
        {editItem && (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-foreground">
                {labels.editTitle}
              </h2>
              <button
                onClick={() => !loading && setEditItem(null)}
                className="p-2 hover:bg-primary/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-foreground-muted" />
              </button>
            </div>

            {feedback && (
              <div
                className={`flex items-center gap-2 p-3 rounded-xl text-sm ${
                  feedback.type === "success"
                    ? "bg-green-400/10 border border-green-400/30 text-green-400"
                    : "bg-red-400/10 border border-red-400/30 text-red-400"
                }`}
              >
                {feedback.type === "success" ? (
                  <CheckCircle className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0" />
                )}
                <span>{feedback.msg}</span>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">
                  {labels.category}
                </label>
                <select
                  value={editForm.category}
                  onChange={(e) =>
                    setEditForm({ ...editForm, category: e.target.value })
                  }
                  disabled={loading}
                  className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
                >
                  <option value="IA">IA</option>
                  <option value="Gaming">Gaming</option>
                  <option value="Dev">Dev</option>
                  <option value="Hardware">Hardware</option>
                  <option value="Security">Security</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">
                  {labels.titleEn}
                </label>
                <input
                  type="text"
                  value={editForm.title_en}
                  onChange={(e) =>
                    setEditForm({ ...editForm, title_en: e.target.value })
                  }
                  disabled={loading}
                  className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">
                  {labels.titlePt}
                </label>
                <input
                  type="text"
                  value={editForm.title_pt}
                  onChange={(e) =>
                    setEditForm({ ...editForm, title_pt: e.target.value })
                  }
                  disabled={loading}
                  className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">
                  {labels.summaryEn}
                </label>
                <textarea
                  rows={4}
                  value={editForm.summary_en}
                  onChange={(e) =>
                    setEditForm({ ...editForm, summary_en: e.target.value })
                  }
                  disabled={loading}
                  className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">
                  {labels.summaryPt}
                </label>
                <textarea
                  rows={4}
                  value={editForm.summary_pt}
                  onChange={(e) =>
                    setEditForm({ ...editForm, summary_pt: e.target.value })
                  }
                  disabled={loading}
                  className="w-full px-4 py-3 bg-background border border-primary/20 rounded-xl text-foreground focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-50"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => !loading && setEditItem(null)}
                disabled={loading}
                className="px-6 py-2.5 bg-primary/10 hover:bg-primary/20 text-foreground font-medium rounded-xl transition-colors disabled:opacity-50"
              >
                {labels.cancel}
              </button>
              <button
                onClick={handleSave}
                disabled={loading}
                className="px-6 py-2.5 bg-primary hover:bg-accent text-background font-bold rounded-xl transition-all duration-300 shadow-[0_0_15px_rgba(0,255,255,0.1)] hover:shadow-[0_0_20px_rgba(0,255,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {labels.saving}
                  </>
                ) : (
                  labels.save
                )}
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={!!deleteItem}
        onClose={() => !loading && setDeleteItem(null)}
      >
        {deleteItem && (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-red-400">
                {labels.deleteTitle}
              </h2>
              <button
                onClick={() => !loading && setDeleteItem(null)}
                className="p-2 hover:bg-primary/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-foreground-muted" />
              </button>
            </div>

            {feedback && (
              <div
                className={`flex items-center gap-2 p-3 rounded-xl text-sm ${
                  feedback.type === "success"
                    ? "bg-green-400/10 border border-green-400/30 text-green-400"
                    : "bg-red-400/10 border border-red-400/30 text-red-400"
                }`}
              >
                {feedback.type === "success" ? (
                  <CheckCircle className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0" />
                )}
                <span>{feedback.msg}</span>
              </div>
            )}

            <p className="text-foreground-muted">{labels.deleteMsg}</p>

            <div className="p-4 bg-background rounded-xl border border-primary/10">
              <p className="text-sm font-medium text-foreground truncate">
                {deleteItem.title_en}
              </p>
              <p className="text-xs text-foreground-muted mt-1">
                {deleteItem.source_name} -{" "}
                {new Date(deleteItem.published_at).toLocaleDateString(
                  isPt ? "pt-BR" : "en-US"
                )}
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => !loading && setDeleteItem(null)}
                disabled={loading}
                className="px-6 py-2.5 bg-primary/10 hover:bg-primary/20 text-foreground font-medium rounded-xl transition-colors disabled:opacity-50"
              >
                {labels.cancel}
              </button>
              <button
                onClick={handleDelete}
                disabled={loading}
                className="px-6 py-2.5 bg-red-500 hover:bg-red-400 text-white font-bold rounded-xl transition-all duration-300 shadow-[0_0_15px_rgba(239,68,68,0.1)] hover:shadow-[0_0_20px_rgba(239,68,68,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {labels.deleting}
                  </>
                ) : (
                  labels.deleteConfirm
                )}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
