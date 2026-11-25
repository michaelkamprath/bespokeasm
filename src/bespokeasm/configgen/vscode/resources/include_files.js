const fs = require('fs');
const path = require('path');
const labelHover = require('./label_hover');

const VERBATIM_START_RE = /^\s*#verbatim(?=\s|;|$)/;
const VERBATIM_END_RE = /^\s*#endverbatim(?=\s|;|$)/;

// The text of a #verbatim block is for an output format, not assembly: replace each of its
// lines with spaces, so symbol lookups and the semantic pass never read, for example, an xmin
// assignment `x = 1` as a constant definition, or follow an #include written in a block. Every
// line keeps its length, so positions computed from these lines still match the document.
function maskVerbatimBlocks(lines) {
  let inBlock = false;
  return lines.map((text) => {
    if (inBlock) {
      if (VERBATIM_END_RE.test(text)) {
        inBlock = false;
        return text;
      }
      return ' '.repeat(text.length);
    }
    if (VERBATIM_START_RE.test(text)) {
      inBlock = true;
    }
    return text;
  });
}

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
      const includeLines = maskVerbatimBlocks(contents.split(/\r?\n/));
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

module.exports = { collectIncludedFiles, maskVerbatimBlocks };
