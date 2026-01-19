function findLabelDefinition(line) {
  const match = line.match(/^\s*(##LABEL_PATTERN##)\s*:/);
  return match ? match[1] : null;
}

function buildLabelDefinitionMap(lines) {
  return buildLabelDefinitionMapForFile(lines, null);
}

function buildLabelDefinitionMapForFile(lines, uri) {
  const labels = new Map();
  for (let i = 0; i < lines.length; i += 1) {
    const text = lines[i];
    const def = findLabelDefinition(text);
    if (def) {
      labels.set(def, {
        line: i,
        character: text.indexOf(def),
        name: def,
        uri
      });
    }
  }
  return labels;
}

function buildLabelDefinitionMapFromFiles(fileEntries) {
  const merged = new Map();
  for (const entry of fileEntries) {
    const perFile = buildLabelDefinitionMapForFile(entry.lines, entry.uri);
    for (const [label, location] of perFile.entries()) {
      if (!merged.has(label)) {
        merged.set(label, location);
      }
    }
  }
  return merged;
}

function parseIncludePath(line) {
  const match = line.match(/^\s*#include\s+(?:"([^"]+)"|<([^>]+)>|(\S+))/i);
  if (!match) {
    return null;
  }
  return match[1] || match[2] || match[3] || null;
}

function getLabelLocation(labelMap, token) {
  if (!token) {
    return null;
  }
  return labelMap.get(token) || null;
}

function isDefinitionAtLocation(labelMap, token, line, character, uri) {
  const location = getLabelLocation(labelMap, token);
  if (!location) {
    return false;
  }
  if (uri && location.uri && uri.toString() !== location.uri.toString()) {
    return false;
  }
  return location.line === line && location.character === character;
}

module.exports = {
  buildLabelDefinitionMap,
  buildLabelDefinitionMapForFile,
  buildLabelDefinitionMapFromFiles,
  findLabelDefinition,
  getLabelLocation,
  isDefinitionAtLocation,
  parseIncludePath
};
