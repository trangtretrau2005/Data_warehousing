"""Make the staged component project loadable by SSDT; do not deploy it.

SSDT stores database properties, cube definitions and partitions separately.
The complete XMLA remains the deployment model and is left unchanged.
"""
from pathlib import Path
import copy
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "ssas/CoffeeCubeTrang"
NS = "http://schemas.microsoft.com/analysisservices/2003/engine"
N = {"a": NS}
ET.register_namespace("", NS)
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


def write(tree, path):
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main():
    database = ET.parse(P / "CoffeeCube.database")
    for child in list(database.getroot()):
        if child.tag.rsplit("}", 1)[-1] in {
            "DataSources", "DataSourceViews", "Dimensions", "Cubes", "Roles", "Assemblies"
        }:
            database.getroot().remove(child)
    write(database, P / "CoffeeCube.database")

    cube = ET.parse(P / "Coffee Performance.cube")
    partition_root = ET.Element(f"{{{NS}}}Cube")
    ET.SubElement(partition_root, f"{{{NS}}}ID").text = cube.findtext("a:ID", namespaces=N)
    groups = ET.SubElement(partition_root, f"{{{NS}}}MeasureGroups")
    for group in cube.findall("a:MeasureGroups/a:MeasureGroup", N):
        partitions = group.find("a:Partitions", N)
        if partitions is not None:
            target = ET.SubElement(groups, f"{{{NS}}}MeasureGroup")
            ET.SubElement(target, f"{{{NS}}}ID").text = group.findtext("a:ID", namespaces=N)
            target.append(copy.deepcopy(partitions))
            group.remove(partitions)
    if list(groups):
        write(ET.ElementTree(partition_root), P / "Coffee Performance.partitions")
    assert (P / "Coffee Performance.partitions").exists()
    write(cube, P / "Coffee Performance.cube")

    project = (P / "CoffeeCube.dwproj").read_text(encoding="utf-8-sig")
    project = re.sub(r"<ProductVersion>.*?</ProductVersion>", "<ProductVersion>16.0.21152.0</ProductVersion>", project)
    project = re.sub(r"<SchemaVersion>.*?</SchemaVersion>", "<SchemaVersion>9.0.2.10</SchemaVersion>", project)
    project = re.sub(r"\s*<Dependencies>.*?</Dependencies>", "", project, flags=re.S)
    project = project.replace(
        "<FullPath>Coffee Performance.cube</FullPath>",
        "<FullPath>Coffee Performance.cube</FullPath>\n"
        "      <Dependencies><ProjectItem><Name>Coffee Performance.partitions</Name>"
        "<FullPath>Coffee Performance.partitions</FullPath></ProjectItem></Dependencies>",
    )
    (P / "CoffeeCube.dwproj").write_text(project, encoding="utf-8")
    print("Prepared SSDT database properties + components + separate partitions; XMLA unchanged.")


if __name__ == "__main__":
    main()
