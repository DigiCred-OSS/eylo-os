import type { FC } from "preact/compat";
import type { WidgetRendererProps } from "../../components/DynamicWidget/registry";
import type { TWidgetTablePayload } from "./types";
import { Text } from "../components/Typography";
import { Stack } from "../components/Stack";

export const WidgetTable: FC<WidgetRendererProps<TWidgetTablePayload>> = ({ payload }) => {
  const { columns, rows, caption } = payload.props;

  return (
    <Stack spacing="xs" direction="vertical">
      <div style={{ overflowX: "auto", width: "100%" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "var(--font-size-sm, 0.875rem)",
          }}
        >
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={{
                    textAlign: col.align ?? "left",
                    padding: "0.5rem 0.75rem",
                    borderBottom: "2px solid hsl(var(--border))",
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                  }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td
                    key={col.key}
                    style={{
                      textAlign: col.align ?? "left",
                      padding: "0.5rem 0.75rem",
                      borderBottom: "1px solid hsl(var(--border))",
                    }}
                  >
                    {String(row[col.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {caption ? (
        <Text size="small" variant="muted">
          {caption}
        </Text>
      ) : null}
    </Stack>
  );
};
