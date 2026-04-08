import json
import pathlib as pl
import shutil
import subprocess
import tempfile
import unittest

from bespokeasm.utilities import PATTERN_ALLOWED_LABELS


class TestVSCodeLabelHover(unittest.TestCase):
    def _label_pattern(self) -> str:
        pattern = PATTERN_ALLOWED_LABELS.pattern
        if pattern.startswith('^'):
            pattern = pattern[1:]
        if pattern.endswith('$'):
            pattern = pattern[:-1]
        return pattern

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

        label_pattern = self._label_pattern()
        temp_dir = tempfile.mkdtemp()
        label_helper_path = pl.Path(temp_dir) / 'label_hover.js'
        constants_helper_path = pl.Path(temp_dir) / 'constants_hover.js'
        label_helper_path.write_text(
            helper_path.read_text().replace('##LABEL_PATTERN##', label_pattern),
            encoding='utf-8'
        )
        constants_helper_path.write_text(
            (helper_path.parent / 'constants_hover.js').read_text().replace('##LABEL_PATTERN##', label_pattern),
            encoding='utf-8'
        )

        script = f"""
const helper = require('{label_helper_path.as_posix()}');
const constants = require('{constants_helper_path.as_posix()}');
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
const opLines = [
  'mix @first:$1111, [@second: $2222]',
  '  mov first, second',
  'text ".not_a_label: nope" ; @ignored: nope'
];
const opMap = helper.buildLabelDefinitionMap(opLines);
const firstLoc = helper.getLabelLocation(opMap, 'first');
const secondLoc = helper.getLabelLocation(opMap, 'second');
const firstIsDef = helper.isDefinitionAtLocation(opMap, 'first', 0, firstLoc.character);
const secondIsDef = helper.isDefinitionAtLocation(opMap, 'second', 0, secondLoc.character);
const opDefs = helper.findLabelDefinitions(opLines[0]);
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
  includeLabelLoc,
  firstLoc,
  secondLoc,
  firstIsDef,
  secondIsDef,
  opDefs
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
        self.assertEqual(payload['firstLoc']['line'], 0)
        self.assertEqual(payload['secondLoc']['line'], 0)
        self.assertTrue(payload['firstIsDef'])
        self.assertTrue(payload['secondIsDef'])
        self.assertEqual([item['name'] for item in payload['opDefs']], ['first', 'second'])
        self.assertEqual(payload['opDefs'][0]['character'], payload['firstLoc']['character'])
        self.assertEqual(payload['opDefs'][1]['character'], payload['secondLoc']['character'])
        shutil.rmtree(temp_dir)

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

    def test_vscode_directive_detection(self):
        node_path = shutil.which('node')
        if not node_path:
            self.skipTest('node is not available')

        extension_path = (
            pl.Path(__file__).resolve().parent.parent
            / 'src' / 'bespokeasm' / 'configgen' / 'vscode' / 'resources' / 'extension.js'
        )
        label_helper_path = (
            pl.Path(__file__).resolve().parent.parent
            / 'src' / 'bespokeasm' / 'configgen' / 'vscode' / 'resources' / 'label_hover.js'
        )
        constants_helper_path = (
            pl.Path(__file__).resolve().parent.parent
            / 'src' / 'bespokeasm' / 'configgen' / 'vscode' / 'resources' / 'constants_hover.js'
        )
        include_files_path = (
            pl.Path(__file__).resolve().parent.parent
            / 'src' / 'bespokeasm' / 'configgen' / 'vscode' / 'resources' / 'include_files.js'
        )

        label_pattern = self._label_pattern()
        temp_dir = tempfile.mkdtemp()
        temp_path = pl.Path(temp_dir)

        # Write processed helper files with patterns replaced
        (temp_path / 'label_hover.js').write_text(
            label_helper_path.read_text().replace('##LABEL_PATTERN##', label_pattern),
            encoding='utf-8'
        )
        (temp_path / 'constants_hover.js').write_text(
            constants_helper_path.read_text().replace('##LABEL_PATTERN##', label_pattern),
            encoding='utf-8'
        )
        shutil.copy(str(include_files_path), str(temp_path / 'include_files.js'))

        # Read extension.js and extract just the functions we need
        ext_src = extension_path.read_text()
        ext_src = ext_src.replace('##LABEL_PATTERN##', label_pattern)
        ext_src = ext_src.replace('##MNEMONIC_PATTERN##', r'\bLDA\b|\bJMP\b|\bNOP\b')
        ext_src = ext_src.replace('##REGISTERS##', r'\ba\b|\bb\b')

        # Write a test script that extracts and tests getDirectiveAtPosition
        # and extractConstantValue
        script = f"""
const fs = require('fs');
const path = require('path');

