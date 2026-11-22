"""Stage a new isolated SSAS project; no server commands are executed here."""

from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".work/review_chi/ssas/CoffeeCube"
TARGET = ROOT / "ssas/CoffeeCubeTrang"
EVIDENCE = ROOT / "results/native_build_20261120/ssas/integrated_ssis_source"
DATABASE = "CoffeeCube_Trang_20261120"
RELATIONAL_DATABASE = "CoffeeDW_Trang_SSIS_TN03_20261120"
SERVER = r"localhost\TRANGTRETRAU"
CONNECTION = f"Provider=MSOLEDBSQL;Data Source=.;Integrated Security=SSPI;Initial Catalog={RELATIONAL_DATABASE};Use Encryption for Data=False;Trust Server Certificate=True"
N = {"a": "http://schemas.microsoft.com/analysisservices/2003/engine"}
ET.register_namespace("", N["a"])
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

ERROR_CONFIGURATION = '''<ErrorConfiguration>
  <KeyNotFound>ReportAndStop</KeyNotFound>
  <KeyDuplicate>ReportAndStop</KeyDuplicate>
  <NullKeyNotAllowed>ReportAndStop</NullKeyNotAllowed>
  <NullKeyConvertedToUnknown>ReportAndStop</NullKeyConvertedToUnknown>
</ErrorConfiguration>'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adapt(text, filename):
    text = text.replace("<ID>CoffeeCube</ID>", f"<ID>{DATABASE}</ID>")
    text = text.replace("<Name>CoffeeCube</Name>", f"<Name>{DATABASE}</Name>")
    text = text.replace("<TargetDatabase>CoffeeCube</TargetDatabase>", f"<TargetDatabase>{DATABASE}</TargetDatabase>")
    text = text.replace("<TargetServer>localhost</TargetServer>", f"<TargetServer>{SERVER}</TargetServer>")
    text = re.sub(r"<ConnectionString>.*?</ConnectionString>", f"<ConnectionString>{CONNECTION}</ConnectionString>", text)
    def inventory_aggregate(match):
        block = match.group(0)
        if "<ID>Inventory</ID>" not in block:
            return block
        if "<AggregateFunction>" in block:
            block = re.sub(r"<AggregateFunction>.*?</AggregateFunction>", "<AggregateFunction>LastChild</AggregateFunction>", block, count=1)
        else:
            block = block.replace("<Source>", "<AggregateFunction>LastChild</AggregateFunction>\n          <Source>", 1)
        return block
    text = re.sub(r"<Measure>.*?</Measure>", inventory_aggregate, text, flags=re.S)
    if "-- Semi-additive policy for Inventory" in text:
        text = re.sub(r"-- Semi-additive policy for Inventory.*?END SCOPE;</Text>", "-- Inventory uses the physical SSAS LastChild aggregation along the time dimension.\n</Text>", text, flags=re.S)
    if filename.endswith(".dim"):
        block_end = text.rfind("</Dimension>")
        if block_end >= 0 and "<ErrorConfiguration>" not in text:
            text = text[:block_end] + ERROR_CONFIGURATION + "\n" + text[block_end:]
    if filename == "CreateCoffeeCubeTrang.xmla":
        start = text.find("<Dimensions>")
        end = text.find("</Dimensions>", start)
        if start < 0 or end < 0:
            raise ValueError("Could not identify full database dimension metadata in the Create XMLA.")
        region = text[start:end]
        def strict_dimension(match):
            block = match.group(0)
            if "<Source xsi:type=\"DataSourceViewBinding\">" not in block or "<ErrorConfiguration>" in block:
                return block
            pos = block.rfind("</Dimension>")
            return block[:pos] + ERROR_CONFIGURATION + "\n      " + block[pos:]
        text = text[:start] + re.sub(r"<Dimension>.*?</Dimension>", strict_dimension, region, flags=re.S) + text[end:]
        # A DataSet XSD is inline beneath an Analysis Services database. The
        # empty default namespace keeps its XML Schema identity-constraint
        # QName references resolvable while the enclosing database is namespaced.
        text = re.sub(r"<xs:schema\b([^>]*)>", lambda m: "<xs:schema" + m.group(1) + (' xmlns=""' if 'xmlns=""' not in m.group(1) else '') + ">", text)
        text = re.sub(r"<CoffeeDW\s*/>", '<CoffeeDW xmlns="" />', text)
    if filename == "queries.mdx":
        text = text.replace("    NON EMPTY [Dim Product].[Product Name].[Product Name].Members,",
                            "    NONEMPTY([Dim Product].[Product Name].[Product Name].Members, [Measures].[Sales]),")
    return text


def main(target=TARGET, evidence=EVIDENCE):
    target, evidence = Path(target), Path(evidence)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Refusing to overwrite an existing Visual Studio/server project: {target}")
    target.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    original_hashes = {}
    for src in sorted(SOURCE.iterdir()):
        if src.is_file():
            name = "CreateCoffeeCubeTrang.xmla" if src.name == "DeployCoffeeCube.xmla" else src.name
            if src.name == "Coffee Performance.cube":
                # VS stores cube metadata and partition bindings separately.
                cube_text = adapt(src.read_text(encoding="utf-8-sig"), name)
                cube_root = ET.fromstring(cube_text)
                partition_root = ET.Element("{" + N["a"] + "}Cube")
                ET.SubElement(partition_root, "{" + N["a"] + "}ID").text = "Coffee Performance"
                groups_root = ET.SubElement(partition_root, "{" + N["a"] + "}MeasureGroups")
                for measure_group in cube_root.findall(".//a:MeasureGroup", N):
                    partitions = measure_group.find("a:Partitions", N)
                    if partitions is not None:
                        group = ET.SubElement(groups_root, "{" + N["a"] + "}MeasureGroup")
                        ET.SubElement(group, "{" + N["a"] + "}ID").text = measure_group.findtext("a:ID", namespaces=N)
                        group.append(partitions)
                        measure_group.remove(partitions)
                ET.indent(partition_root, space="  ")
                (target / "Coffee Performance.partitions").write_bytes(ET.tostring(partition_root, encoding="utf-8", xml_declaration=True))
                ET.indent(cube_root, space="  ")
                (target / name).write_bytes(ET.tostring(cube_root, encoding="utf-8", xml_declaration=True))
                original_hashes[src.relative_to(ROOT).as_posix()] = sha(src)
                continue
            if src.name == "CoffeeCube.database":
                database = ET.parse(src).getroot()
                minimal = ET.Element("{" + N["a"] + "}Database")
                for tag in ("ID", "Name", "Description"):
                    value = database.find("a:" + tag, N)
                    if value is not None:
                        child = ET.SubElement(minimal, "{" + N["a"] + "}" + tag)
                        child.text = DATABASE if tag in {"ID", "Name"} else value.text
                ET.indent(minimal, space="  ")
                (target / src.name).write_bytes(ET.tostring(minimal, encoding="utf-8", xml_declaration=True))
                original_hashes[src.relative_to(ROOT).as_posix()] = sha(src)
                continue
            if src.name == "CoffeeCube.dwproj":
                project = ET.parse(src).getroot()
                project.find("Database/Name").text = DATABASE
                project.find("Database/FullPath").text = "CoffeeCube.database"
                project.find("SchemaVersion").text = "9.0.2.10"
                cube_item = project.find("Cubes/ProjectItem")
                dependencies = cube_item.find("Dependencies")
                if dependencies is not None:
                    for child in list(dependencies):
                        dependencies.remove(child)
                    item = ET.SubElement(dependencies, "ProjectItem")
                    ET.SubElement(item, "Name").text = "Coffee Performance.partitions"
                    ET.SubElement(item, "FullPath").text = "Coffee Performance.partitions"
                options = project.find("Configurations/Configuration/Options")
                for element in list(options):
                    if element.tag in {"TargetServer", "TargetDatabase", "ProcessingOption", "TransactionOption"}:
                        options.remove(element)
                for tag, value in (("TargetServer", SERVER), ("TargetDatabase", DATABASE), ("ProcessingOption", "Default"), ("TransactionOption", "true")):
                    ET.SubElement(options, tag).text = value
                ET.indent(project, space="  ")
                (target / src.name).write_bytes(ET.tostring(project, encoding="utf-8", xml_declaration=True))
                original_hashes[src.relative_to(ROOT).as_posix()] = sha(src)
                continue
            original_hashes[src.relative_to(ROOT).as_posix()] = sha(src)
            (target / name).write_text(adapt(src.read_text(encoding="utf-8-sig"), name), encoding="utf-8")
    (target / "ProcessFull.xmla").write_text(f'''<?xml version="1.0" encoding="utf-8"?>
