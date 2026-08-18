import type { FC } from "preact/compat";
import { useMemo, useState } from "preact/hooks";
import type { TWidgetInteraction, TWidgetResponseData } from "@eylo";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Flex,
  ScrollArea,
  Stack,
  Text,
  cm,
} from "../index";
import styles from "./WidgetCardList.module.css";
import type { TWidgetCardListPayload } from "./types";

type WidgetCardListProps = {
  payload: TWidgetCardListPayload;
  onInteraction?: (interaction: TWidgetInteraction) => void;
  isReadOnly?: boolean;
  submission?: TWidgetResponseData | null;
};

export const WidgetCardList: FC<WidgetCardListProps> = ({
  payload,
  onInteraction,
  isReadOnly = false,
  submission = null,
}) => {
  const { props } = payload;
  const [selectedIds, setSelectedIds] = useState<string[]>(() =>
    Array.isArray(submission?.data.selectedIds)
      ? submission.data.selectedIds.filter((value): value is string => typeof value === "string")
      : []
  );
  const [isSubmitted, setIsSubmitted] = useState(Boolean(submission));

  const effectiveReadOnly = isReadOnly || isSubmitted;
  const selectionMode = props.selectionMode || "single";

  const selectedCount = useMemo(() => selectedIds.length, [selectedIds]);

  const toggleSelection = (cardId: string): void => {
    if (effectiveReadOnly) {
      return;
    }

    if (selectionMode === "single") {
      setSelectedIds([cardId]);
      return;
    }

    setSelectedIds((previous) =>
      previous.includes(cardId)
        ? previous.filter((currentId) => currentId !== cardId)
        : [...previous, cardId]
    );
  };

  const handleSubmit = (): void => {
    if (selectedIds.length === 0) {
      return;
    }

    setIsSubmitted(true);
    onInteraction?.({
      component: "card_list",
      action: "submit",
      data: { selectedIds },
    });
  };

  return (
    <Card border shadow="sm">
      {props.title || props.description ? (
        <CardHeader>
          {props.title ? <CardTitle>{props.title}</CardTitle> : null}
          {props.description ? <CardDescription>{props.description}</CardDescription> : null}
        </CardHeader>
      ) : null}
      <CardContent>
        <ScrollArea style={{ maxHeight: "24rem" }}>
          <Stack spacing="md">
            {props.cards.map((card) => {
              const isSelected = selectedIds.includes(card.id);

              return (
                <button
                  key={card.id}
                  type="button"
                  className={styles.cardButton}
                  onClick={() => toggleSelection(card.id)}
                  disabled={effectiveReadOnly}
                  aria-pressed={isSelected}
                >
                  <Card
                    border
                    shadow="xs"
                    padding="md"
                    interactive={!effectiveReadOnly}
                    className={cm(isSelected && styles.cardSelected)}
                  >
                    <Stack spacing="sm">
                      {card.image ? (
                        <img src={card.image} alt={card.title} className={styles.cardMedia} />
                      ) : null}
                      <Flex justify="between" align="center" gap="sm">
                        <CardTitle>{card.title}</CardTitle>
                        {card.badge ? <Badge>{card.badge}</Badge> : null}
                      </Flex>
                      {card.description ? <Text variant="muted">{card.description}</Text> : null}
                      {card.price ? <Text semibold>{card.price}</Text> : null}
                      {card.features?.length ? (
                        <ul className={styles.featureList}>
                          {card.features.map((feature) => (
                            <li key={feature}>
                              <Text size="small">{feature}</Text>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </Stack>
                  </Card>
                </button>
              );
            })}
          </Stack>
        </ScrollArea>
      </CardContent>
      <CardFooter>
        <Button
          width="full"
          onClick={handleSubmit}
          disabled={effectiveReadOnly || selectedCount === 0}
        >
          {props.submitLabel || "Select"}
        </Button>
      </CardFooter>
    </Card>
  );
};