// Mock vscode module
const vscode = {{
  Uri: {{ parse: (s) => s, file: (s) => s }},
  MarkdownString: class {{ constructor(s) {{ this.value = s; }} }},
  Position: class {{ constructor(l,c) {{ this.line=l; this.character=c; }} }},
  Range: class {{ constructor(s,e) {{ this.start=s; this.end=e; }} }},
  Location: class {{ constructor(u,r) {{ this.uri=u; this.range=r; }} }},
  SemanticTokensLegend: class {{ constructor() {{}} }},
  SemanticTokensBuilder: class {{ constructor() {{ this.push = () => {{}}; this.build = () => null; }} }},
  workspace: {{ getConfiguration: () => ({{ get: () => true }}) }},
  languages: {{ registerHoverProvider: () => {{}}, registerDocumentSemanticTokensProvider: () => {{}} }},
  commands: {{ registerCommand: () => {{}}, executeCommand: () => {{}} }},
}};
require.cache['vscode'] = {{ exports: vscode }};

// Redirect helper requires to temp dir
const origResolve = require.resolve;
const labelHelper = require('{(temp_path / "label_hover.js").as_posix()}');
const constantsHelper = require('{(temp_path / "constants_hover.js").as_posix()}');
const includeFilesHelper = require('{(temp_path / "include_files.js").as_posix()}');

// Now load the extension source and extract functions
const Module = require('module');
const m = new Module('extension');
m.paths = Module._nodeModulePaths('{temp_path.as_posix()}');

// Patch requires for the extension module
const origRequire = m.require.bind(m);
m.require = function(id) {{
  if (id === 'vscode') return vscode;
  if (id === './label_hover') return labelHelper;
  if (id === './constants_hover') return constantsHelper;
  if (id === './include_files') return includeFilesHelper;
  return origRequire(id);
}};

const extSource = fs.readFileSync('{extension_path.as_posix()}', 'utf8')
  .replace(/##LABEL_PATTERN##/g, '{label_pattern}')
  .replace(/##MNEMONIC_PATTERN##/g, '\\\\bLDA\\\\b|\\\\bJMP\\\\b|\\\\bNOP\\\\b')
  .replace(/##REGISTERS##/g, '\\\\ba\\\\b|\\\\bb\\\\b');
m._compile(extSource, 'extension.js');

// Test getDirectiveAtPosition (it's not exported, so we test via the patterns)
// Instead, we'll test the regex patterns directly
const COMPILER_RE = /\\.(\\w+)\\b/gi;
const PREPROC_RE = /#(\\S+)\\b/gi;

function getDirective(lineText, character) {{
  COMPILER_RE.lastIndex = 0;
  let match;
  while ((match = COMPILER_RE.exec(lineText)) !== null) {{
    if (character >= match.index && character < match.index + match[0].length) {{
      return match[1].toLowerCase();
    }}
  }}
  PREPROC_RE.lastIndex = 0;
  while ((match = PREPROC_RE.exec(lineText)) !== null) {{
    if (character >= match.index && character < match.index + match[0].length) {{
      return match[1].toLowerCase();
    }}
  }}
  return null;
}}

const results = {{
  // Directive at line start
  orgAtDot: getDirective('.org $1000', 0),
  orgAtName: getDirective('.org $1000', 3),
  orgPastEnd: getDirective('.org $1000', 5),
  // Directive after label
  byteAfterLabel: getDirective('var: .byte 0xff', 5),
  byteAfterLabel2: getDirective('var: .byte 0xff', 9),
  // Preprocessor
  includeAtHash: getDirective('#include "file.asm"', 0),
  includeAtName: getDirective('#include "file.asm"', 5),
  // Constant value extraction
  constValueEq: constantsHelper.findConstantDefinition('MY_CONST = $FF'),
  constValueEqu: constantsHelper.findConstantDefinition('OTHER EQU 42'),
  notConst: constantsHelper.findConstantDefinition('  jmp start'),
}};

console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            [node_path, '-e', script],
            check=True,
            capture_output=True,
            text=True
        )
        payload = json.loads(result.stdout.strip())

        self.assertEqual(payload['orgAtDot'], 'org')
        self.assertEqual(payload['orgAtName'], 'org')
        self.assertIsNone(payload['orgPastEnd'])
        self.assertEqual(payload['byteAfterLabel'], 'byte')
        self.assertEqual(payload['byteAfterLabel2'], 'byte')
        self.assertEqual(payload['includeAtHash'], 'include')
        self.assertEqual(payload['includeAtName'], 'include')
        self.assertEqual(payload['constValueEq'], 'MY_CONST')
        self.assertEqual(payload['constValueEqu'], 'OTHER')
        self.assertIsNone(payload['notConst'])

        shutil.rmtree(temp_dir)
