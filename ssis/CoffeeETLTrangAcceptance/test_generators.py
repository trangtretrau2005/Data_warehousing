"""Small future-codegen tests: never builds/executes a package or writes SQL."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent


class GeneratorTests(unittest.TestCase):
    def test_solution_keeps_real_ssdt_type_and_development_default(self):
        spec=importlib.util.spec_from_file_location('acceptance_finish',HERE/'Finish-Project.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        root=ET.fromstring(module.solution_xml())
        self.assertEqual(root.find('Configurations/BuildType').attrib['Name'],'Development')
        self.assertEqual(root.find('Configurations/Platform').attrib['Name'],'Default')
        self.assertEqual(root.find('Project').attrib['Type'],'c9674dcb-5085-4a16-b785-4c70dd1589bd')
        self.assertEqual(root.find('Project/Platform').attrib['Project'],'?')

    def test_every_aggregate_guard_uses_not_exists_having(self):
        source=(HERE/'BuildAcceptance.cs').read_text(encoding='utf-8')
        lines=[line for line in source.splitlines() if 'HAVING SUM(' in line]
        self.assertEqual(len(lines),4)
        self.assertTrue(all('IF NOT EXISTS(SELECT 1' in line for line in lines))
        self.assertNotIn('IF (SELECT SUM(',source)


if __name__=='__main__':unittest.main()
