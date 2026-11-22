"""Check the SDK-generated package's real metadata contract before native runs."""
from pathlib import Path
import copy
import csv
import xml.etree.ElementTree as ET
import zipfile
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "ssis/CoffeeETLTrang"
DTS = {"d": "www.microsoft.com/SqlServer/Dts"}


def package():
    return ET.parse(PROJECT / "LoadCoffeeTrang.dtsx").getroot()


def test_all_source_columns_reach_native_destination_without_type_coercion():
    with (ROOT / "data/raw/Coffee.csv").open(encoding="utf-8-sig", newline="") as stream:
        expected = next(csv.reader(stream))
    components = package().findall(".//component")
    source = next(c for c in components if c.attrib["componentClassID"] == "Microsoft.FlatFileSource")
    destination = next(c for c in components if c.attrib["componentClassID"] == "Microsoft.OLEDBDestination")
    output = source.find("outputs/output[1]/outputColumns")
    assert [c.attrib["name"] for c in output] == expected
    assert all(c.attrib["dataType"] == "wstr" for c in output)
    inputs = destination.findall("inputs/input/inputColumns/inputColumn")
    external = destination.findall("inputs/input/externalMetadataColumns/externalMetadataColumn")
    assert {c.attrib["cachedName"] for c in inputs} == set(expected) | {"BatchID"}
    assert {c.attrib["name"] for c in external} == set(expected) | {"BatchID"}
    assert len(inputs) == len(external) == 21
    assert all(c.attrib.get("externalMetadataColumnId") for c in inputs)
    assert len(package().findall(".//path")) == 2


def test_control_flow_preserves_register_land_validate_and_transactional_load_order():
    root = package()
    tasks = root.find("d:Executables", DTS)
    assert len(tasks) == 4
    names = ["EST_01_RegisterBatch", "DFT_02_CSV_RawLanding", "EST_03_ValidateAndStage", "EST_04_TransactionalStarLoad"]
    assert {t.attrib["{www.microsoft.com/SqlServer/Dts}ObjectName"] for t in tasks} == set(names)
    constraints = root.find("d:PrecedenceConstraints", DTS)
    edges = {(c.attrib["{www.microsoft.com/SqlServer/Dts}From"].split("\\")[-1],
              c.attrib["{www.microsoft.com/SqlServer/Dts}To"].split("\\")[-1]) for c in constraints}
    assert edges == set(zip(names, names[1:]))
    assert root.find("d:EventHandlers/d:EventHandler", DTS) is not None
    connections = root.find("d:ConnectionManagers", DTS)
    expressions = [e.text for cm in connections for e in cm.findall("d:PropertyExpression", DTS)]
    assert any("User::SourceFilePath" in e for e in expressions)
    assert any("User::DatabaseName" in e and "User::ServerName" in e for e in expressions)


def test_project_descriptor_uses_native_packages_and_explicit_target():
    project_root = ET.parse(PROJECT / "CoffeeETLTrang.dtproj").getroot()
    manifest = project_root.find("DeploymentModelSpecificContent/Manifest")
    assert manifest is not None and len(manifest) == 1
    root_namespace = "{www.microsoft.com/SqlServer/SSIS}"
    project_name = manifest.find(f"{root_namespace}Project/{root_namespace}Properties/{root_namespace}Property[@{root_namespace}Name='Name']")
    assert project_name is not None and project_name.text == "CoffeeETLTrang"
    children = [child.tag for child in list(project_root)]
    assert children.index("DataSources") < children.index("DataSourceViews") < children.index("DeploymentModelSpecificContent")
    assert (PROJECT / "CoffeeETLTrang.database").exists()
    project_id = manifest.find(f"{root_namespace}Project/{root_namespace}Properties/{root_namespace}Property[@{root_namespace}Name='ID']")
    assert project_id is not None
    UUID(project_id.text.strip("{}"))
    # SSDT VS18 save keeps native package references/ID in Manifest and can
    # omit redundant outer ProjectGuid/Packages generated before Designer use.
    if project_root.findtext("ProjectGuid"):
        UUID(project_root.findtext("ProjectGuid").strip("{}"))
    assert project_root.find(".//TargetServerVersion").text == "SQLServer2022"
    expected_packages = {"LoadCoffeeTrang.dtsx", "SCD_TN04_Trang.dtsx"}
    assert {p.attrib[f"{root_namespace}Name"] for p in manifest.findall(f"{root_namespace}Project/{root_namespace}Packages/{root_namespace}Package")} == expected_packages
    assert all((PROJECT / name).exists() for name in expected_packages)
    outer_packages = project_root.findall("Packages/Package")
    if outer_packages:
        assert {p.findtext("Name") for p in outer_packages} == expected_packages


