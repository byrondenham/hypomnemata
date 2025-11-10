import json
import re
from pathlib import Path
from typing import Any

from ..core.model import Anchor
from ..core.ports import ExportAdapter
from ..core.slicer import slice_by_anchor
from ..core.vault import Vault

LINK = re.compile(r"\[\[(.*?)\]\]")
TRANS = re.compile(r"!\[\[(.*?)\]\]")


class QuartzAdapter(ExportAdapter):
    def __init__(self, vault: Vault, out: Path):
        self.vault = vault
        self.out = out

    def export_all(self, out_dir: str | None = None) -> None:
        out = self.out if out_dir is None else Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        graph: dict[str, list[dict[str, Any]]] = {"nodes": [], "edges": []}
        for nid in self.vault.list_ids():
            note = self.vault.get(nid)
            if not note:
                continue
            md = note.body.raw

            # slice-based transclusion (must be done before link substitution)
            def trans_sub(m: re.Match[str]) -> str:
                spec = m.group(1)
                core = spec.split("|")[0]
                
                # Parse target id and anchor
                anchor = None
                if "#^" in core:
                    target_id, label = core.split("#^", 1)
                    anchor = Anchor(kind="block", value=label.strip())
                elif "#" in core:
                    target_id, slug = core.split("#", 1)
                    anchor = Anchor(kind="heading", value=slug.strip())
                else:
                    target_id = core
                
                target_id = target_id.strip()
                
                # Get target note
                t = self.vault.get(target_id)
                if not t:
                    return f"> MISSING: {target_id}\n"
                
                # Get slice
                start, end = slice_by_anchor(t, anchor)
                
                if start == end and anchor:
                    # Anchor not found
                    anchor_repr = f"^{anchor.value}" if anchor.kind == "block" else anchor.value
                    return f"> MISSING ANCHOR: {target_id}#{anchor_repr}\n"
                
                return t.body.raw[start:end]

            md2 = TRANS.sub(trans_sub, md)

            def link_sub(m: re.Match[str]) -> str:
                spec = m.group(1)
                core = spec.split("|")[0].split("#")[0]
                title = spec.split("|")[-1] if "|" in spec else core
                return f"[{title}](/{core}/)"

            md2 = LINK.sub(link_sub, md2)

            (out / nid).mkdir(exist_ok=True)
            (out / nid / "index.md").write_text(md2, encoding="utf-8")

            graph["nodes"].append({"id": nid})
            for link in note.body.links:
                graph["edges"].append({"source": nid, "target": link.target.id})

        (out / "graph.json").write_text(
            json.dumps(graph, indent=2), encoding="utf-8"
        )
