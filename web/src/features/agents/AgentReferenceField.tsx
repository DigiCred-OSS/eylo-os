import { observer } from "mobx-react-lite";

import { useRootStore } from "@/app/use-root-store";
import { ProviderConfigReferenceField } from "@/features/providers/ProviderConfigReferenceField";
import type { ProviderReferenceField } from "@/features/providers/providers.types";

interface AgentReferenceFieldProps {
  description: string;
  field: ProviderReferenceField;
  label: string;
  onChange: (value: string | null) => void;
  organizationId: string;
  value: string | null;
}

const AgentReferenceField = observer(function AgentReferenceField(
  props: AgentReferenceFieldProps,
) {
  const { agents } = useRootStore();
  return (
    <ProviderConfigReferenceField
      {...props}
      references={agents.form.references}
    />
  );
});

export { AgentReferenceField };