def test_sdk_project_archive_contains_same_package_and_explicit_target():
    archive_path = PROJECT / "CoffeeETLTrang.ispac"
    if not archive_path.exists():
        pytest.skip("Optional SDK-generated .ispac not built locally; source descriptor is checked separately")
    project_root = ET.parse(PROJECT / "CoffeeETLTrang.dtproj").getroot()
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.read("LoadCoffeeTrang.dtsx") == (PROJECT / "LoadCoffeeTrang.dtsx").read_bytes()
        assert archive.read("SCD_TN04_Trang.dtsx") == (PROJECT / "SCD_TN04_Trang.dtsx").read_bytes()
        assert "@Project.manifest" in archive.namelist()
        assert "Project.params" in archive.namelist()
        ispac_manifest = ET.fromstring(archive.read("@Project.manifest"))
    manifest = project_root.find("DeploymentModelSpecificContent/Manifest")
    assert manifest is not None and len(manifest) == 1
    root_namespace = "{www.microsoft.com/SqlServer/SSIS}"
    target_path = f"{root_namespace}Properties/{root_namespace}Property[@{root_namespace}Name='TargetServerVersion']"
    assert ispac_manifest.find(target_path).text == "160"
    designer_target = manifest[0].find(target_path)
    if designer_target is not None:
        assert designer_target.text == "160"
    def canonical(node):
        node = copy.deepcopy(node)
        # SSDT VS18 save omits this redundant manifest property, while the
        # descriptor Configuration still explicitly targets SQLServer2022.
        target = node.find(target_path)
        if target is not None:
            node.find(f"{root_namespace}Properties").remove(target)
        for element in node.iter():
            if element.text is not None and not element.text.strip(): element.text=None
            if element.tail is not None and not element.tail.strip(): element.tail=None
        return ET.tostring(node, encoding="unicode")
    assert canonical(manifest[0]) == canonical(ispac_manifest)
    assert [p.attrib[f"{root_namespace}Name"] for p in ispac_manifest.findall(f".//{root_namespace}PackageMetaData")] == ["LoadCoffeeTrang.dtsx","SCD_TN04_Trang.dtsx"]


def test_scd_native_package_is_separate_synthetic_execute_sql_entrypoint():
    root = ET.parse(PROJECT / "SCD_TN04_Trang.dtsx").getroot()
    assert root.attrib["{www.microsoft.com/SqlServer/Dts}ObjectName"] == "SCD_TN04_Trang"
    sql = root.find(".//{www.microsoft.com/sqlserver/dts/tasks/sqltask}SqlTaskData")
    assert sql is not None and "audit.SCDNativeEvidence" in sql.attrib["{www.microsoft.com/sqlserver/dts/tasks/sqltask}SqlStatementSource"]
    statement = sql.attrib["{www.microsoft.com/sqlserver/dts/tasks/sqltask}SqlStatementSource"]
    assert "THROW 50213" in statement and "audit.LoadBatch" not in statement
    assert len(root.findall("{www.microsoft.com/SqlServer/Dts}Executables/{www.microsoft.com/SqlServer/Dts}Executable")) == 1
