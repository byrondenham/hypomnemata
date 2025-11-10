import argparse
from pathlib import Path
from .adapters.fs_storage import FsStorage
from .adapters.yaml_codec import YamlFrontmatter, MarkdownNoteCodec
from .adapters.markdown_parser import MarkdownParser
from .adapters.idgen import HexId
from .core.vault import Vault
from .core.meta import MetaBag
from .core.model import Note
from .adapters.resolver_index import DefaultResolver, InMemoryIndex


def build_vault(root: Path) -> Vault:
    storage = FsStorage(root)
    codec = MarkdownNoteCodec(YamlFrontmatter())
    parser = MarkdownParser()
    return Vault(storage, parser, codec)


def main():
    ap = argparse.ArgumentParser("hypo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ap_new = sub.add_parser("new").add_argument("--meta", action="append", default=[])
    ap_find = sub.add_parser("find").add_argument("query")
    ap_open = sub.add_parser("open").add_argument("id")
    ap_ls = sub.add_parser("ls")
    args = ap.parse_args()

    root = Path("./vault")
    v = build_vault(root)
    if args.cmd == "new":
        nid = HexId().new_id()
        mb = MetaBag()
        for kv in args.meta:
            k, _, val = kv.partition("=")
            mb[k.strip()] = val.strip()
        body = "# \n"
        note = v.parser.parse(body, nid)
        v.put(Note(id=nid, meta=mb, body=note))
        print(nid)
    elif args.cmd == "find":
        idx = InMemoryIndex(v)
        idx.rebuild()
        print("\n".join(idx.search(args.query)))
    elif args.cmd == "open":
        n = v.get(args.id)
        print(n.body.raw if n else "not found")
    elif args.cmd == "ls":
        for nid in v.list_ids():
            print(nid)


if __name__ == "__main__":
    main()
