import { isValidElement, type ReactNode } from "react";
import { Link } from "react-router";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { MermaidDiagram } from "@/features/documentation/MermaidDiagram";
import {
  resolveDocumentationLink,
  type DocumentationPage,
} from "@/features/documentation/documentation-content";

interface DocumentationArticleProps {
  organizationId: string;
  page: DocumentationPage;
}

function DocumentationArticle({
  organizationId,
  page,
}: DocumentationArticleProps) {
  const headingIdByLine = new Map(
    page.headings.map((heading) => [heading.line, heading.id]),
  );

  const components: Components = {
    a({ children, href }) {
      if (href === undefined) {
        return <span>{children}</span>;
      }
      const resolved = resolveDocumentationLink(
        page.sourcePath,
        href,
        organizationId,
      );
      const className =
        "font-medium underline decoration-border underline-offset-4 hover:decoration-foreground focus-visible:rounded-sm focus-visible:outline-2";

      if (resolved.openInNewTab) {
        return (
          <a
            className={className}
            href={resolved.href}
            rel="noreferrer"
            target="_blank"
          >
            {children}
          </a>
        );
      }
      if (resolved.href.startsWith(`/org/${organizationId}/documentation`)) {
        return (
          <Link className={className} to={resolved.href}>
            {children}
          </Link>
        );
      }
      return (
        <a className={className} href={resolved.href}>
          {children}
        </a>
      );
    },
    blockquote({ children }) {
      return (
        <blockquote className="my-5 border-l-2 pl-4 text-muted-foreground">
          {children}
        </blockquote>
      );
    },
    code({ children, className }) {
      const source = textContent(children).replace(/\n$/, "");
      if (className === "language-mermaid") {
        return <MermaidDiagram source={source} />;
      }
      return (
        <code
          className={
            className === undefined
              ? "rounded bg-muted px-1 py-0.5 font-mono text-[0.875em]"
              : `${className} font-mono text-xs leading-5`
          }
        >
          {children}
        </code>
      );
    },
    h2({ children, node }) {
      return (
        <h2
          className="mt-10 scroll-mt-20 border-b pb-2 text-xl font-semibold tracking-tight first:mt-0"
          id={headingIdByLine.get(node?.position?.start.line ?? -1)}
        >
          {children}
        </h2>
      );
    },
    h3({ children, node }) {
      return (
        <h3
          className="mt-8 scroll-mt-20 text-base font-semibold tracking-tight"
          id={headingIdByLine.get(node?.position?.start.line ?? -1)}
        >
          {children}
        </h3>
      );
    },
    h4({ children }) {
      return (
        <h4 className="mt-6 text-sm font-semibold tracking-tight">
          {children}
        </h4>
      );
    },
    hr() {
      return <hr className="my-8 border-border" />;
    },
    img({ alt, src }) {
      return (
        <img
          alt={alt ?? ""}
          className="my-6 h-auto max-w-full border"
          loading="lazy"
          src={src}
        />
      );
    },
    li({ children }) {
      return <li className="pl-1">{children}</li>;
    },
    ol({ children }) {
      return (
        <ol className="my-4 ml-6 list-decimal space-y-2 marker:text-muted-foreground">
          {children}
        </ol>
      );
    },
    p({ children }) {
      return <p className="my-4 leading-7 text-pretty">{children}</p>;
    },
    pre({ children, node }) {
      const codeNode = node?.children[0];
      const codeClassNames =
        codeNode?.type === "element" ? codeNode.properties.className : null;
      const containsMermaid =
        Array.isArray(codeClassNames) &&
        codeClassNames.includes("language-mermaid");
      if (
        containsMermaid ||
        (isValidElement(children) && children.type === MermaidDiagram)
      ) {
        return children;
      }
      return (
        <pre className="my-5 max-w-full overflow-x-auto border bg-muted/50 p-4 text-xs leading-5">
          {children}
        </pre>
      );
    },
    table({ children }) {
      return (
        <div className="my-6 max-w-full overflow-x-auto border">
          <table className="w-full border-collapse text-left text-sm">
            {children}
          </table>
        </div>
      );
    },
    tbody({ children }) {
      return <tbody className="divide-y">{children}</tbody>;
    },
    td({ children }) {
      return <td className="min-w-36 p-3 align-top leading-6">{children}</td>;
    },
    th({ children }) {
      return (
        <th className="min-w-36 bg-muted/50 p-3 align-bottom text-xs font-medium text-muted-foreground">
          {children}
        </th>
      );
    },
    thead({ children }) {
      return <thead className="border-b">{children}</thead>;
    },
    ul({ children }) {
      return (
        <ul className="my-4 ml-6 list-disc space-y-2 marker:text-muted-foreground">
          {children}
        </ul>
      );
    },
  };

  return (
    <article className="min-w-0" aria-labelledby="documentation-page-title">
      <header className="mb-8 border-b pb-6">
        <p className="text-xs font-medium text-muted-foreground">
          Documentation
        </p>
        <h1
          id="documentation-page-title"
          className="mt-2 text-3xl font-semibold tracking-tight text-balance"
        >
          {page.title}
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
          Source: <code>{page.sourcePath}</code>
        </p>
      </header>

      <Markdown components={components} remarkPlugins={[remarkGfm]} skipHtml>
        {page.body}
      </Markdown>
    </article>
  );
}

function textContent(children: ReactNode): string {
  if (typeof children === "string" || typeof children === "number") {
    return String(children);
  }
  if (Array.isArray(children)) {
    return children.map(textContent).join("");
  }
  return "";
}

export { DocumentationArticle };
