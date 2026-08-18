import type { FC } from "preact/compat";
import type { WidgetRendererProps } from "../../components/DynamicWidget/registry";
import type { TWidgetProgressPayload } from "./types";
import { Progress } from "../components/Progress";
import { Text } from "../components/Typography";
import { Stack } from "../components/Stack";
import { Flex } from "../components/Flex";

export const WidgetProgress: FC<WidgetRendererProps<TWidgetProgressPayload>> = ({ payload }) => {
  const { currentStep, totalSteps, label, steps } = payload.props;
  const percent = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0;

  return (
    <Stack spacing="sm" direction="vertical">
      {label ? <Text semibold>{label}</Text> : null}
      <Progress value={percent} />
      {steps ? (
        <Flex gap="sm" wrap="wrap">
          {steps.map((step, i) => (
            <Text
              key={i}
              size="small"
              variant={
                step.status === "completed"
                  ? "success"
                  : step.status === "active"
                    ? "default"
                    : "muted"
              }
              semibold={step.status === "active"}
            >
              {step.label}
            </Text>
          ))}
        </Flex>
      ) : (
        <Text size="small" variant="muted">
          Step {currentStep} of {totalSteps}
        </Text>
      )}
    </Stack>
  );
};
