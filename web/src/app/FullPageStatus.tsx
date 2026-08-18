import { LoaderCircle } from "lucide-react";

interface FullPageStatusProps {
  message: string;
}

function FullPageStatus({ message }: FullPageStatusProps) {
  return (
    <main className="grid min-h-svh place-items-center p-6">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        <span>{message}</span>
      </div>
    </main>
  );
}

export { FullPageStatus };
