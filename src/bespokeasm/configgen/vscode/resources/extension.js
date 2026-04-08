const fs = require('fs');
const path = require('path');
const vscode = require('vscode');

const labelHover = require('./label_hover');
const constantsHover = require('./constants_hover');
const includeFiles = require('./include_files');
const tokenTypes = new Map([['label', 0], ['constant', 1]]);
const tokenModifiers = new Map([['definition', 0]]);
const semanticLegend = new vscode.SemanticTokensLegend(
  Array.from(tokenTypes.keys()),
  Array.from(tokenModifiers.keys())
);
const OPEN_LABEL_COMMAND = 'bespokeasm.openLabelDefinition';
const OPEN_CONSTANT_COMMAND = 'bespokeasm.openConstantDefinition';
const DEFAULT_HOVER_SETTINGS = {
  mnemonics: true,
  labels: true,
  constants: true
};

function loadInstructionDocs(context) {
  const docsPath = context.asAbsolutePath('instruction-docs.json');
  try {
    const raw = fs.readFileSync(docsPath, 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    console.error('Failed to load instruction docs:', error);
    return null;
  }
}

function getLanguageId(context) {
  const packageJson = context.extension?.packageJSON;
  return packageJson?.contributes?.languages?.[0]?.id || null;
}

function buildLabelDefinitionMap(document) {
  const lines = [];
  for (let i = 0; i < document.lineCount; i += 1) {
    lines.push(document.lineAt(i).text);
  }

  const entries = [{ uri: document.uri, lines }];
  const baseDir = document.uri.fsPath ? path.dirname(document.uri.fsPath) : null;
  if (baseDir) {
    const includes = includeFiles.collectIncludedFiles(lines, baseDir).map((entry) => ({
      uri: vscode.Uri.file(entry.path),
      lines: entry.lines
    }));
    entries.push(...includes);
  }

  return labelHover.buildLabelDefinitionMapFromFiles(entries);
}

function buildConstantDefinitionMap(document) {
  const lines = [];
  for (let i = 0; i < document.lineCount; i += 1) {
    lines.push(document.lineAt(i).text);
  }

  const entries = [{ uri: document.uri, lines }];
  const baseDir = document.uri.fsPath ? path.dirname(document.uri.fsPath) : null;
  if (baseDir) {
    const includes = includeFiles.collectIncludedFiles(lines, baseDir).map((entry) => ({
      uri: vscode.Uri.file(entry.path),
      lines: entry.lines
    }));
    entries.push(...includes);
  }

  return constantsHover.buildConstantDefinitionMapFromFiles(entries);
}

function buildDefinitionHover(label, location, uri) {
  const position = new vscode.Position(location.line, location.character);
  const targetUri = location.uri || uri;
  const commandArgs = {
    uri: targetUri.toString(),
    line: location.line,
    character: location.character
  };
  const commandUri = vscode.Uri.parse(
    `command:${OPEN_LABEL_COMMAND}?${encodeURIComponent(JSON.stringify(commandArgs))}`
  );
  const filename = targetUri?.fsPath ? path.basename(targetUri.fsPath) : 'file';
  const locationText = targetUri === uri
    ? `Defined at line ${location.line + 1}.`
    : `Defined at line ${location.line + 1} in ${filename}.`;
  const markdown = new vscode.MarkdownString(
    `\`${label}\`: ${locationText} [Go to definition](${commandUri})`
  );
  markdown.isTrusted = { enabledCommands: [OPEN_LABEL_COMMAND] };
  return markdown;
}

function buildConstantHover(constant, location, uri) {
  const position = new vscode.Position(location.line, location.character);
  const targetUri = location.uri || uri;
  const commandArgs = {
    uri: targetUri.toString(),
    line: location.line,
    character: location.character
  };
  const commandUri = vscode.Uri.parse(
    `command:${OPEN_CONSTANT_COMMAND}?${encodeURIComponent(JSON.stringify(commandArgs))}`
  );
  const filename = targetUri?.fsPath ? path.basename(targetUri.fsPath) : 'file';
  const locationText = targetUri === uri
    ? `Defined at line ${location.line + 1}.`
    : `Defined at line ${location.line + 1} in ${filename}.`;
  const markdown = new vscode.MarkdownString(
    `\`${constant}\`: ${locationText} [Go to definition](${commandUri})`
  );
  markdown.isTrusted = { enabledCommands: [OPEN_CONSTANT_COMMAND] };
  return markdown;
}

function getSemanticSearchRanges(text) {
  const ranges = [];
  let segmentStart = 0;
  let inQuote = null;
  let escaped = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuote) {
      if (escaped) {
        escaped = false;
      } else if (ch === '\\') {
        escaped = true;
      } else if (ch === inQuote) {
        inQuote = null;
        segmentStart = i + 1;
      }
      continue;
    }

    if (ch === '"' || ch === '\'') {
      if (segmentStart < i) {
        ranges.push({ start: segmentStart, end: i });
      }
      inQuote = ch;
      continue;
    }

    if (ch === ';') {
      if (segmentStart < i) {
        ranges.push({ start: segmentStart, end: i });
      }
      return ranges;
    }
  }

  if (!inQuote && segmentStart < text.length) {
    ranges.push({ start: segmentStart, end: text.length });
  }
  return ranges;
}

