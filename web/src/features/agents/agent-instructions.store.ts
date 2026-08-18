import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { getAgentApiErrorMessage } from "@/features/agents/agent-api-errors";
import type { StoredAgentInstructionDraft } from "@/features/agents/agent-instruction-draft-storage";
import { AgentInstructionDraftStorage } from "@/features/agents/agent-instruction-draft-storage";
import type {
  AgentInstructionTemplate,
  AgentInstructionTemplateCreateInput,
  AgentInstructionTemplateUpdateInput,
} from "@/features/agents/agents.types";

const LOAD_ERROR_MESSAGE =
  "Instruction templates could not be loaded. Try again.";
const ACTION_ERROR_MESSAGE =
  "The instruction template could not be published. Your text is preserved.";
const CONFLICT_MESSAGE =
  "This instruction draft changed after your local edit began. Keep your text and rebase it onto the latest draft before publishing.";
const DRAFT_STORAGE_ERROR_MESSAGE =
  "This browser could not save the instruction draft. Keep this tab open until it is published.";

interface AgentInstructionEditorContext {
  memberKey: string;
  organizationId: string;
  templateId: string | null;
}

class AgentInstructionsStore {
  actionErrorMessage: string | null = null;
  baseDraftVersion: number | null = null;
  body = "";
  conflictMessage: string | null = null;
  draftStorageErrorMessage: string | null = null;
  errorMessage: string | null = null;
  isLoading = false;
  isSaving = false;
  items: AgentInstructionTemplate[] = [];
  name = "";
  savedAt: string | null = null;
  templateId: string | null = null;

  private readonly api: ApiClient;
  private baselineBody = "";
  private baselineName = "";
  private context: AgentInstructionEditorContext | null = null;
  private editorVersion = 0;
  private loadVersion = 0;
  private organizationId: string | null = null;
  private readonly storage: AgentInstructionDraftStorage;

  constructor(api: ApiClient, storage: AgentInstructionDraftStorage) {
    this.api = api;
    this.storage = storage;

    makeAutoObservable<
      this,
      | "api"
      | "baselineBody"
      | "baselineName"
      | "context"
      | "editorVersion"
      | "loadVersion"
      | "organizationId"
      | "storage"
    >(
      this,
      {
        api: false,
        baselineBody: false,
        baselineName: false,
        context: false,
        editorVersion: false,
        loadVersion: false,
        organizationId: false,
        storage: false,
      },
      { autoBind: true },
    );
  }

  get hasEditor(): boolean {
    return this.context !== null;
  }

  get isEditorDirty(): boolean {
    return this.body !== this.baselineBody || this.name !== this.baselineName;
  }

  get isCreating(): boolean {
    return this.context !== null && this.templateId === null;
  }

  templateFor(id: string | null): AgentInstructionTemplate | null {
    if (id === null) {
      return null;
    }
    return this.items.find((template) => template.id === id) ?? null;
  }

  async load(organizationId: string, force = false): Promise<void> {
    const changedOrganization = this.organizationId !== organizationId;
    if (changedOrganization) {
      this.resetForOrganization(organizationId);
    } else if (!force && (this.isLoading || this.items.length > 0)) {
      return;
    }

    const loadVersion = ++this.loadVersion;
    this.isLoading = true;
    this.errorMessage = null;

    try {
      const templates = await this.fetchTemplates();
      if (!this.isCurrentLoad(organizationId, loadVersion)) {
        return;
      }
      runInAction(() => {
        this.items = templates;
      });
    } catch {
      if (this.isCurrentLoad(organizationId, loadVersion)) {
        runInAction(() => {
          this.errorMessage = LOAD_ERROR_MESSAGE;
        });
      }
    } finally {
      if (this.isCurrentLoad(organizationId, loadVersion)) {
        runInAction(() => {
          this.isLoading = false;
        });
      }
    }
  }

  beginCreate(memberKey: string, organizationId: string): void {
    this.prepareEditor({ memberKey, organizationId, templateId: null });
    const stored = this.readStoredDraft();
    if (stored !== null && stored.baseDraftVersion === null) {
      this.applyStoredDraft(stored);
    }
  }

  beginEdit(
    memberKey: string,
    organizationId: string,
    template: AgentInstructionTemplate,
  ): void {
    this.prepareEditor({
      memberKey,
      organizationId,
      templateId: template.id,
    });
    this.name = template.name;
    this.body = template.draft_body;
    this.baselineName = template.name;
    this.baselineBody = template.draft_body;
    this.baseDraftVersion = template.draft_version;

    const stored = this.readStoredDraft();
    if (stored !== null) {
      this.applyStoredDraft(stored);
      this.conflictMessage =
        stored.baseDraftVersion === template.draft_version
          ? null
          : CONFLICT_MESSAGE;
    }
  }

