import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..adapters.sqlite_index import SQLiteIndex
from ..core.model import Anchor
from ..core.ports import ExportAdapter
from ..core.slicer import slice_by_anchor
from ..core.vault import Vault

LINK = re.compile(r"\[\[(.*?)\]\]")
TRANS = re.compile(r"!\[\[(.*?)\]\]")


class QuartzAdapter(ExportAdapter):
    def __init__(
        self,
        vault: Vault,
        out: Path,
        index: Any = None,
        assets_dir: Path | None = None,
        katex_auto: bool = False,
    ):
        self.vault = vault
        self.out = out
        self.index = index
        self.assets_dir = assets_dir
        self.katex_auto = katex_auto

    def export_all(self, out_dir: str | None = None) -> None:
        out = self.out if out_dir is None else Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Get title lookup if we have SQLiteIndex
        title_map = {}
        has_math_global = False
        if self.index and isinstance(self.index, SQLiteIndex):
            conn = self.index._conn()
            try:
                rows = conn.execute("SELECT id, title, has_math FROM notes").fetchall()
                for note_id, title, has_math in rows:
                    if title:
                        title_map[note_id] = title
                    if has_math:
                        has_math_global = True
            finally:
                conn.close()

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
                    return f"> **Hypo:** missing note `{target_id}`\n"
                
                # Get slice
                start, end = slice_by_anchor(t, anchor)
                
                if start == end and anchor:
                    # Anchor not found
                    anchor_repr = f"^{anchor.value}" if anchor.kind == "block" else anchor.value
                    return f"> **Hypo:** missing anchor `{target_id}#{anchor_repr}`\n"
                
                return t.body.raw[start:end]

            md2 = TRANS.sub(trans_sub, md)

            def link_sub(m: re.Match[str]) -> str:
                spec = m.group(1)
                core = spec.split("|")[0].split("#")[0]
                title = spec.split("|")[-1] if "|" in spec else core
                return f"[{title}](/{core}/)"

            md2 = LINK.sub(link_sub, md2)
            
            # Add title as H1 if available and not already present
            title = title_map.get(nid, "")
            if title and not md2.startswith("#"):
                md2 = f"# {title}\n\n{md2}"

            (out / nid).mkdir(exist_ok=True)
            (out / nid / "index.md").write_text(md2, encoding="utf-8")

            graph["nodes"].append({"id": nid, "title": title})
            for link in note.body.links:
                graph["edges"].append({"source": nid, "target": link.target.id})

        (out / "graph.json").write_text(
            json.dumps(graph, indent=2), encoding="utf-8"
        )
        
        # Copy assets if requested
        if self.assets_dir and self.assets_dir.exists():
            dest_assets = out / "assets"
            if dest_assets.exists():
                shutil.rmtree(dest_assets)
            shutil.copytree(self.assets_dir, dest_assets)
        
        # Write KaTeX flag if needed
        if self.katex_auto and has_math_global:
            katex_flag = out / ".katex"
            katex_flag.write_text("", encoding="utf-8")