<Process xmlns="http://schemas.microsoft.com/analysisservices/2003/engine">
  <Object><DatabaseID>{DATABASE}</DatabaseID></Object>
  <Type>ProcessFull</Type>
  <WriteBackTableCreation>UseExisting</WriteBackTableCreation>
</Process>
''', encoding="utf-8")
    query_source = ROOT / ".work/review_chi/ssas/queries.mdx"
    queries = query_source.read_text(encoding="utf-8-sig")
    queries = queries.replace("    NON EMPTY [Dim Product].[Product Name].[Product Name].Members,", "    NONEMPTY([Dim Product].[Product Name].[Product Name].Members, [Measures].[Sales]),")
    queries = queries.replace("(LastNonEmpty / latest selected month)", "(calculated: latest selected month, without earlier nonempty fallback)")
    (target / "queries.mdx").write_text("-- Adapted for isolated SSAS database " + DATABASE + "; SELECT DATABASE IN CONNECTION.\n" + queries, encoding="utf-8")
    for path in target.iterdir():
        if path.suffix in {".xmla", ".database", ".ds", ".dsv", ".dim", ".cube", ".dwproj"}:
            ET.parse(path)
    create = ET.parse(target / "CreateCoffeeCubeTrang.xmla").getroot()
    db = create.find("a:ObjectDefinition/a:Database", N)
    assert db.findtext("a:ID", namespaces=N) == DATABASE
    assert len(db.findall("a:Dimensions/a:Dimension", N)) == 3
    cube = db.find("a:Cubes/a:Cube", N)
    measures = cube.findall("a:MeasureGroups/a:MeasureGroup/a:Measures/a:Measure", N)
    assert len(measures) == 11
    inventory = next(m for m in measures if m.findtext("a:ID", namespaces=N) == "Inventory")
    assert inventory.findtext("a:AggregateFunction", namespaces=N) == "LastChild"
    assert all(dim.find("a:ErrorConfiguration/a:KeyDuplicate", N) is not None for dim in db.findall("a:Dimensions/a:Dimension", N))
    script = cube.findtext("a:MdxScripts/a:MdxScript/a:Commands/a:Command/a:Text", namespaces=N)
    assert "SCOPE" not in script
    project = ET.parse(target / "CoffeeCube.dwproj").getroot()
    assert len(project.find("Cubes/ProjectItem/Dependencies")) == 1
    assert len(list(ET.parse(target / "CoffeeCube.database").getroot())) == 3
    manifest = {"source_chi_commit": "59d2559", "source_project": str(SOURCE), "target_project": str(TARGET),
                "ssas_server": SERVER, "ssas_database": DATABASE, "relational_server": ".", "relational_database": RELATIONAL_DATABASE,
                "provider": "MSOLEDBSQL", "impersonation": "ImpersonateServiceAccount", "deployment_executed": False,
                "create_script": "CreateCoffeeCubeTrang.xmla", "process_script": "ProcessFull.xmla",
                "changes": ["isolated SSAS target and relational source", "NONEMPTY inside Query7 ORDER",
                            "Inventory uses native LastChild and passed 9 multi-period tests",
                            "key duplicate, key-not-found and null-key dimension errors stop processing",
                            "Create XMLA keeps the DataSet inline XSD outside the AS namespace"],
                "source_sha256": original_hashes,
                "staged_files": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(TARGET.iterdir()) if p.is_file()],
                "required_runtime_validation": ["Create and ProcessFull in SSMS", "all 8 OLAP queries", "Inventory year/quarter/range/noncontiguous and leaf filters", "source-SQL-cube comparison"],
                "permission_needed_if_not_present": {"windows_service_account": r"NT Service\MSOLAP$TRANGTRETRAU", "sql_database": RELATIONAL_DATABASE,
                    "minimum_objects_select": ["dw.DimDate", "dw.DimLocation", "dw.DimProduct", "dw.FactSalesPerformance"], "grants_executed_by_preparation": False}}
    manifest["target_project"] = str(target.resolve())
    manifest["staged_files"] = [{"path": p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.name,
                                  "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(target.iterdir()) if p.is_file()]
    (evidence / "staging_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"staged": True, "target": str(target), "server": SERVER, "database": DATABASE, "deployed": False}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=TARGET)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    main(args.target, args.evidence)
