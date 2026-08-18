import { Link } from "react-router";

import { buttonVariants } from "@/components/ui/button-variants";

function NotFoundPage() {
  return (
    <main className="grid min-h-svh place-items-center p-6">
      <section className="w-full max-w-md space-y-5" aria-labelledby="title">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">404</p>
          <h1 id="title" className="text-2xl font-semibold tracking-tight">
            Page not found
          </h1>
          <p className="text-sm leading-6 text-muted-foreground">
            This page is unavailable or does not belong to your organization.
          </p>
        </div>
        <Link className={buttonVariants()} to="/">
          Return to Eylo
        </Link>
      </section>
    </main>
  );
}

export { NotFoundPage };