  setName(name: string): void {
    this.name = name;
    this.actionErrorMessage = null;
    this.persistEditor();
  }

  setBody(body: string): void {
    this.body = body;
    this.actionErrorMessage = null;
    this.persistEditor();
  }

  discardEditor(): void {
    this.invalidateEditorOperation();
    if (this.context !== null) {
      this.storage.clear(this.context);
    }
    this.resetEditor();
  }

  rebaseEditor(): void {
    if (this.templateId === null) {
      return;
    }
    const template = this.templateFor(this.templateId);
    if (template === null) {
      this.actionErrorMessage = LOAD_ERROR_MESSAGE;
      return;
    }
    this.name = template.name;
    this.baselineName = template.name;
    this.baselineBody = template.draft_body;
    this.baseDraftVersion = template.draft_version;
    this.conflictMessage = null;
    this.actionErrorMessage = null;
    this.persistEditor();
  }

  async publishAndSelect(): Promise<string | null> {
    if (
      this.context === null ||
      this.isSaving ||
      this.conflictMessage !== null
    ) {
      return null;
    }

    const name = this.name.trim();
    const body = this.body;
    if (name === "" || body.trim() === "") {
      this.actionErrorMessage = "Name and instructions are required.";
      return null;
    }

    this.isSaving = true;
    this.actionErrorMessage = null;
    this.persistEditor();
    const editorVersion = this.editorVersion;
    const editorContext = this.context;

    try {
      const template =
        this.templateId === null
          ? await this.createTemplate(name, body, editorVersion)
          : await this.updateTemplateIfNeeded(body, editorVersion);
      const revision = await this.publishTemplate(template);
      if (!this.isCurrentEditor(editorVersion)) {
        return null;
      }
      const publishedTemplate: AgentInstructionTemplate = {
        ...template,
        draft_dirty: false,
        lifecycle: "published",
        published_revision: revision,
      };

      runInAction(() => {
        this.items = replaceTemplate(this.items, publishedTemplate);
        this.clearEditorDraft();
        this.resetEditor();
        this.isSaving = false;
        this.editorVersion += 1;
      });
      return publishedTemplate.id;
    } catch (error) {
      if (
        this.isCurrentEditor(editorVersion) &&
        error instanceof InstructionActionError &&
        error.status === 409 &&
        editorContext.templateId !== null
      ) {
        await this.refreshConflict(editorContext.organizationId, editorVersion);
      }
      if (!this.isCurrentEditor(editorVersion)) {
        return null;
      }
      runInAction(() => {
        this.actionErrorMessage =
          error instanceof InstructionActionError
            ? error.message
            : ACTION_ERROR_MESSAGE;
      });
      return null;
    } finally {
      if (this.isCurrentEditor(editorVersion)) {
        runInAction(() => {
          this.isSaving = false;
        });
      }
    }
  }

  private async createTemplate(
    name: string,
    body: string,
    editorVersion: number,
  ): Promise<AgentInstructionTemplate> {
    const input: AgentInstructionTemplateCreateInput = {
      body,
      kind: "agent_instructions",
      name,
      variable_schema: { variables: [] },
    };
    const { data, error, response } = await this.api.POST("/api/templates", {
      body: input,
    });
    const template = requireTemplate(data, error, response);

    const previousContext = this.context;
    if (previousContext !== null && this.isCurrentEditor(editorVersion)) {
      this.storage.clear(previousContext);
      runInAction(() => {
        this.context = { ...previousContext, templateId: template.id };
        this.templateId = template.id;
        this.baseDraftVersion = template.draft_version;
        this.baselineName = template.name;
        this.baselineBody = template.draft_body;
        this.items = replaceTemplate(this.items, template);
        this.persistEditor();
      });
    }
    return template;
  }

  private async updateTemplateIfNeeded(
    body: string,
    editorVersion: number,
  ): Promise<AgentInstructionTemplate> {
    const template = this.templateFor(this.templateId);
    if (template === null || this.baseDraftVersion === null) {
      throw new InstructionActionError(LOAD_ERROR_MESSAGE, 404);
    }
    if (body === template.draft_body) {
      return template;
    }

    const input: AgentInstructionTemplateUpdateInput = {
      body,
      expected_draft_version: this.baseDraftVersion,
    };
    const { data, error, response } = await this.api.PATCH(
      "/api/templates/{template_id}/draft",
      {
        params: { path: { template_id: template.id } },
        body: input,
      },
    );
    const updated = requireTemplate(data, error, response);
    if (this.isCurrentEditor(editorVersion)) {
      runInAction(() => {
        this.baseDraftVersion = updated.draft_version;
        this.baselineBody = updated.draft_body;
        this.baselineName = updated.name;
        this.items = replaceTemplate(this.items, updated);
        this.persistEditor();
      });
    }
    return updated;
  }

