import json
import pathlib as pl
import shutil
import subprocess
import unittest


class TestVSCodeLabelHover(unittest.TestCase):
    def test_label_hover_helpers(self):
        node_path = shutil.which('node')  # type: ignore[name-defined]
        if not node_path:
            self.skipTest('node is not available to run label hover tests')

        helper_path = (
            pl.Path(__file__).resolve().parent.parent
            / 'src'
            / 'bespokeasm'
            / 'configgen'
            / 'vscode'
            / 'resources'
            / 'label_hover.js'
        )
        self.assertTrue(helper_path.is_file(), f'missing helper: {helper_path}')

        script = f"""
const helper = require('{helper_path.as_posix()}');
const constants = require('{(helper_path.parent / "constants_hover.js").as_posix()}');
const lines = ['start:', '  jmp start', '.local:', '  jmp .local', '_file:', '  jmp _file'];
const map = helper.buildLabelDefinitionMap(lines);
const start = helper.getLabelLocation(map, 'start');
const usage = helper.isDefinitionAtLocation(map, 'start', 0, start.character);
const usage2 = helper.isDefinitionAtLocation(map, 'start', 1, 6);
const local = helper.getLabelLocation(map, '.local');
const file = helper.getLabelLocation(map, '_file');
const includePath = helper.parseIncludePath('#include "file.asm"');
const includePath2 = helper.parseIncludePath('#include <other.asm>');
const includePath3 = helper.parseIncludePath('#include relative.asm');
const constLines = ['CONST = 10', '  mov CONST', 'VALUE EQU 5'];
const constMap = constants.buildConstantDefinitionMapFromFiles([
  {{uri: null, lines: constLines}}
]);
const constLoc = constants.getConstantLocation(constMap, 'CONST');
const constLoc2 = constants.getConstantLocation(constMap, 'VALUE');
const constUsage = constants.isDefinitionAtLocation(constMap, 'CONST', 0, constLoc.character, null);
const constUsage2 = constants.isDefinitionAtLocation(constMap, 'CONST', 1, 6, null);
const includeLabels = helper.buildLabelDefinitionMapFromFiles([
  {{uri: 'file:///main.asm', lines: ['main:', '  jmp ext']}},
  {{uri: 'file:///inc.asm', lines: ['ext:', '  nop']}}
]);
const includeLabelLoc = helper.getLabelLocation(includeLabels, 'ext');
console.log(JSON.stringify({{
  start,
  usage,
  usage2,
  local,
  file,
  includePath,
  includePath2,
  includePath3,
  constLoc,
  constLoc2,
  constUsage,
  constUsage2,
  includeLabelLoc
}}));
"""
        result = subprocess.run(
            [node_path, '-e', script],
            check=True,
            capture_output=True,
            text=True
        )
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload['start']['line'], 0)
        self.assertEqual(payload['start']['character'], 0)
        self.assertTrue(payload['usage'])
        self.assertFalse(payload['usage2'])
        self.assertEqual(payload['local']['line'], 2)
        self.assertEqual(payload['file']['line'], 4)
        self.assertEqual(payload['includePath'], 'file.asm')
        self.assertEqual(payload['includePath2'], 'other.asm')
        self.assertEqual(payload['includePath3'], 'relative.asm')
        self.assertEqual(payload['constLoc']['line'], 0)
        self.assertEqual(payload['constLoc2']['line'], 2)
        self.assertTrue(payload['constUsage'])
        self.assertFalse(payload['constUsage2'])
        self.assertEqual(payload['includeLabelLoc']['line'], 0)

    def test_vscode_collect_includes_transitive(self):
        node_path = shutil.which('node')  # type: ignore[name-defined]
        if not node_path:
            self.skipTest('node is not available to run label hover tests')

        helper_path = (
            pl.Path(__file__).resolve().parent.parent
            / 'src'
            / 'bespokeasm'
            / 'configgen'
            / 'vscode'
            / 'resources'
            / 'include_files.js'
        )
        self.assertTrue(helper_path.is_file(), f'missing helper: {helper_path}')

        script = f"""
const fs = require('fs');
const os = require('os');
const path = require('path');
const includeFiles = require('{helper_path.as_posix()}');
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bespokeasm-'));
const mainPath = path.join(tmpDir, 'main.asm');
const firstPath = path.join(tmpDir, 'first.asm');
const secondPath = path.join(tmpDir, 'second.asm');
const otherPath = path.join(tmpDir, 'other.asm');
fs.writeFileSync(mainPath, '#include \"first.asm\"\\n');
fs.writeFileSync(firstPath, '#include \"second.asm\"\\nfirst:\\n');
fs.writeFileSync(secondPath, 'second:\\n');
fs.writeFileSync(otherPath, 'other:\\n');
const lines = fs.readFileSync(mainPath, 'utf8').split(/\\r?\\n/);
const entries = includeFiles.collectIncludedFiles(lines, tmpDir);
console.log(JSON.stringify({{
  paths: entries.map((entry) => path.basename(entry.path))
}}));
"""
        result = subprocess.run(
            [node_path, '-e', script],
            check=True,
            capture_output=True,
            text=True
        )
        payload = json.loads(result.stdout.strip())
        self.assertIn('first.asm', payload['paths'])
        self.assertIn('second.asm', payload['paths'])
        self.assertNotIn('other.asm', payload['paths'])
        self.assertEqual(len(payload['paths']), 2)
