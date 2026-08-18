import type { FC } from "preact/compat";
import { useMemo, useState } from "preact/hooks";
import {
  getActiveWidgetComponents,
  isCompoundWidgetPayload,
  validateCompoundWidgetPayload,
  validateWidgetPayload,
  type TWidgetInteraction,
} from "@eylo";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Code,
  Flex,
  ScrollArea,
  Stack,
  Text,
} from "../../design-system";
import {
  DynamicWidgetRenderBoundary,
  DynamicWidgetRenderer,
  InvalidDynamicWidgetPayload,
} from "../DynamicWidget";
import { registerDynamicWidgetComponents } from "../../design-system/compositions/register";
import { widgetSamples, type TWidgetSample } from "./samples";
import styles from "./WidgetSamplesScreen.module.css";

registerDynamicWidgetComponents();

const ThrowingSampleRenderer: FC = () => {
  throw new Error("Intentional sample renderer crash");
};

const CATEGORY_LABELS: Record<TWidgetSample["category"], string> = {
  individual: "Individual",
  compound: "Compound",
  error: "Error / Edge cases",
};

const CATEGORIES: TWidgetSample["category"][] = ["individual", "compound", "error"];

const WidgetSamplesScreen: FC = () => {
  const [activeSampleId, setActiveSampleId] = useState(widgetSamples[0]?.id || "");
  const [interactions, setInteractions] = useState<TWidgetInteraction[]>([]);

  const activeSample = useMemo(
    () => widgetSamples.find((sample) => sample.id === activeSampleId) || widgetSamples[0],
    [activeSampleId]
  );

  const validation = useMemo(() => {
    if (activeSample?.kind === "runtime_crash" || !activeSample?.payload) return null;
    if (isCompoundWidgetPayload(activeSample.payload)) {
      return validateCompoundWidgetPayload(activeSample.payload);
    }
    return validateWidgetPayload(activeSample.payload);
  }, [activeSample]);

  const activeComponents = useMemo(() => getActiveWidgetComponents(), []);

  const handleInteraction = (interaction: TWidgetInteraction): void => {
    setInteractions((previous) => [interaction, ...previous].slice(0, 10));
  };

  return (
    <div className={styles.root}>
      <Stack spacing="lg">
        <div>
          <Text as="span" size="small" variant="muted">
            Widget samples mode
          </Text>
          <CardTitle>Dynamic widget playground</CardTitle>
          <CardDescription>
            Validate registered payloads and render the active widget subset before backend
            integration.
          </CardDescription>
        </div>

        <div className={styles.layout}>
          <div className={styles.sidebar}>
            <Card border shadow="sm">
              <CardHeader>
                <CardTitle>Registered components</CardTitle>
                <CardDescription>
                  Active subset currently exposed by the SDK registry.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Stack spacing="sm">
                  <Flex wrap="wrap" gap="xs">
                    {activeComponents.map((component) => (
                      <Badge key={component.type}>{component.type}</Badge>
                    ))}
                  </Flex>
                  <ScrollArea className={styles.sampleList}>
                    <Stack spacing="md">
                      {CATEGORIES.map((category) => {
                        const items = widgetSamples.filter((s) => s.category === category);
                        if (items.length === 0) return null;
                        return (
                          <Stack key={category} spacing="xs">
                            <Text size="small" semibold variant="muted">
                              {CATEGORY_LABELS[category]}
                            </Text>
                            {items.map((sample) => (
                              <Button
                                key={sample.id}
                                variant={sample.id === activeSample?.id ? "default" : "outline"}
                                size="sm"
                                onClick={() => setActiveSampleId(sample.id)}
                                width="full"
                              >
                                {sample.title}
                              </Button>
                            ))}
                          </Stack>
                        );
                      })}
                    </Stack>
                  </ScrollArea>
                </Stack>
              </CardContent>
            </Card>
          </div>

          <Stack spacing="lg">
            <Card border shadow="sm" className={styles.previewPanel}>
              <CardHeader>
                <Flex gap="xs" align="center">
                  <CardTitle>{activeSample?.title}</CardTitle>
                  <Badge variant={activeSample?.category === "compound" ? "outline" : "default"}>
                    {activeSample?.category}
                  </Badge>
                </Flex>
                <CardDescription>{activeSample?.description}</CardDescription>
              </CardHeader>
              <CardContent>
                {activeSample?.kind === "runtime_crash" ? (
                  <DynamicWidgetRenderBoundary
                    component="sample-runtime-crash"
                    fallback={
                      <Text variant="muted">
                        Renderer crash captured. Check the console for the logged failure.
                      </Text>
                    }
                  >
                    <ThrowingSampleRenderer />
                  </DynamicWidgetRenderBoundary>
                ) : activeSample && validation?.ok ? (
                  <DynamicWidgetRenderer
                    payload={validation.value}
                    onInteraction={handleInteraction}
                  />
                ) : validation && !validation.ok ? (
                  <InvalidDynamicWidgetPayload issues={validation.issues} />
                ) : (
                  <Text variant="muted">No preview available for this sample.</Text>
                )}
              </CardContent>
            </Card>

            <Card border shadow="sm">
              <CardHeader>
                <CardTitle>Interaction log</CardTitle>
                <CardDescription>
                  Latest interactions emitted by the rendered widget.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {interactions.length === 0 ? (
                  <Text variant="muted">
                    Interact with a sample to see the structured output here.
                  </Text>
                ) : (
                  <ScrollArea className={styles.interactionLog}>
                    <Stack spacing="sm">
                      {interactions.map((interaction, index) => (
                        <Card
                          key={`${interaction.component}-${interaction.action}-${index}`}
                          border
                          shadow="xs"
                        >
                          <CardContent>
                            <Stack spacing="xs">
                              <Flex gap="xs" align="center">
                                <Badge>{interaction.component}</Badge>
                                <Code>{interaction.action}</Code>
                              </Flex>
                              <pre className={styles.codeBlock}>
                                {JSON.stringify(interaction.data, null, 2)}
                              </pre>
                            </Stack>
                          </CardContent>
                        </Card>
                      ))}
                    </Stack>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          </Stack>

          <Stack spacing="lg">
            <Card border shadow="sm">
              <CardHeader>
                <CardTitle>Payload</CardTitle>
                <CardDescription>
                  The JSON payload currently being validated and rendered.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className={styles.codeBlock}>
                  {JSON.stringify(
                    activeSample?.payload ?? { sample: activeSample?.kind ?? "none" },
                    null,
                    2
                  )}
                </pre>
              </CardContent>
            </Card>

            <Card border shadow="sm">
              <CardHeader>
                <CardTitle>Validation</CardTitle>
                <CardDescription>
                  SDK-side validation result using the registered component schemas.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Stack spacing="sm">
                  <Badge
                    variant={
                      validation?.ok || activeSample?.kind === "runtime_crash"
                        ? "success"
                        : "destructive"
                    }
                  >
                    {activeSample?.kind === "runtime_crash"
                      ? "Crash boundary sample"
                      : validation?.ok
                        ? "Valid payload"
                        : "Invalid payload"}
                  </Badge>
                  {activeSample?.kind === "runtime_crash" ? (
                    <Text variant="muted">
                      This sample bypasses payload validation and verifies that renderer exceptions
                      are isolated.
                    </Text>
                  ) : !validation?.ok ? (
                    <pre className={styles.codeBlock}>
                      {JSON.stringify(validation?.issues, null, 2)}
                    </pre>
                  ) : (
                    <Text variant="muted">
                      The payload matches the currently registered component schema.
                    </Text>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Stack>
        </div>
      </Stack>
    </div>
  );
};

export default WidgetSamplesScreen;
