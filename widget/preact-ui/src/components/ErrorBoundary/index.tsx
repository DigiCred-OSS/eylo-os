import type { ComponentChildren, VNode } from "preact";
import { useErrorBoundary } from "preact/hooks";
import { logger } from "../../utils/logging";
import { Alert, AlertTitle, AlertDescription } from "../../design-system/components/Alert";
import { Button } from "../../design-system/components/Button";
import { Stack } from "../../design-system/components/Stack";
import { Box } from "../../design-system/components/Box";

interface ErrorBoundaryProps {
  children: ComponentChildren;
  fallback?: VNode;
}

const ErrorBoundary = ({ children, fallback }: ErrorBoundaryProps) => {
  const [error, resetError] = useErrorBoundary((err) => {
    // Log the error to our logging utility and any reporting service
    logger.error("ErrorBoundary caught an error:", err);
  });

  if (error) {
    // If a fallback is provided, use it. Otherwise, use our default.
    return (
      fallback || (
        <Box padding="xl">
          <Stack spacing="lg" align="center">
            <Alert variant="destructive" className="ew-max-w-md">
              <AlertTitle>Something went wrong</AlertTitle>
              <AlertDescription>
                We're sorry for the inconvenience. Please try again.
              </AlertDescription>
            </Alert>
            <Button variant="outline" onClick={() => resetError()}>
              Try again
            </Button>
          </Stack>
        </Box>
      )
    );
  }

  return <>{children}</>;
};

export default ErrorBoundary;
