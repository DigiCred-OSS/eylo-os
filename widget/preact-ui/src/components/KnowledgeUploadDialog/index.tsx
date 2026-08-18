import type { FC } from "preact/compat";

import { Button } from "../../design-system/components/Button";
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../design-system/components/Dialog";
import { Input } from "../../design-system/components/Input";
import styles from "./KnowledgeUploadDialog.module.css";

export type KnowledgeUploadStatus = {
  kind: "progress" | "success" | "error";
  message: string;
};

interface KnowledgeUploadDialogProps {
  open: boolean;
  selectedFile: File | null;
  busy: boolean;
  status: KnowledgeUploadStatus | null;
  onOpenChange: (open: boolean) => void;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
}

const KnowledgeUploadDialog: FC<KnowledgeUploadDialogProps> = ({
  open,
  selectedFile,
  busy,
  status,
  onOpenChange,
  onFileChange,
  onUpload,
}) => {
  const canUpload = Boolean(selectedFile && !busy);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div>
            <DialogTitle>Upload a file</DialogTitle>
            <DialogDescription>
              Eylo extracts and indexes the file for this conversation. The Agent can use it once
              indexing completes.
            </DialogDescription>
          </div>
          <DialogClose aria-label="Close" onClick={() => onOpenChange(false)} />
        </DialogHeader>

        <DialogBody className={styles.body}>
          <label className={styles.field}>
            <span className={styles.label}>File</span>
            <Input
              type="file"
              disabled={busy}
              onClick={(event) => {
                (event.currentTarget as HTMLInputElement).value = "";
              }}
              onChange={(event) => {
                const input = event.currentTarget as HTMLInputElement;
                onFileChange(input.files?.[0] || null);
              }}
            />
          </label>

          {selectedFile && !status && <p className={styles.help}>Selected: {selectedFile.name}</p>}
          {status && (
            <p className={styles[status.kind]} aria-live="polite">
              {status.message}
            </p>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button disabled={!canUpload} onClick={onUpload}>
            {busy ? "Indexing..." : "Upload and index"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default KnowledgeUploadDialog;