function isOffsetInCodeRegion(text, offset) {
  if (offset < 0 || offset >= text.length) {
    return false;
  }
  const ranges = getSemanticSearchRanges(text);
  for (const range of ranges) {
    if (offset >= range.start && offset < range.end) {
      return true;
    }
  }
  return false;
}

function buildSemanticTokens(document) {
  const labelMap = buildLabelDefinitionMap(document);
  const labels = new Set(labelMap.keys());
  const constantMap = buildConstantDefinitionMap(document);
  const constants = new Set(constantMap.keys());
  const lines = [];

  for (let i = 0; i < document.lineCount; i += 1) {
    const text = document.lineAt(i).text;
    lines.push(text);
  }

  const builder = new vscode.SemanticTokensBuilder(semanticLegend);
  const labelType = tokenTypes.get('label');
  const constantType = tokenTypes.get('constant');
  const definitionModifier = 1 << tokenModifiers.get('definition');

  for (let line = 0; line < lines.length; line += 1) {
    const text = lines[line];
    const labelDefinitions = labelHover.findLabelDefinitions(text);
    const labelDefinitionOffsets = new Set();
    for (const def of labelDefinitions) {
      builder.push(line, def.character, def.name.length, labelType, definitionModifier);
      labelDefinitionOffsets.add(`${def.name}@${def.character}`);
    }
    const constDef = constantsHover.findConstantDefinition(text);
    let constDefStart = -1;
    if (constDef) {
      constDefStart = text.indexOf(constDef);
      builder.push(line, constDefStart, constDef.length, constantType, definitionModifier);
    }

    const searchRanges = getSemanticSearchRanges(text);
    for (const range of searchRanges) {
      const segment = text.slice(range.start, range.end);
      const regex = /(##LABEL_PATTERN##)/g;
      let match;
      while ((match = regex.exec(segment)) !== null) {
        const word = match[1];
        const offset = range.start + match.index;
        if (constants.has(word)) {
          if (!(constDef && word === constDef && offset === constDefStart)) {
            builder.push(line, offset, word.length, constantType, 0);
            continue;
          }
        }
        if (labels.has(word)) {
          if (labelDefinitionOffsets.has(`${word}@${offset}`)) {
            continue;
          }
          builder.push(line, offset, word.length, labelType, 0);
        }
      }
    }
  }

  return builder.build();
}

function getHoverSettings(document, languageId) {
  const config = vscode.workspace.getConfiguration(`bespokeasm.${languageId}`, document.uri);
  return {
    mnemonics: config.get('hover.mnemonics', DEFAULT_HOVER_SETTINGS.mnemonics),
    labels: config.get('hover.labels', DEFAULT_HOVER_SETTINGS.labels),
    constants: config.get('hover.constants', DEFAULT_HOVER_SETTINGS.constants)
  };
}

function buildMarkdownHover(doc) {
  const markdown = new vscode.MarkdownString(doc);
  markdown.isTrusted = false;
  return markdown;
}

const COMPILER_DIRECTIVE_RE = /\.(\w+)\b/gi;
const PREPROCESSOR_DIRECTIVE_RE = /#(\S+)\b/gi;
const REGISTER_RE = /(?:##REGISTERS##)/gi;
const CONSTANT_VALUE_RE = /^\s*##LABEL_PATTERN##\s*(?:=|\bEQU\b)\s*(.+?)(?:\s*;.*)?$/;

function getDirectiveAtPosition(lineText, character) {
  if (!isOffsetInCodeRegion(lineText, character)) {
    return null;
  }
  COMPILER_DIRECTIVE_RE.lastIndex = 0;
  let match;
  while ((match = COMPILER_DIRECTIVE_RE.exec(lineText)) !== null) {
    const dirStart = match.index;  // include the dot
    const dirEnd = match.index + match[0].length;
    if (character >= dirStart && character < dirEnd) {
      return match[1].toLowerCase();
    }
  }
  PREPROCESSOR_DIRECTIVE_RE.lastIndex = 0;
  while ((match = PREPROCESSOR_DIRECTIVE_RE.exec(lineText)) !== null) {
    const dirStart = match.index;  // include the hash
    const dirEnd = match.index + match[0].length;
    if (character >= dirStart && character < dirEnd) {
      return match[1].toLowerCase();
    }
  }
  return null;
}

function getRegisterAtPosition(lineText, character) {
  let match;
  REGISTER_RE.lastIndex = 0;
  while ((match = REGISTER_RE.exec(lineText)) !== null) {
    if (character >= match.index && character < match.index + match[0].length) {
      return match[0].toLowerCase();
    }
  }
  return null;
}

function extractConstantValue(document, token, constantMap) {
  const location = constantsHover.getConstantLocation(constantMap, token);
  if (!location) {
    return null;
  }
  const targetUri = location.uri || document.uri;
  try {
    let lineText;
    if (targetUri.toString() === document.uri.toString()) {
      lineText = document.lineAt(location.line).text;
    } else {
      const content = fs.readFileSync(targetUri.fsPath, 'utf8');
      const lines = content.split(/\r?\n/);
      if (location.line < lines.length) {
        lineText = lines[location.line];
      }
    }
    if (lineText) {
      const match = CONSTANT_VALUE_RE.exec(lineText);
      if (match) {
        return match[1].trim();
      }
    }
  } catch (_) {
    // ignore read errors
  }
  return null;
}

function findReferences(document, token) {
  const refs = [];
  const wordPattern = /(?:##MNEMONIC_PATTERN##|##LABEL_PATTERN##)/gi;

  function scanLines(lines, uri) {
    for (let lineIdx = 0; lineIdx < lines.length; lineIdx += 1) {
      const text = lines[lineIdx];
      const searchRanges = getSemanticSearchRanges(text);
      let labelDefs = null;
      let constDef = null;
      let constDefChecked = false;
      for (const range of searchRanges) {
        const segment = text.slice(range.start, range.end);
        wordPattern.lastIndex = 0;
        let match;
        while ((match = wordPattern.exec(segment)) !== null) {
          if (match[0] !== token) {
            continue;
          }
          const offset = range.start + match.index;
          if (labelDefs === null) {
            labelDefs = labelHover.findLabelDefinitions(text);
          }
          if (!constDefChecked) {
            constDef = constantsHover.findConstantDefinition(text);
            constDefChecked = true;
          }
          let isDef = false;
          for (const def of labelDefs) {
            if (def.name === token && def.character === offset) {
              isDef = true;
              break;
            }
          }
          if (!isDef && constDef === token) {
            const constStart = text.indexOf(constDef);
            if (constStart === offset) {
              isDef = true;
            }
          }
          if (!isDef) {
            refs.push({ line: lineIdx, character: offset, uri });
          }
        }
      }
    }
  }

  const lines = [];
  for (let i = 0; i < document.lineCount; i += 1) {
    lines.push(document.lineAt(i).text);
  }
  scanLines(lines, document.uri);

  const baseDir = document.uri.fsPath ? path.dirname(document.uri.fsPath) : null;
  if (baseDir) {
    const includes = includeFiles.collectIncludedFiles(lines, baseDir);
    for (const entry of includes) {
      scanLines(entry.lines, vscode.Uri.file(entry.path));
    }
  }
  return refs;
}

function buildConstantHoverWithValue(constant, location, uri, valueText) {
  const targetUri = location.uri || uri;
  const commandArgs = {
    uri: targetUri.toString(),
    line: location.line,
    character: location.character
  };
  const commandUri = vscode.Uri.parse(
    `command:${OPEN_CONSTANT_COMMAND}?${encodeURIComponent(JSON.stringify(commandArgs))}`
  );
  const filename = targetUri?.fsPath ? path.basename(targetUri.fsPath) : 'file';
  const locationText = targetUri === uri
    ? `Defined at line ${location.line + 1}.`
    : `Defined at line ${location.line + 1} in ${filename}.`;
  let text = `\`${constant}\``;
  if (valueText) {
    text += ` = \`${valueText}\``;
  }
  text += `\n\n${locationText} [Go to definition](${commandUri})`;
  const markdown = new vscode.MarkdownString(text);
  markdown.isTrusted = { enabledCommands: [OPEN_CONSTANT_COMMAND] };
  return markdown;
}

function buildLabelDefinitionSelfHover(label, references, documentUri) {
  if (!references || references.length === 0) {
    const markdown = new vscode.MarkdownString(`\`${label}\`: No references found.`);
    markdown.isTrusted = false;
    return markdown;
  }
  const count = references.length;
  const header = count === 1
    ? `\`${label}\`: 1 reference`
    : `\`${label}\`: ${count} references`;
  const lines = [header, ''];
  for (const ref of references) {
    const lineNum = ref.line + 1;
    const targetUri = ref.uri || documentUri;
    const commandArgs = {
      uri: targetUri.toString(),
      line: ref.line,
      character: ref.character || 0
    };
    const commandUri = vscode.Uri.parse(
      `command:${OPEN_LABEL_COMMAND}?${encodeURIComponent(JSON.stringify(commandArgs))}`
    );
    const filename = targetUri?.fsPath ? path.basename(targetUri.fsPath) : 'file';
    const isSameFile = targetUri.toString() === documentUri.toString();
    const locationLabel = isSameFile
      ? `line ${lineNum}`
      : `line ${lineNum} in ${filename}`;
    lines.push(`- [${locationLabel}](${commandUri})`);
  }
  const markdown = new vscode.MarkdownString(lines.join('\n'));
  markdown.isTrusted = { enabledCommands: [OPEN_LABEL_COMMAND] };
  return markdown;
}

function activate(context) {
  const languageId = getLanguageId(context);
  if (!languageId) {
    return;
  }

  const hoverDocs = loadInstructionDocs(context);
  if (!hoverDocs) {
    return;
  }

  const instructionDocs = hoverDocs.instructions || {};
  const macroDocs = hoverDocs.macros || {};
  const predefinedDocs = hoverDocs.predefined || {};
  const predefinedConstantDocs = predefinedDocs.constants || {};
  const predefinedDataDocs = predefinedDocs.data || {};
  const predefinedMemoryZoneDocs = predefinedDocs.memory_zones || {};
  const directiveDocsAll = hoverDocs.directives || {};
  const directiveCategories = [
    directiveDocsAll.preprocessor || {},
    directiveDocsAll.data_type || {},
    directiveDocsAll.compiler || {}
  ];
  const registerDocs = hoverDocs.registers || {};
  const exprFuncDocs = hoverDocs.expression_functions || {};
  const wordPattern = /(?:##MNEMONIC_PATTERN##|##LABEL_PATTERN##)/i;
  const provider = {
    provideHover(document, position) {
      const hoverSettings = getHoverSettings(document, languageId);
      const lineText = document.lineAt(position.line).text;

      // Check directives first
      if (hoverSettings.mnemonics) {
        const directiveName = getDirectiveAtPosition(lineText, position.character);
        if (directiveName) {
          for (const category of directiveCategories) {
            if (directiveName in category) {
              return new vscode.Hover(buildMarkdownHover(category[directiveName]));
            }
          }
        }
      }

      // Check registers
      if (hoverSettings.mnemonics) {
        if (isOffsetInCodeRegion(lineText, position.character)) {
          const registerName = getRegisterAtPosition(lineText, position.character);
          if (registerName && registerDocs[registerName]) {
            return new vscode.Hover(buildMarkdownHover(registerDocs[registerName]));
          }
        }
      }

      const range = document.getWordRangeAtPosition(position, wordPattern);
      if (!range) {
        return null;
      }

      if (!isOffsetInCodeRegion(lineText, range.start.character)) {
        return null;
      }

      const token = document.getText(range);
      if (!token) {
        return null;
      }

      if (hoverSettings.mnemonics) {
        const key = token.toUpperCase();
        const doc = instructionDocs[key] || macroDocs[key];
        if (doc) {
          return new vscode.Hover(buildMarkdownHover(doc), range);
        }
        const exprDoc = exprFuncDocs[key];
        if (exprDoc) {
          return new vscode.Hover(buildMarkdownHover(exprDoc), range);
        }
      }

      if (hoverSettings.constants) {
        const constantMap = buildConstantDefinitionMap(document);
        const constantLocation = constantsHover.getConstantLocation(constantMap, token);
        if (constantLocation) {
          if (!constantsHover.isDefinitionAtLocation(
            constantMap,
            token,
            range.start.line,
            range.start.character,
            document.uri
          )) {
            const valueText = extractConstantValue(document, token, constantMap);
            const markdown = buildConstantHoverWithValue(
              token, constantLocation, document.uri, valueText
            );
            return new vscode.Hover(markdown, range);
          }
        } else {
          const predefinedConstantDoc = predefinedConstantDocs[token];
          if (predefinedConstantDoc) {
            return new vscode.Hover(buildMarkdownHover(predefinedConstantDoc), range);
          }
        }
      }

      if (hoverSettings.labels) {
        const labelMap = buildLabelDefinitionMap(document);
        const labelLocation = labelHover.getLabelLocation(labelMap, token);
        if (labelLocation) {
          if (labelHover.isDefinitionAtLocation(
            labelMap,
            token,
            range.start.line,
            range.start.character,
            document.uri
          )) {
            const references = findReferences(document, token);
            const markdown = buildLabelDefinitionSelfHover(token, references, document.uri);
            return new vscode.Hover(markdown, range);
          }
          const markdown = buildDefinitionHover(token, labelLocation, document.uri);
          return new vscode.Hover(markdown, range);
        }

        const predefinedLabelDoc = predefinedDataDocs[token] || predefinedMemoryZoneDocs[token];
        if (predefinedLabelDoc) {
          return new vscode.Hover(buildMarkdownHover(predefinedLabelDoc), range);
        }
      }
      return null;
    }
  };

  context.subscriptions.push(
    vscode.languages.registerHoverProvider(languageId, provider)
  );

  context.subscriptions.push(
    vscode.languages.registerDocumentSemanticTokensProvider(
      { language: languageId },
      { provideDocumentSemanticTokens: buildSemanticTokens },
      semanticLegend
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(OPEN_LABEL_COMMAND, (args) => {
      if (!args || !args.uri) {
        return;
      }
      const uri = vscode.Uri.parse(args.uri);
      const position = new vscode.Position(args.line || 0, args.character || 0);
      const range = new vscode.Range(position, position);
      return vscode.commands.executeCommand(
        'editor.action.goToLocations',
        uri,
        position,
        [new vscode.Location(uri, range)],
        'goto'
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(OPEN_CONSTANT_COMMAND, (args) => {
      if (!args || !args.uri) {
        return;
      }
      const uri = vscode.Uri.parse(args.uri);
      const position = new vscode.Position(args.line || 0, args.character || 0);
      const range = new vscode.Range(position, position);
      return vscode.commands.executeCommand(
        'editor.action.goToLocations',
        uri,
        position,
        [new vscode.Location(uri, range)],
        'goto'
      );
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
