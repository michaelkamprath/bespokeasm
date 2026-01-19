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
    const def = labelHover.findLabelDefinition(text);
    if (def) {
      const start = text.indexOf(def);
      builder.push(line, start, def.length, labelType, definitionModifier);
    }
    const constDef = constantsHover.findConstantDefinition(text);
    if (constDef) {
      const start = text.indexOf(constDef);
      builder.push(line, start, constDef.length, constantType, definitionModifier);
    }

    const regex = /(##LABEL_PATTERN##)/g;
    let match;
    while ((match = regex.exec(text)) !== null) {
      const word = match[1];
      if (constants.has(word)) {
        if (!(constDef && word === constDef && match.index === text.indexOf(constDef))) {
          builder.push(line, match.index, word.length, constantType, 0);
          continue;
        }
      }
      if (labels.has(word)) {
        if (def && word === def && match.index === text.indexOf(def)) {
          continue;
        }
        builder.push(line, match.index, word.length, labelType, 0);
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
  const wordPattern = /(?:##MNEMONIC_PATTERN##|##LABEL_PATTERN##)/i;
  const provider = {
    provideHover(document, position) {
      const hoverSettings = getHoverSettings(document, languageId);
      const range = document.getWordRangeAtPosition(position, wordPattern);
      if (!range) {
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
          const markdown = new vscode.MarkdownString(doc);
          markdown.isTrusted = false;
          return new vscode.Hover(markdown, range);
        }
      }

      if (hoverSettings.constants) {
        const constantMap = buildConstantDefinitionMap(document);
        const constantLocation = constantsHover.getConstantLocation(constantMap, token);
        if (constantLocation &&
            !constantsHover.isDefinitionAtLocation(
              constantMap,
              token,
              range.start.line,
              range.start.character,
              document.uri
            )) {
          const markdown = buildConstantHover(token, constantLocation, document.uri);
          return new vscode.Hover(markdown, range);
        }
      }

      if (hoverSettings.labels) {
        const labelMap = buildLabelDefinitionMap(document);
        const labelLocation = labelHover.getLabelLocation(labelMap, token);
        if (!labelLocation) {
          return null;
        }
        if (labelHover.isDefinitionAtLocation(
          labelMap,
          token,
          range.start.line,
          range.start.character,
          document.uri
        )) {
          return null;
        }
        const markdown = buildDefinitionHover(token, labelLocation, document.uri);
        return new vscode.Hover(markdown, range);
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
