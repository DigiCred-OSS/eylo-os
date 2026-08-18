import { useState, type FormEvent } from "react";
import { observer } from "mobx-react-lite";
import { Navigate, useLocation } from "react-router";

import { FullPageStatus } from "@/app/FullPageStatus";
import { ThemeToggle } from "@/app/ThemeToggle";
import { useRootStore } from "@/app/use-root-store";
import loginCollaborationArtwork from "@/assets/login-collaboration.webp";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SessionUnavailable } from "@/features/auth/SessionUnavailable";
import type { LoginCredentials } from "@/features/auth/auth.types";

interface LoginLocationState {
  returnTo?: unknown;
}

const LoginPage = observer(function LoginPage() {
  const { auth } = useRootStore();
  const location = useLocation();
  const [credentials, setCredentials] = useState<LoginCredentials>({
    email: "",
    password: "",
  });

  if (auth.status === "checking") {
    return <FullPageStatus message="Verifying session…" />;
  }

  if (auth.status === "unavailable") {
    return <SessionUnavailable />;
  }

  if (auth.status === "authenticated" && auth.organizationId !== null) {
    const returnTo = getSafeReturnPath(location.state);
    return (
      <Navigate replace to={returnTo ?? `/org/${auth.organizationId}/agents`} />
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await auth.login(credentials);
  }

  return (
    <main className="relative grid min-h-svh lg:grid-cols-[minmax(0,1fr)_30rem]">
      <section className="relative hidden overflow-hidden border-r lg:block">
        <img
          className="absolute inset-0 h-full w-full object-cover"
          src={loginCollaborationArtwork}
          alt=""
          aria-hidden="true"
        />
        <div className="relative max-w-md p-8 xl:p-10">
          <div className="bg-background/90 p-6 text-foreground">
            <p className="text-lg font-semibold tracking-tight">Eylo</p>
            <div className="mt-10 space-y-3">
              <p className="text-3xl leading-tight font-semibold tracking-tight">
                Build agents. Connect their infrastructure. Review their work.
              </p>
              <p className="text-sm leading-6 text-muted-foreground">
                One workspace for your organization&apos;s agents,
                infrastructure, and products.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="relative flex items-center justify-center p-6 sm:p-10">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-sm space-y-7">
          <header className="space-y-2">
            <p className="text-sm font-semibold lg:hidden">Eylo</p>
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
            <p className="text-sm leading-6 text-muted-foreground">
              Use your organization member account.
            </p>
          </header>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                name="email"
                autoComplete="email"
                autoFocus
                required
                value={credentials.email}
                aria-invalid={auth.errorMessage !== null}
                onChange={(event) =>
                  setCredentials((current) => ({
                    ...current,
                    email: event.target.value,
                  }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={credentials.password}
                aria-invalid={auth.errorMessage !== null}
                aria-describedby={
                  auth.errorMessage === null ? undefined : "login-error"
                }
                onChange={(event) =>
                  setCredentials((current) => ({
                    ...current,
                    password: event.target.value,
                  }))
                }
              />
            </div>

            {auth.errorMessage !== null ? (
              <p
                id="login-error"
                role="alert"
                className="text-sm leading-5 text-destructive"
              >
                {auth.errorMessage}
              </p>
            ) : null}

            <Button
              className="w-full"
              type="submit"
              disabled={auth.isSubmitting}
            >
              {auth.isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
});

function getSafeReturnPath(state: unknown): string | null {
  const returnTo = (state as LoginLocationState | null)?.returnTo;
  return typeof returnTo === "string" &&
    returnTo.startsWith("/") &&
    !returnTo.startsWith("//")
    ? returnTo
    : null;
}

export { LoginPage };
