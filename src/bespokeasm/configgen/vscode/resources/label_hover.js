function getCodeRanges(line) {
  const ranges = [];
  let segmentStart = 0;
  let inQuote = null;
  let escaped = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
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

  if (!inQuote && segmentStart < line.length) {
    ranges.push({ start: segmentStart, end: line.length });
  }
  return ranges;
}

function isOffsetInCodeRegion(line, offset) {
  const ranges = getCodeRanges(line);
  for (const range of ranges) {
    if (offset >= range.start && offset < range.end) {
      return true;
    }
  }
  return false;
}

function findLineLabelDefinition(line) {
  const match = line.match(/^\s*(##LABEL_PATTERN##)\s*:/);
  if (!match) {
    return null;
  }
  const character = line.indexOf(match[1]);
  if (!isOffsetInCodeRegion(line, character)) {
    return null;
  }
  return { name: match[1], character };
}

function findOperandLabelDefinitions(line) {
  const definitions = [];
  const operandLabelRegex = /@(##LABEL_PATTERN##):\s*/g;
  const ranges = getCodeRanges(line);

  for (const range of ranges) {
    const segment = line.slice(range.start, range.end);
    let match;
    while ((match = operandLabelRegex.exec(segment)) !== null) {
      definitions.push({
        name: match[1],
        character: range.start + match.index + 1
      });
    }
  }

  return definitions;
}

function findLabelDefinitions(line) {
  const definitions = [];
  const lineLabel = findLineLabelDefinition(line);
  if (lineLabel) {
    definitions.push(lineLabel);
  }
  definitions.push(...findOperandLabelDefinitions(line));
  definitions.sort((a, b) => a.character - b.character);
  return definitions;
}

function findLabelDefinition(line) {
  const definitions = findLabelDefinitions(line);
  return definitions.length > 0 ? definitions[0].name : null;
}

function buildLabelDefinitionMap(lines) {
  return buildLabelDefinitionMapForFile(lines, null);
}

function buildLabelDefinitionMapForFile(lines, uri) {
  const labels = new Map();
  for (let i = 0; i < lines.length; i += 1) {
    const text = lines[i];
    const definitions = findLabelDefinitions(text);
    for (const def of definitions) {
      if (labels.has(def.name)) {
        continue;
      }
      labels.set(def.name, {
        line: i,
        character: def.character,
        name: def.name,
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
  findLabelDefinitions,
  getLabelLocation,
  isDefinitionAtLocation,
  parseIncludePath
};
