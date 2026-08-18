function getAgentApiErrorMessage(error: unknown, fallback: string): string {
  if (typeof error !== "object" || error === null || !("detail" in error)) {
    return fallback;
  }

  const detail = error.detail;
  if (typeof detail === "string" && detail.trim() !== "") {
    return detail.slice(0, 500);
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (
          typeof item !== "object" ||
          item === null ||
          !("msg" in item) ||
          typeof item.msg !== "string"
        ) {
          return null;
        }

        return item.msg;
      })
      .filter((message): message is string => message !== null);

    if (messages.length > 0) {
      return messages.join(" ").slice(0, 500);
    }
  }

  return fallback;
}

export { getAgentApiErrorMessage };
