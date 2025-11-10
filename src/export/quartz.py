import re, json
from pathlib import Path
from ..core.ports import ExportAdapter
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

        graph = {"nodes": [], "edges": []}
        for nid in self.vault.list_ids():
            note = self.vault.get(nid)
            if not note:
                continue
            md = note.body.raw

            def link_sub(m):
                spec = m.group(1)
                core = spec.split("|")[0].split("#")[0]
                title = spec.split("|")[-1] if "|" in spec else core
                return f"[{title}](/{core}/)"
            md2 = LINK.sub(link_sub, md)

            # naive transclusion: inline raw of target (anchor resolution omitted here)
            def trans_sub(m):
                core = m.group(1).split("|")[0]
                target_id = core.split("#")[0]
                t = self.vault.get(target_id)
                return t.body.raw if t else f"> MISSING: {target_id}\n"
            md2 = TRANS.sub(trans_sub, md2)

            (out / nid).mkdir(exist_ok=True)
            (out / nid / "index.md").write_text(md2, encoding="utf-8")

            graph["nodes"].append({"id": nid})
            for link in note.body.links:
                graph["edges"].append({"source": nid, "target": link.target.id})

        (out / "graph.json").write_text(json.dumps(graph, indent=2) encoding="utf-8")
