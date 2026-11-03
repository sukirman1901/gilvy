"""Opt-in measured flow layout. Explicit legacy coordinates are not rewritten."""
from gilvy.errors import GilvyError


def layout_groups(nodes):
    for node in nodes:
        if node["type"] != "group":
            continue
        layout_groups(node["children"])
        config = node.get("layout")
        if config is None:
            continue
        if (not isinstance(config, dict) or set(config)-{"direction", "gap", "padding", "align", "justify"}
            or config.get("direction", "row") not in ("row", "column")
            or config.get("align", "center") not in ("start", "center", "end")
            or config.get("justify", "start") not in ("start", "center", "end")):
            raise GilvyError(f"layer {node['id']}: invalid layout")
        gap, pad = config.get("gap", 0), config.get("padding", 0)
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not 0 <= v <= 4096 for v in (gap, pad)):
            raise GilvyError("layout gap/padding must be finite 0..4096")
        row = config.get("direction", "row") == "row"
        main, cross = ("width", "height") if row else ("height", "width")
        required = sum(c[main] for c in node["children"]) + gap * max(0, len(node["children"])-1)
        available = node[main] - 2*pad
        if required > available or any(c[cross] > node[cross]-2*pad for c in node["children"]):
            raise GilvyError(f"layout overflows group {node['id']}")
        cursor = pad + {"start": 0, "center": .5, "end": 1}[config.get("justify", "start")] * (available-required)
        for child in node["children"]:
            if any(p in child or p in child.get("keyframes", {}) for p in ("x", "y", "pivot_x", "pivot_y")):
                raise GilvyError(f"flow child {child['id']}: x/y/pivot are layout-owned; animate a nested child")
            center = cursor + child[main]/2
            side = pad + child[cross]/2 + {"start": 0, "center": .5, "end": 1}[config.get("align", "center")] * (node[cross]-2*pad-child[cross])
            child.update(dict(zip(("x", "y"), (center, side) if row else (side, center))))
            cursor += child[main]+gap
