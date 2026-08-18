import type { FilterGroup, FilterNode } from "./filter-types.ts";

function appendFilterNode<Property extends string>(
  root: FilterGroup<Property>,
  parentGroupId: string,
  node: FilterNode<Property>,
): FilterGroup<Property> {
  if (root.id === parentGroupId) {
    return { ...root, children: [...root.children, node] };
  }

  return {
    ...root,
    children: root.children.map((child) =>
      child.type === "group"
        ? appendFilterNode(child, parentGroupId, node)
        : child,
    ),
  };
}

function replaceFilterNode<Property extends string>(
  root: FilterGroup<Property>,
  replacement: FilterNode<Property>,
): FilterGroup<Property> {
  if (root.id === replacement.id) {
    return replacement.type === "group" ? replacement : root;
  }

  return {
    ...root,
    children: root.children.map((child) => {
      if (child.id === replacement.id) {
        return replacement;
      }
      return child.type === "group"
        ? replaceFilterNode(child, replacement)
        : child;
    }),
  };
}

function removeFilterNode<Property extends string>(
  root: FilterGroup<Property>,
  nodeId: string,
): FilterGroup<Property> {
  return {
    ...root,
    children: root.children
      .filter((child) => child.id !== nodeId)
      .map((child) =>
        child.type === "group" ? removeFilterNode(child, nodeId) : child,
      ),
  };
}

function pruneFilterTree<Property extends string>(
  root: FilterGroup<Property>,
): FilterGroup<Property> {
  const children: FilterNode<Property>[] = [];
  for (const child of root.children) {
    if (child.type === "condition") {
      if (child.values.length > 0) {
        children.push(child);
      }
      continue;
    }
    const group = pruneFilterTree(child);
    if (group.children.length > 0) {
      children.push(group);
    }
  }
  return { ...root, children };
}

export {
  appendFilterNode,
  pruneFilterTree,
  removeFilterNode,
  replaceFilterNode,
};