  private async publishTemplate(
    template: AgentInstructionTemplate,
  ): Promise<number> {
    const { data, error, response } = await this.api.POST(
      "/api/templates/{template_id}/publish",
      {
        params: { path: { template_id: template.id } },
        body: { expected_draft_version: template.draft_version },
      },
    );
    if (!response.ok || data === undefined) {
      throw new InstructionActionError(
        getAgentApiErrorMessage(error, ACTION_ERROR_MESSAGE),
        response.status,
      );
    }
    return data.revision;
  }

  private async refreshConflict(
    organizationId: string,
    editorVersion: number,
  ): Promise<void> {
    if (
      this.organizationId !== organizationId ||
      !this.isCurrentEditor(editorVersion)
    ) {
      return;
    }
    try {
      const templates = await this.fetchTemplates();
      if (
        this.organizationId !== organizationId ||
        !this.isCurrentEditor(editorVersion)
      ) {
        return;
      }
      runInAction(() => {
        this.items = templates;
        this.conflictMessage = CONFLICT_MESSAGE;
      });
    } catch {
      // Keep the mutation error and the member's local text intact.
    }
  }

  private async fetchTemplates(): Promise<AgentInstructionTemplate[]> {
    const { data, response } = await this.api.GET("/api/templates");
    if (!response.ok || data === undefined) {
      throw new Error(LOAD_ERROR_MESSAGE);
    }
    return data.filter((template) => template.kind === "agent_instructions");
  }

  private prepareEditor(context: AgentInstructionEditorContext): void {
    if (this.organizationId !== context.organizationId) {
      this.resetForOrganization(context.organizationId);
    }
    this.invalidateEditorOperation();
    this.resetEditor();
    this.context = context;
    this.templateId = context.templateId;
  }

  private readStoredDraft(): StoredAgentInstructionDraft | null {
    return this.context === null ? null : this.storage.read(this.context);
  }

  private applyStoredDraft(draft: StoredAgentInstructionDraft): void {
    this.name = draft.name;
    this.body = draft.body;
    this.baseDraftVersion = draft.baseDraftVersion;
    this.savedAt = draft.savedAt;
  }

  private persistEditor(): void {
    if (this.context === null || !this.isEditorDirty) {
      return;
    }
    const savedAt = new Date().toISOString();
    const saved = this.storage.write(this.context, {
      baseDraftVersion: this.baseDraftVersion,
      body: this.body,
      name: this.name,
      savedAt,
      version: 1,
    });
    if (saved) {
      this.savedAt = savedAt;
      this.draftStorageErrorMessage = null;
    } else {
      this.draftStorageErrorMessage = DRAFT_STORAGE_ERROR_MESSAGE;
    }
  }

  private clearEditorDraft(): void {
    if (this.context !== null) {
      this.storage.clear(this.context);
    }
  }

  private resetEditor(): void {
    this.actionErrorMessage = null;
    this.baseDraftVersion = null;
    this.baselineBody = "";
    this.baselineName = "";
    this.body = "";
    this.conflictMessage = null;
    this.context = null;
    this.draftStorageErrorMessage = null;
    this.name = "";
    this.savedAt = null;
    this.templateId = null;
  }

  private resetForOrganization(organizationId: string): void {
    this.invalidateEditorOperation();
    this.loadVersion += 1;
    this.organizationId = organizationId;
    this.items = [];
    this.errorMessage = null;
    this.isLoading = false;
    this.resetEditor();
  }

  private invalidateEditorOperation(): void {
    this.editorVersion += 1;
    this.isSaving = false;
  }

  private isCurrentEditor(editorVersion: number): boolean {
    return this.editorVersion === editorVersion;
  }

  private isCurrentLoad(organizationId: string, loadVersion: number): boolean {
    return (
      this.organizationId === organizationId && this.loadVersion === loadVersion
    );
  }
}

class InstructionActionError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function requireTemplate(
  data: AgentInstructionTemplate | undefined,
  error: unknown,
  response: Response,
): AgentInstructionTemplate {
  if (!response.ok || data === undefined) {
    throw new InstructionActionError(
      getAgentApiErrorMessage(error, ACTION_ERROR_MESSAGE),
      response.status,
    );
  }
  return data;
}

function replaceTemplate(
  templates: readonly AgentInstructionTemplate[],
  replacement: AgentInstructionTemplate,
): AgentInstructionTemplate[] {
  return [
    replacement,
    ...templates.filter((template) => template.id !== replacement.id),
  ];
}

export { AgentInstructionsStore };
