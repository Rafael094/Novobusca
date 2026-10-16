"use client";

import { useRef, useState } from "react";

import {
  Badge,
  Button,
  EmptyState,
  ErrorNote,
  Select,
  Spinner,
} from "@/components/ui";
import {
  downloadNitDocument,
  useNitDocuments,
  useUploadNitDocument,
} from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";

const LEVEL_TONES: Record<string, "green" | "blue" | "amber" | "red"> = {
  PUBLIC: "green",
  INTERNAL: "blue",
  RESTRICTED: "amber",
  CONFIDENTIAL: "red",
};

/** Documents panel: upload (validated server-side) and authorized download. */
export function DocumentsPanel({
  disclosureId,
  assetId,
}: {
  disclosureId?: string;
  assetId?: string;
}) {
  const { has } = useAuth();
  const { data, isLoading, error } = useNitDocuments({
    disclosure_id: disclosureId,
    asset_id: assetId,
    page_size: 50,
  });
  const upload = useUploadNitDocument();
  const fileRef = useRef<HTMLInputElement>(null);
  const [level, setLevel] = useState("INTERNAL");
  const [message, setMessage] = useState<string | null>(null);

  const canUpload = has("NIT_DOCUMENT_UPLOAD");

  function onUpload(file: File) {
    setMessage(null);
    upload.mutate(
      { file, disclosure_id: disclosureId, asset_id: assetId, confidentiality_level: level },
      {
        onSuccess: () => {
          setMessage("Documento enviado com sucesso.");
          if (fileRef.current) fileRef.current.value = "";
        },
      },
    );
  }

  return (
    <div className="space-y-4">
      {canUpload && (
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-gray-100 px-4 py-3">
          <div className="min-w-[180px]">
            <Select
              label="Nível de sigilo"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            >
              <option value="PUBLIC">Público</option>
              <option value="INTERNAL">Interno</option>
              <option value="RESTRICTED">Restrito</option>
              <option value="CONFIDENTIAL">Confidencial</option>
            </Select>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.gif,.docx,.xlsx"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
            }}
            className="text-sm text-slate-600"
          />
          {upload.isPending ? <Spinner label="Enviando…" /> : null}
        </div>
      )}

      {message ? (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {message}
        </p>
      ) : null}
      {upload.error ? (
        <ErrorNote>{(upload.error as Error).message}</ErrorNote>
      ) : null}
      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      {isLoading ? (
        <Spinner />
      ) : data && data.items.length > 0 ? (
        <ul className="space-y-2">
          {data.items.map((doc) => (
            <li
              key={doc.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-100 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-700">
                  {doc.title || doc.original_filename}
                </p>
                <p className="text-xs text-slate-400">
                  {(doc.size_bytes / 1024).toFixed(1)} KB · {doc.mime_type} ·{" "}
                  {new Date(doc.created_at).toLocaleDateString("pt-BR")}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={LEVEL_TONES[doc.confidentiality_level] || "slate"}>
                  {doc.confidentiality_level}
                </Badge>
                <Button
                  variant="secondary"
                  className="px-3 py-1.5"
                  onClick={() =>
                    downloadNitDocument(doc.id, doc.original_filename).catch(
                      (e) => setMessage((e as Error).message),
                    )
                  }
                >
                  Baixar
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          title="Nenhum documento"
          description="Documentos confidenciais ficam acessíveis apenas a usuários autorizados."
        />
      )}
    </div>
  );
}
