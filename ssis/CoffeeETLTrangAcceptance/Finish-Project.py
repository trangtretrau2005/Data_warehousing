"""Extract native SDK archive, build SSDT descriptor and static proof. No execution."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NS='www.microsoft.com/SqlServer/SSIS'
ET.register_namespace('SSIS',NS)


def solution_xml():
    """Match the working SSDT project type/configuration saved by VS18."""
    return '''<Solution>
  <Configurations>
    <BuildType Name="Development" />
    <Platform Name="Default" />
  </Configurations>
  <Project Path="CoffeeETLTrangAcceptance.dtproj" Type="c9674dcb-5085-4a16-b785-4c70dd1589bd">
    <Platform Project="?" />
  </Project>
</Solution>
'''


def main():
    with zipfile.ZipFile(HERE/'CoffeeETLTrangAcceptance.ispac') as archive:
        for name in archive.namelist():
            if name.endswith('.dtsx') or name=='Project.params': (HERE/name).write_bytes(archive.read(name))
        manifest=ET.fromstring(archive.read('@Project.manifest'))
    project=ET.Element('Project',{'xmlns:xsd':'http://www.w3.org/2001/XMLSchema','xmlns:xsi':'http://www.w3.org/2001/XMLSchema-instance'})
    for tag,text in [('DeploymentModel','Project'),('ProductVersion','16.0.1000.6'),('SchemaVersion','9.0.1.0'),('ProjectGuid','{9DF66170-AB4F-409C-B47B-65F31F01E54A}')]:
        ET.SubElement(project,tag).text=text
    db=ET.SubElement(project,'Database')
    for tag in ('Name','FullPath'):ET.SubElement(db,tag).text='CoffeeETLTrangAcceptance.database'
    ET.SubElement(project,'DataSources');ET.SubElement(project,'DataSourceViews')
    ET.SubElement(ET.SubElement(project,'DeploymentModelSpecificContent'),'Manifest').append(manifest)
    packages=ET.SubElement(project,'Packages')
    names=['00_AcceptAll.dtsx']+sorted(p.name for p in HERE.glob('0[1-8]_*.dtsx'))
    for name in names:
        item=ET.SubElement(packages,'Package')
        for tag in ('Name','FullPath'):ET.SubElement(item,tag).text=name
    config=ET.SubElement(ET.SubElement(project,'Configurations'),'Configuration')
    ET.SubElement(config,'Name').text='Development'
    options=ET.SubElement(config,'Options')
    ET.SubElement(options,'OutputPath').text='bin'
    ET.SubElement(options,'TargetServerVersion').text='SQLServer2022'
    ET.indent(project)
    ET.ElementTree(project).write(HERE/'CoffeeETLTrangAcceptance.dtproj',encoding='utf-8',xml_declaration=True)
    database=ET.parse(HERE.parent/'CoffeeETLTrang/CoffeeETLTrang.database')
    dbroot=database.getroot(); dns={'a':'http://schemas.microsoft.com/analysisservices/2003/engine'}
    for tag in ('ID','Name'):dbroot.find(f'a:{tag}',dns).text='CoffeeETLTrangAcceptance'
    for key in list(dbroot.attrib):
        if key.endswith('design-time-name'):dbroot.attrib[key]=str(uuid4())
    database.write(HERE/'CoffeeETLTrangAcceptance.database',encoding='utf-8',xml_declaration=True)
    (HERE/'CoffeeETLTrangAcceptance.slnx').write_text(solution_xml(),encoding='utf-8')
    prepared=json.loads((HERE/'acceptance_manifest.json').read_text(encoding='utf-8'))
    proof={'status':'PREPARED_NOT_EXECUTED','suite_id':prepared['suite_id'],'packages':[],'assertions':[]}
    package_ids=set()
    for name in names:
        p=HERE/name;r=ET.parse(p).getroot();identity=r.attrib['{www.microsoft.com/SqlServer/Dts}DTSID'];package_ids.add(identity)
        proof['packages'].append({'name':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'DTSID':identity})
    assert len(names)==9 and len(package_ids)==9
    parent=ET.parse(HERE/'00_AcceptAll.dtsx').getroot()
    tasks=parent.find('{www.microsoft.com/SqlServer/Dts}Executables')
    execute=[t for t in tasks if t.attrib.get('{www.microsoft.com/SqlServer/Dts}CreationName')=='Microsoft.ExecutePackageTask']
    assert len(execute)==8,(len(execute),[t.attrib for t in tasks])
    assert len(tasks)==18
    assert len(parent.find('{www.microsoft.com/SqlServer/Dts}PrecedenceConstraints'))==17
    batch_ids=set()
    for case in prepared['cases']:
        r=ET.parse(HERE/case['package']).getroot()
        variables={v.attrib['{www.microsoft.com/SqlServer/Dts}ObjectName']:v.find('{www.microsoft.com/SqlServer/Dts}VariableValue').text for v in r.findall('{www.microsoft.com/SqlServer/Dts}Variables/{www.microsoft.com/SqlServer/Dts}Variable')}
        assert variables['BatchID']==case['batch_id'];batch_ids.add(variables['BatchID'])
        assert variables['SourceChecksum']==case['source_sha256']
        assert variables['SourceFilePath']==case['source_path']
        assert int(variables['SourceCount'])==case['source_count']
        assert variables['DatabaseName']==prepared['database']
        assert hashlib.sha256(Path(case['source_path']).read_bytes()).hexdigest()==case['source_sha256']
        assert len(r.findall('.//component'))==3
    assert len(batch_ids)==8
    proof['assertions']=['9 unique package IDs','8 unique fresh BatchIDs','8 fixture SHA/count/path bindings verified','8 ExecutePackageTask project references','18 parent tasks /17 success links','Each child retains3native dataflowcomponents']
    (HERE/'build_verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    evidence=ROOT/'results/native_build_20261120/ssis/acceptance_prepared'/prepared['suite_id']
    evidence.mkdir(parents=True,exist_ok=True)
    for name in ('acceptance_manifest.json','build_verification.json','CoffeeETLTrangAcceptance.ispac'):
        (evidence/name).write_bytes((HERE/name).read_bytes())
    print(f'Ready: {len(names)} native packages; 8 project-reference tasks; 18-task parent. No runtime/database proof claimed.')


if __name__=='__main__':main()
