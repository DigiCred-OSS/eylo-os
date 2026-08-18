import { observer } from "mobx-react-lite";

import { ThemeToggle } from "@/app/ThemeToggle";
import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";

const SessionUnavailable = observer(function SessionUnavailable() {
  const { auth } = useRootStore();

  return (
    <main className="relative grid min-h-svh place-items-center p-6">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <section className="w-full max-w-md space-y-5" aria-labelledby="title">
        <div className="space-y-2">
          <p className="text-sm font-medium text-warning">Connection problem</p>
          <h1 id="title" className="text-2xl font-semibold tracking-tight">
            Session could not be verified
          </h1>
          <p className="text-sm leading-6 text-muted-foreground">
            {auth.errorMessage}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void auth.hydrate()}>Try again</Button>
          <Button variant="outline" onClick={() => void auth.logout()}>
            Sign out
          </Button>
        </div>
      </section>
    </main>
  );
});

export { SessionUnavailable };
