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

const ANNOTATE_START_RE = /^\s*#annotate(?=\s|$)/;

// Whether a line continues onto the next: it ends with a `\` that is outside quotes, and it
// has no `;` comment (a continued line cannot carry one), as the assembler reads it.
function continuesLine(text) {
  let quote = null;
  let escaped = false;
  for (const character of text) {
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (character === '\\') {
        escaped = true;
      } else if (character === quote) {
        quote = null;
      }
    } else if (character === '"' || character === "'") {
      quote = character;
    } else if (character === ';') {
      return false;
    }
  }
  return quote === null && text.trimEnd().endsWith('\\');
}

// For a later line of a continued #annotate, the row of its #annotate line; otherwise -1.
function annotateContinuationStart(getLine, row) {
  for (let k = row - 1; k >= 0 && continuesLine(getLine(k)); k -= 1) {
    if (ANNOTATE_START_RE.test(getLine(k))) {
      return k;
    }
  }
  return -1;
}

// The later lines of a continued #annotate hold arguments, not assembly: replace them with
// spaces, so `description="..."` on its own line is not read as a constant definition.
function maskAnnotateContinuations(lines) {
  let continuing = false;
  return lines.map((text) => {
    if (continuing) {
      continuing = continuesLine(text);
      return ' '.repeat(text.length);
    }
    continuing = ANNOTATE_START_RE.test(text) && continuesLine(text);
    return text;
  });
}

// The lines symbol lookups and the semantic pass read: #verbatim block text and #annotate
// continuation lines become spaces, and every line keeps its length.
function maskNonAssemblyText(lines) {
  return maskAnnotateContinuations(maskVerbatimBlocks(lines));
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
      const includeLines = maskNonAssemblyText(contents.split(/\r?\n/));
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

module.exports = {
  annotateContinuationStart,
  collectIncludedFiles,
  continuesLine,
  maskNonAssemblyText,
  maskVerbatimBlocks,
};
