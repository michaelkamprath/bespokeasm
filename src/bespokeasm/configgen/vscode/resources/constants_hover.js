const labelHover = require('./label_hover');

function findConstantDefinition(line) {
  const match = line.match(/^\s*(##LABEL_PATTERN##)\s*(?:=|\bEQU\b)/);
  return match ? match[1] : null;
}

function buildConstantDefinitionMapForFile(lines, uri) {
  const constants = new Map();
  for (let i = 0; i < lines.length; i += 1) {
    const text = lines[i];
    const def = findConstantDefinition(text);
    if (def) {
      constants.set(def, {
        line: i,
        character: text.indexOf(def),
        name: def,
        uri
      });
    }
  }
  return constants;
}

function buildConstantDefinitionMapFromFiles(fileEntries) {
  const merged = new Map();
  for (const entry of fileEntries) {
    const perFile = buildConstantDefinitionMapForFile(entry.lines, entry.uri);
    for (const [name, location] of perFile.entries()) {
      if (!merged.has(name)) {
        merged.set(name, location);
      }
    }
  }
  return merged;
}

function getConstantLocation(constantMap, token) {
  if (!token) {
    return null;
  }
  return constantMap.get(token) || null;
}

function isDefinitionAtLocation(constantMap, token, line, character, uri) {
  const location = getConstantLocation(constantMap, token);
  if (!location) {
    return false;
  }
  if (uri && location.uri && uri.toString() !== location.uri.toString()) {
    return false;
  }
  return location.line === line && location.character === character;
}

module.exports = {
  findConstantDefinition,
  buildConstantDefinitionMapForFile,
  buildConstantDefinitionMapFromFiles,
  getConstantLocation,
  isDefinitionAtLocation,
  parseIncludePath: labelHover.parseIncludePath
};
