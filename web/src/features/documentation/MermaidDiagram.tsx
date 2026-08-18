import { observer } from "mobx-react-lite";
import { useEffect, useId, useState } from "react";

import { useRootStore } from "@/app/use-root-store";

interface MermaidDiagramProps {
  source: string;
}

interface DiagramState {
  errorMessage: string | null;
  svg: string | null;
}

let mermaidRenderQueue: Promise<void> = Promise.resolve();

function scheduleMermaidRender<T>(operation: () => Promise<T>): Promise<T> {
  const result = mermaidRenderQueue.then(operation, operation);
  mermaidRenderQueue = result.then(
    () => undefined,
    () => undefined,
  );
  return result;
}

const MermaidDiagram = observer(function MermaidDiagram({
  source,
}: MermaidDiagramProps) {
  const { theme } = useRootStore();
  const diagramId = `eylo-doc-diagram-${useId().replaceAll(":", "")}`;
  const [state, setState] = useState<DiagramState>({
    errorMessage: null,
    svg: null,
  });

  useEffect(() => {
    let isCurrent = true;
    setState({ errorMessage: null, svg: null });

    async function renderDiagram(): Promise<void> {
      try {
        const svg = await scheduleMermaidRender(async () => {
          const { default: mermaid } = await import("mermaid");
          mermaid.initialize({
            securityLevel: "strict",
            startOnLoad: false,
            suppressErrorRendering: true,
            theme: theme.resolvedTheme === "dark" ? "dark" : "neutral",
          });
          const result = await mermaid.render(diagramId, source);
          if (result.svg.trim() === "") {
            throw new Error("The diagram renderer returned an empty result.");
          }
          return result.svg;
        });
        if (isCurrent) {
          setState({ errorMessage: null, svg });
        }
      } catch (error) {
        if (isCurrent) {
          setState({
            errorMessage:
              error instanceof Error
                ? error.message
                : "The diagram could not be rendered.",
            svg: null,
          });
        }
      }
    }

    void renderDiagram();
    return () => {
      isCurrent = false;
    };
  }, [diagramId, source, theme.resolvedTheme]);

  if (state.errorMessage !== null) {
    return (
      <figure className="my-6 min-w-0 border bg-muted/30 p-4">
        <figcaption className="text-sm font-medium">
          Diagram unavailable
        </figcaption>
        <p
          className="mt-1 text-sm leading-6 text-muted-foreground"
          role="alert"
        >
          {state.errorMessage}
        </p>
        <pre className="mt-4 max-w-full overflow-x-auto bg-muted p-3 text-xs leading-5">
          <code>{source}</code>
        </pre>
      </figure>
    );
  }

  if (state.svg === null) {
    return (
      <div
        className="my-6 min-h-40 animate-pulse border bg-muted/40"
        role="status"
        aria-label="Rendering diagram"
      />
    );
  }

  return (
    <figure
      className="my-6 min-w-0 overflow-x-auto border bg-card p-4 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      aria-label="Architecture diagram"
      // Mermaid receives trusted, source-controlled Markdown and encodes labels
      // under strict security before returning this SVG.
      dangerouslySetInnerHTML={{ __html: state.svg }}
    />
  );
});

export { MermaidDiagram };
