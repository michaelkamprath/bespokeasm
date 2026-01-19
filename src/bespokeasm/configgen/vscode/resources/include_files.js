const fs = require('fs');
const path = require('path');
const labelHover = require('./label_hover');

function collectIncludedFiles(lines, baseDir, visited = new Set()) {
  const entries = [];
  for (const line of lines) {
    const includePath = labelHover.parseIncludePath(line);
    if (!includePath) {
      continue;
    }
    const resolved = path.isAbsolute(includePath)
      ? includePath
      : path.resolve(baseDir, includePath);
    if (visited.has(resolved)) {
      continue;
    }
    try {
      const contents = fs.readFileSync(resolved, 'utf8');
      const includeLines = contents.split(/\r?\n/);
      visited.add(resolved);
      entries.push({
        path: resolved,
        lines: includeLines
      });
      entries.push(...collectIncludedFiles(includeLines, path.dirname(resolved), visited));
    } catch (error) {
      console.error('Failed to load include file:', resolved, error);
    }
  }
  return entries;
}

module.exports = { collectIncludedFiles };
