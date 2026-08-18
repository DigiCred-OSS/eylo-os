import type { TCompoundWidgetPayload } from "@eylo";
import type { TDynamicWidgetPayload } from "../../design-system/compositions/types";

export type TWidgetSample = {
  id: string;
  title: string;
  description: string;
  payload?: unknown;
  kind?: "payload" | "runtime_crash";
  category: "individual" | "compound" | "error";
};

// ---------------------------------------------------------------------------
// Individual component samples
// ---------------------------------------------------------------------------

const individualSamples: TWidgetSample[] = [
  {
    id: "booking-form",
    title: "Booking Form",
    description: "Multi-field form using text, select, date, checkbox, and textarea fields.",
    category: "individual",
    payload: {
      component: "form",
      props: {
        title: "Book an appointment",
        description: "Fill out the fields below and submit when ready.",
        submitLabel: "Submit booking",
        fields: [
          {
            type: "text",
            name: "name",
            label: "Your name",
            placeholder: "Jane Doe",
            required: true,
            validation: { minLength: 2 },
          },
          {
            type: "select",
            name: "service",
            label: "Service",
            required: true,
            options: [
              { value: "consultation", label: "Consultation" },
              { value: "follow_up", label: "Follow-up" },
            ],
          },
          {
            type: "date",
            name: "date",
            label: "Preferred date",
            required: true,
            validation: { minDate: "today" },
          },
          {
            type: "checkbox",
            name: "consent",
            label: "Consent",
            placeholder: "I agree to share my information",
            required: true,
          },
          {
            type: "textarea",
            name: "notes",
            label: "Notes",
            placeholder: "Anything else we should know?",
            validation: { maxLength: 180 },
          },
        ],
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "survey-form",
    title: "Survey Form",
    description: "Form with cancel flow and diverse field types.",
    category: "individual",
    payload: {
      component: "form",
      props: {
        title: "Help us tailor your onboarding",
        description: "Answer a few quick questions so the agent can guide you faster.",
        submitLabel: "Send answers",
        cancelLabel: "Skip survey",
        fields: [
          {
            type: "text",
            name: "companyName",
            label: "Company name",
            placeholder: "Acme Inc.",
            required: true,
            validation: { minLength: 2 },
          },
          {
            type: "email",
            name: "workEmail",
            label: "Work email",
            placeholder: "team@example.com",
            required: true,
          },
          {
            type: "select",
            name: "goal",
            label: "What should the agent help with first?",
            required: true,
            options: [
              {
                value: "setup",
                label: "Initial setup",
                description: "Configure the workspace and first flows.",
              },
              {
                value: "migration",
                label: "Migration",
                description: "Bring over data or workflows from another tool.",
              },
              {
                value: "training",
                label: "Team training",
                description: "Get your team comfortable using the agent.",
              },
            ],
            defaultValue: "setup",
          },
          {
            type: "number",
            name: "teamSize",
            label: "How large is your team?",
            defaultValue: 25,
            validation: { min: 1, max: 500 },
          },
          {
            type: "textarea",
            name: "notes",
            label: "Anything else we should know?",
            placeholder: "Share context, constraints, or priorities.",
            validation: { maxLength: 240 },
          },
        ],
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "button-group",
    title: "Button Group",
    description: "Short-choice interaction rendered as a button group.",
    category: "individual",
    payload: {
      component: "button_group",
      props: {
        question: "How should we proceed?",
        buttons: [
          { value: "book", label: "Book now", variant: "primary" },
          { value: "later", label: "Later", variant: "secondary" },
          { value: "cancel", label: "Cancel", variant: "destructive" },
        ],
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "card-list",
    title: "Card List",
    description: "Card-based selection for structured options.",
    category: "individual",
    payload: {
      component: "card_list",
      props: {
        title: "Choose a plan",
        description: "Select the plan that fits best.",
        submitLabel: "Continue",
        selectionMode: "single",
        cards: [
          {
            id: "starter",
            title: "Starter",
            description: "Best for quick setup and lightweight usage.",
            price: "$19/mo",
            features: ["Basic automation", "Email support"],
          },
          {
            id: "growth",
            title: "Growth",
            description: "Balanced package for growing teams.",
            badge: "Popular",
            price: "$49/mo",
            features: ["Priority routing", "Advanced analytics", "Priority support"],
          },
        ],
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "date-picker-date",
    title: "Date Picker (date)",
    description: "Date-only picker with month/day/year selects.",
    category: "individual",
    payload: {
      component: "date_picker",
      props: {
        label: "Choose a date",
        name: "preferred_date",
        description: "Select the date that works for you.",
        mode: "date",
        required: true,
        submitLabel: "Confirm date",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "date-picker-time",
    title: "Date Picker (time)",
    description: "Time-only picker with hour/minute selects.",
    category: "individual",
    payload: {
      component: "date_picker",
      props: {
        label: "Preferred time",
        name: "preferred_time",
        description: "Pick a time slot.",
        mode: "time",
        required: true,
        submitLabel: "Confirm time",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "date-picker-datetime",
    title: "Date Picker (datetime)",
    description: "Combined date + time picker.",
    category: "individual",
    payload: {
      component: "date_picker",
      props: {
        label: "Choose a meeting time",
        name: "meeting_at",
        description: "Pick a date and time that works for you.",
        mode: "datetime",
        required: true,
        submitLabel: "Confirm time",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "alert-info",
    title: "Alert (info)",
    description: "Informational alert banner.",
    category: "individual",
    payload: {
      component: "alert",
      props: {
        title: "Heads up",
        message: "The widget is currently running in sample mode without backend integration.",
        severity: "info",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "alert-warning",
    title: "Alert (warning)",
    description: "Warning alert with dismissible option.",
    category: "individual",
    payload: {
      component: "alert",
      props: {
        title: "Rate limit approaching",
        message: "You've used 90% of your monthly API quota. Consider upgrading your plan.",
        severity: "warning",
        dismissible: true,
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "text-body",
    title: "Text (body)",
    description: "Simple body text block.",
    category: "individual",
    payload: {
      component: "text",
      props: {
        content:
          "Welcome to Eylo! Our agent is ready to help you set up your workspace. " +
          "Just tell us what you need and we'll guide you through the process step by step.",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "text-heading",
    title: "Text (heading)",
    description: "Heading text variant.",
    category: "individual",
    payload: {
      component: "text",
      props: {
        content: "Getting started with your workspace",
        variant: "heading",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "image",
    title: "Image",
    description: "Image with alt text and caption.",
    category: "individual",
    payload: {
      component: "image",
      props: {
        src: "https://placehold.co/600x300/1a1a1a/666?text=Widget+Preview",
        alt: "Widget preview placeholder",
        caption: "A sample image rendered inside the widget.",
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "progress",
    title: "Progress",
    description: "Step progress indicator with labeled steps.",
    category: "individual",
    payload: {
      component: "progress",
      props: {
        currentStep: 2,
        totalSteps: 4,
        label: "Onboarding progress",
        steps: [
          { label: "Account created", status: "completed" },
          { label: "Workspace configured", status: "active" },
          { label: "Team invited", status: "pending" },
          { label: "First agent deployed", status: "pending" },
        ],
      },
    } satisfies TDynamicWidgetPayload,
  },
  {
    id: "table",
    title: "Table",
    description: "Data table with columns and rows.",
    category: "individual",
    payload: {
      component: "table",
      props: {
        caption: "Recent conversations",
        columns: [
          { key: "id", label: "#", align: "center" },
          { key: "contact", label: "Contact" },
          { key: "status", label: "Status", align: "center" },
          { key: "messages", label: "Messages", align: "right" },
        ],
        rows: [
          { id: 1, contact: "Jane Cooper", status: "Active", messages: 24 },
          { id: 2, contact: "Wade Warren", status: "Resolved", messages: 8 },
          { id: 3, contact: "Esther Howard", status: "Pending", messages: 3 },
        ],
      },
    } satisfies TDynamicWidgetPayload,
  },
];

// ---------------------------------------------------------------------------
// Compound component samples (adjacency-list format)
// ---------------------------------------------------------------------------

const compoundSamples: TWidgetSample[] = [
  {
    id: "compound-onboarding",
    title: "⊞ Onboarding Flow",
    description: "Stack layout: progress indicator → heading → onboarding form.",
    category: "compound",
    payload: {
      root: "root",
      components: [
        {
          id: "root",
          component: "stack",
          props: { spacing: "md" },
          children: ["progress-1", "heading-1", "onboarding-form"],
        },
        {
          id: "progress-1",
          component: "progress",
          props: {
            currentStep: 1,
            totalSteps: 3,
            label: "Setup progress",
            steps: [
              { label: "Account info", status: "active" },
              { label: "Preferences", status: "pending" },
              { label: "Confirmation", status: "pending" },
            ],
          },
        },
        {
          id: "heading-1",
          component: "text",
          props: { content: "Let's set up your account", variant: "heading" },
        },
        {
          id: "onboarding-form",
          component: "form",
          props: {
            title: "Account details",
            description: "We'll use this to personalize your experience.",
            submitLabel: "Continue",
            fields: [
              { type: "text", name: "fullName", label: "Full name", required: true },
              { type: "email", name: "email", label: "Email", required: true },
              {
                type: "select",
                name: "role",
                label: "Your role",
                options: [
                  { value: "founder", label: "Founder" },
                  { value: "engineer", label: "Engineer" },
                  { value: "pm", label: "Product Manager" },
                  { value: "support", label: "Support" },
                ],
              },
            ],
          },
        },
      ],
    } satisfies TCompoundWidgetPayload,
  },
  {
    id: "compound-alert-choices",
    title: "⊞ Alert + Choices",
    description: "Stack layout: warning alert → explanatory text → action buttons.",
    category: "compound",
    payload: {
      root: "root",
      components: [
        {
          id: "root",
          component: "stack",
          props: { spacing: "md" },
          children: ["warn", "explanation", "actions"],
        },
        {
          id: "warn",
          component: "alert",
          props: {
            title: "Payment overdue",
            message:
              "Your subscription payment failed. Please update your billing information to continue.",
            severity: "warning",
          },
        },
        {
          id: "explanation",
          component: "text",
          props: {
            content:
              "If no action is taken within 7 days, your workspace will be downgraded to the free tier.",
          },
        },
        {
          id: "actions",
          component: "button_group",
          props: {
            question: "What would you like to do?",
            buttons: [
              { value: "update_billing", label: "Update billing", variant: "primary" },
              { value: "contact_support", label: "Contact support", variant: "secondary" },
              { value: "dismiss", label: "Remind me later", variant: "ghost" },
            ],
          },
        },
      ],
    } satisfies TCompoundWidgetPayload,
  },
  {
    id: "compound-dashboard",
    title: "⊞ Mini Dashboard",
    description:
      "Section with table + image side-by-side in a row, plus a divider and action buttons.",
    category: "compound",
    payload: {
      root: "root",
      components: [
        {
          id: "root",
          component: "stack",
          props: { spacing: "md" },
          children: ["title-section", "content-row", "sep", "actions"],
        },
        {
          id: "title-section",
          component: "section",
          props: {
            title: "Weekly summary",
            description: "Performance overview for March 11–17, 2026.",
          },
          children: ["summary-text"],
        },
        {
          id: "summary-text",
          component: "text",
          props: {
            content:
              "Your agents handled 342 conversations this week, a 15% increase over last week.",
          },
        },
        {
          id: "content-row",
          component: "row",
          props: { spacing: "md", align: "start" },
          children: ["stats-table", "chart-image"],
        },
        {
          id: "stats-table",
          component: "table",
          props: {
            caption: "Top agents by volume",
            columns: [
              { key: "agent", label: "Agent" },
              { key: "conversations", label: "Conversations", align: "right" },
              { key: "resolution", label: "Resolution %", align: "right" },
            ],
            rows: [
              { agent: "Support Bot", conversations: 187, resolution: "94%" },
              { agent: "Sales Agent", conversations: 98, resolution: "82%" },
              { agent: "Onboarding", conversations: 57, resolution: "91%" },
            ],
          },
        },
        {
          id: "chart-image",
          component: "image",
          props: {
            src: "https://placehold.co/300x200/1a1a1a/666?text=Weekly+Chart",
            alt: "Weekly conversation volume chart",
            caption: "Conversations per day",
          },
        },
        {
          id: "sep",
          component: "divider",
          props: { label: "Actions" },
        },
        {
          id: "actions",
          component: "button_group",
          props: {
            buttons: [
              { value: "export", label: "Export report", variant: "primary" },
              { value: "details", label: "View details", variant: "outline" },
            ],
          },
        },
      ],
    } satisfies TCompoundWidgetPayload,
  },
  {
    id: "compound-scheduling",
    title: "⊞ Scheduling Wizard",
    description: "Section-wrapped date picker + form in a stack, with progress bar.",
    category: "compound",
    payload: {
      root: "root",
      components: [
        {
          id: "root",
          component: "stack",
          props: { spacing: "md" },
          children: ["progress", "heading", "date-section", "details-section"],
        },
        {
          id: "progress",
          component: "progress",
          props: {
            currentStep: 2,
            totalSteps: 3,
            steps: [
              { label: "Select type", status: "completed" },
              { label: "Pick time", status: "active" },
              { label: "Confirm", status: "pending" },
            ],
          },
        },
        {
          id: "heading",
          component: "text",
          props: { content: "Schedule your consultation", variant: "heading" },
        },
        {
          id: "date-section",
          component: "section",
          props: { title: "When works for you?" },
          children: ["date-picker"],
        },
        {
          id: "date-picker",
          component: "date_picker",
          props: {
            label: "Meeting date & time",
            name: "consultation_at",
            mode: "datetime",
            required: true,
            submitLabel: "Lock in time",
          },
        },
        {
          id: "details-section",
          component: "section",
          props: { title: "Additional details", collapsible: true },
          children: ["details-form"],
        },
        {
          id: "details-form",
          component: "form",
          props: {
            title: "Tell us more",
            submitLabel: "Confirm booking",
            fields: [
              {
                type: "text",
                name: "topic",
                label: "Topic",
                placeholder: "What would you like to discuss?",
              },
              {
                type: "select",
                name: "duration",
                label: "Duration",
                options: [
                  { value: "15", label: "15 minutes" },
                  { value: "30", label: "30 minutes" },
                  { value: "60", label: "1 hour" },
                ],
                defaultValue: "30",
              },
              {
                type: "textarea",
                name: "notes",
                label: "Notes",
                placeholder: "Anything we should prepare?",
                validation: { maxLength: 500 },
              },
            ],
          },
        },
      ],
    } satisfies TCompoundWidgetPayload,
  },
  {
    id: "compound-card-selection",
    title: "⊞ Product Selection",
    description: "Heading + card list + alert footer in a stack.",
    category: "compound",
    payload: {
      root: "root",
      components: [
        {
          id: "root",
          component: "stack",
          props: { spacing: "md" },
          children: ["heading", "description", "cards", "note"],
        },
        {
          id: "heading",
          component: "text",
          props: { content: "Choose your integration", variant: "heading" },
        },
        {
          id: "description",
          component: "text",
          props: {
            content:
              "Select the platforms you'd like to connect. You can always add more later from settings.",
          },
        },
        {
          id: "cards",
          component: "card_list",
          props: {
            selectionMode: "multiple",
            submitLabel: "Connect selected",
            cards: [
              {
                id: "slack",
                title: "Slack",
                description: "Receive agent notifications and interact via Slack channels.",
                badge: "Popular",
                features: ["Real-time alerts", "Thread replies", "Slash commands"],
              },
              {
                id: "zendesk",
                title: "Zendesk",
                description: "Sync tickets and let the agent auto-respond to common queries.",
                features: ["Ticket sync", "Auto-tagging", "CSAT routing"],
              },
              {
                id: "hubspot",
                title: "HubSpot",
                description: "Enrich contacts and log agent interactions as CRM activities.",
                features: ["Contact enrichment", "Activity logging"],
              },
            ],
          },
        },
        {
          id: "note",
          component: "alert",
          props: {
            message:
              "Each integration requires OAuth authorization. You'll be redirected after selection.",
            severity: "info",
          },
        },
      ],
    } satisfies TCompoundWidgetPayload,
  },
];

// ---------------------------------------------------------------------------
// Error / edge-case samples
// ---------------------------------------------------------------------------

const errorSamples: TWidgetSample[] = [
  {
    id: "invalid-form",
    title: "⚠ Invalid Payload",
    description: "A deliberately broken payload to demonstrate SDK-side validation.",
    category: "error",
    payload: {
      component: "form",
      props: {
        title: "Broken form",
        fields: [{ type: "select", name: "missingOptions", label: "Missing options" }],
      },
    },
  },
  {
    id: "hallucinated-component",
    title: "⚠ Hallucinated Component",
    description: "Unknown component type rejected by validation.",
    category: "error",
    payload: {
      component: "carousel",
      props: { title: "This should never render" },
    },
  },
  {
    id: "invalid-card-list",
    title: "⚠ Invalid Card List",
    description: "Structurally invalid payload with duplicate IDs.",
    category: "error",
    payload: {
      component: "card_list",
      props: {
        title: "Broken cards",
        cards: [
          { id: "dup", title: "First" },
          { id: "dup", title: "Second", unsupported: true },
        ],
      },
    },
  },
  {
    id: "invalid-compound-cycle",
    title: "⚠ Compound Cycle",
    description: "Compound payload with a cycle — node A references B, B references A.",
    category: "error",
    payload: {
      root: "a",
      components: [
        { id: "a", component: "stack", props: { spacing: "md" }, children: ["b"] },
        { id: "b", component: "stack", props: { spacing: "md" }, children: ["a"] },
      ],
    },
  },
  {
    id: "invalid-compound-orphan",
    title: "⚠ Compound Orphan",
    description: "Compound payload with an unreachable orphan node.",
    category: "error",
    payload: {
      root: "root",
      components: [
        { id: "root", component: "stack", props: { spacing: "md" }, children: ["child"] },
        { id: "child", component: "text", props: { content: "I'm reachable." } },
        { id: "orphan", component: "text", props: { content: "I'm not." } },
      ],
    },
  },
  {
    id: "runtime-render-crash",
    title: "⚠ Renderer Crash",
    description: "Forces a renderer crash to verify the error boundary.",
    category: "error",
    kind: "runtime_crash",
  },
];

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export const widgetSamples: TWidgetSample[] = [
  ...individualSamples,
  ...compoundSamples,
  ...errorSamples,
];
