#!/usr/bin/env node
// jscg.js ROOT DIR1,DIR2,... OUT.json — function-level call graph for JS/TS via the TypeScript parser.
const fs = require('fs'), path = require('path');
const [, , ROOT, DIRS, OUT] = process.argv;
let ts;
try { ts = require('typescript'); } catch (e) {
  try { ts = require(path.join(ROOT, 'looper-bot', 'node_modules', 'typescript')); } catch (e2) { console.error('typescript not found: run this through tools/callgraph/build.py, which provides it.'); process.exit(2); }
}
const EXCL = new Set(['node_modules', 'dist', 'dist-electron', 'tests', 'test', '__tests__', '.venv', 'release']);
const EXTS = ['.js', '.cjs', '.mjs', '.ts', '.tsx', '.jsx'];
const DENY_TAIL = new Set('push pop shift unshift slice splice map filter forEach reduce find findIndex some every includes indexOf join split trim toLowerCase toUpperCase replace replaceAll startsWith endsWith concat sort keys values entries toString toFixed padStart padEnd charAt charCodeAt substring substr test match exec bind call apply at flat flatMap fill from of trimStart trimEnd localeCompare toISOString toLocaleString toLocaleDateString toLocaleTimeString getTime assign freeze isArray stringify parse now max min round floor ceil abs sqrt random log warn error info debug trace isFinite isNaN isInteger lastIndexOf repeat normalize'.split(' '));
const TRIVIAL_HEAD = new Set('String Number Boolean Array Object parseInt parseFloat isNaN isFinite Math JSON Error TypeError RangeError Set Map WeakMap WeakSet Symbol Date RegExp Promise encodeURIComponent decodeURIComponent encodeURI decodeURI console Reflect Proxy BigInt structuredClone queueMicrotask'.split(' '));
const KEEP_HEAD = new Set('fetch window document navigator localStorage sessionStorage ipcMain ipcRenderer contextBridge BrowserWindow app shell session process crypto setTimeout setInterval clearTimeout clearInterval requestAnimationFrame cancelAnimationFrame addEventListener removeEventListener dispatchEvent postMessage AbortController URL URLSearchParams Response Request Headers TextEncoder TextDecoder WebSocket RTCPeerConnection MediaStream AudioContext speechSynthesis SpeechSynthesisUtterance Audio Blob FormData Intl performance caches indexedDB Notification globalThis self MutationObserver ResizeObserver IntersectionObserver CustomEvent Event'.split(' '));
const CALLBACK_TAIL = new Set(['handle', 'handleOnce', 'on', 'once', 'subscribe', 'register', 'addListener', 'whenReady']);
const GLOBAL_RE = /^(root|window|globalThis|self|global)\.([A-Za-z_$][\w$]*)$/;
const CHANNEL_TAIL = new Set('on once off emit addEventListener removeEventListener handle handleOnce invoke send postMessage dispatchEvent fetch getItem setItem removeItem getElementById querySelector querySelectorAll createElement exposeInMainWorld register subscribe publish setHeader get set has delete Header append header route use open writeHead end json text CustomEvent Event URL'.split(' '));

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.name.startsWith('.')) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (!EXCL.has(e.name)) walk(p, out); continue; }
    if (EXTS.includes(path.extname(e.name)) && !/\.d\.ts$/.test(e.name) && !/\.(test|spec)\./.test(e.name) && !/config\.(ts|js)$/.test(e.name)) out.push(p);
  }
}
const files = [];
for (const d of DIRS.split(',')) { const b = path.join(ROOT, d); if (fs.statSync(b).isFile()) files.push(b); else walk(b, files); }
const fileSet = new Set(files);
const rel = p => path.relative(ROOT, p).split(path.sep).join('/');

function resolveModule(fromFile, spec) {
  if (!spec.startsWith('.') && !spec.startsWith('/')) return null;
  const base = path.resolve(path.dirname(fromFile), spec);
  for (const ext of ['', ...EXTS, '/index.js', '/index.ts', '/index.tsx']) { const c = base + ext; if (fileSet.has(c)) return c; }
  return null;
}

const mods = {};        // relpath -> { functions: {qual:{...}}, imports:{alias:{file,member}}, env:[], exports:[] }
const allDefs = new Map(); // "rel:qual" -> fileinfo

function kindOf(p) { const e = path.extname(p); return e === '.tsx' ? ts.ScriptKind.TSX : e === '.ts' ? ts.ScriptKind.TS : e === '.jsx' ? ts.ScriptKind.JSX : ts.ScriptKind.JS; }

function dotted(n) {
  if (!n) return null;
  switch (n.kind) {
    case ts.SyntaxKind.Identifier: return n.text;
    case ts.SyntaxKind.ThisKeyword: return 'this';
    case ts.SyntaxKind.SuperKeyword: return 'super';
    case ts.SyntaxKind.ImportKeyword: return 'import';
    case ts.SyntaxKind.PropertyAccessExpression: { const b = dotted(n.expression); return b ? `${b}.${n.name.text}` : null; }
    case ts.SyntaxKind.ElementAccessExpression: { const b = dotted(n.expression); if (!b) return null; const a = n.argumentExpression; return ts.isStringLiteralLike(a) ? `${b}.${a.text}` : `${b}[]`; }
    case ts.SyntaxKind.CallExpression: { const b = dotted(n.expression); return b ? `${b}()` : null; }
    case ts.SyntaxKind.NewExpression: { const b = dotted(n.expression); return b ? `new ${b}` : null; }
    case ts.SyntaxKind.ParenthesizedExpression: case ts.SyntaxKind.NonNullExpression: case ts.SyntaxKind.AsExpression:
    case ts.SyntaxKind.TypeAssertionExpression: case ts.SyntaxKind.SatisfiesExpression: case ts.SyntaxKind.AwaitExpression:
      return dotted(n.expression);
    case ts.SyntaxKind.MetaProperty: return 'import.meta';
    default: return null;
  }
}
function litCond(e) {
  while (ts.isParenthesizedExpression(e)) e = e.expression;
  if (ts.isBinaryExpression(e)) {
    const k = e.operatorToken.kind;
    if (k === ts.SyntaxKind.BarBarToken) { const a = litCond(e.left), b = litCond(e.right); return a && b ? `${a} | ${b}` : null; }
    if (k === ts.SyntaxKind.EqualsEqualsEqualsToken || k === ts.SyntaxKind.EqualsEqualsToken) {
      const ls = litText(e.left), rs = litText(e.right);
      if (ls != null && !(rs != null)) { const d = dotted(e.right); return d ? `${d} == "${ls}"` : null; }
      if (rs != null && !(ls != null)) { const d = dotted(e.left); return d ? `${d} == "${rs}"` : null; }
    }
  }
  return null;
}
function litText(n) { if (!n) return null; if (ts.isStringLiteralLike(n)) return n.text; if (ts.isTemplateExpression(n)) return n.getText().slice(0, 80); return null; }
function propName(n) { return n && (ts.isIdentifier(n) || ts.isStringLiteralLike(n) || ts.isNumericLiteral(n) || ts.isPrivateIdentifier(n)) ? n.text : n ? n.getText() : '?'; }

function containerName(obj) { // obj: ObjectLiteralExpression or ClassLikeDeclaration
  const p = obj.parent;
  if (!p) return '<obj>';
  if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
  if (ts.isPropertyAssignment(p)) return `${containerName(p.parent)}.${propName(p.name)}`;
  if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.EqualsToken) return dotted(p.left) || '<obj>';
  if (ts.isCallExpression(p)) { const s = litText(p.arguments[0]); const callee = dotted(p.expression) || 'call'; const tail = callee.split('.').pop(); if (tail === 'exposeInMainWorld' && s) return `window.${s}`; return s && p.arguments[0] !== obj ? `${callee}("${s}")` : `${callee}(obj)`; }
  if (ts.isNewExpression(p)) { const callee = dotted(p.expression) || 'new'; return `new ${callee}(opts)`; }
  if (ts.isReturnStatement(p)) return '<returned-obj>';
  if (ts.isExportAssignment(p)) return 'default';
  if (ts.isParenthesizedExpression(p) || ts.isAsExpression(p) || ts.isSatisfiesExpression(p)) return containerName(p);
  if (ts.isArrayLiteralExpression(p)) return `${containerName(p)}[]`;
  if (ts.isArrowFunction(p) || ts.isFunctionExpression(p)) return '<obj>';
  return '<obj>';
}
function classNameOf(c) { if (c.name) return c.name.text; return containerName(c); }

function fnName(node, classStack) {
  const p = node.parent;
  if (ts.isFunctionDeclaration(node)) return node.name ? node.name.text : 'default';
  if (ts.isConstructorDeclaration(node)) return `${classStack[classStack.length - 1] || '?'}.constructor`;
  if (ts.isMethodDeclaration(node) || ts.isGetAccessor(node) || ts.isSetAccessor(node)) {
    const c = ts.isClassLike(p) ? classNameOf(p) : ts.isObjectLiteralExpression(p) ? containerName(p) : '?';
    return `${c}.${propName(node.name)}`;
  }
  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
    if (ts.isVariableDeclaration(p) && p.initializer === node && ts.isIdentifier(p.name)) return p.name.text;
    if (ts.isPropertyAssignment(p) && p.initializer === node) return `${containerName(p.parent)}.${propName(p.name)}`;
    if (ts.isPropertyDeclaration(p) && p.initializer === node) return `${classStack[classStack.length - 1] || '?'}.${propName(p.name)}`;
    if (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.EqualsToken && p.right === node) {
      const l = dotted(p.left) || '<assigned>';
      return l.startsWith('this.') && classStack.length ? `${classStack[classStack.length - 1]}.${l.slice(5)}` : l;
    }
    if (ts.isExportAssignment(p)) return 'default';
    if (ts.isParenthesizedExpression(p) || ts.isAsExpression(p)) return fnName(p, classStack) ? fnName(p, classStack) : null;
    if (ts.isCallExpression(p) && p.arguments.includes(node)) {
      const cal = (dotted(p.expression) || '').replace(/\(\)$/, ''); const ctail = cal.split('.').pop(); const lit = litText(p.arguments[0]);
      if (lit != null && p.arguments[0] !== node && CALLBACK_TAIL.has(ctail)) return `${cal}("${lit}")`;
      // wrapped definitions: const X = memo(() => ...), forwardRef, useCallback(() => ...) assigned to a name
      const gp = p.parent;
      if (ts.isVariableDeclaration(gp) && ts.isIdentifier(gp.name)) {
        const callee = dotted(p.expression) || '';
        if (/^(React\.)?(memo|forwardRef|useCallback|useMemo|observer|styled|wrap|withRouter)$/.test(callee)) return gp.name.text;
      }
      return null;
    }
    return null;
  }
  return null;
}

for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kindOf(file));
  const r = rel(file);
  const info = { path: r, lines: text.split('\n').length, imports: {}, functions: {}, env: new Set(), exports: new Set(), globals: {}, aliases: {}, defaultExport: null, branchParents: {}, rawCalls: [] };
  const named = { qual: '<module>', line: 1 };
  info.functions['<module>'] = { line: 1, kind: 'module', calls: [], external: [], refs: [], channels: [], jsx: [], _c: [], _r: [], _ch: [] };
  const stack = [named]; const classStack = []; const pendingCases = new Map();
  const line = n => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;

  // imports / requires
  function noteImport(alias, spec, member) { info.imports[alias] = { spec, file: resolveModule(file, spec), member }; }
  function visitImports(n) {
    if (ts.isImportDeclaration(n) && ts.isStringLiteral(n.moduleSpecifier)) {
      const spec = n.moduleSpecifier.text, c = n.importClause;
      if (c) {
        if (c.name) noteImport(c.name.text, spec, 'default');
        if (c.namedBindings) {
          if (ts.isNamespaceImport(c.namedBindings)) noteImport(c.namedBindings.name.text, spec, '*');
          else for (const el of c.namedBindings.elements) noteImport(el.name.text, spec, (el.propertyName || el.name).text);
        }
      } else noteImport(`<side-effect:${spec}>`, spec, '*');
    }
    if (ts.isVariableDeclaration(n) && n.initializer) {
      let init = n.initializer; let member = null;
      if (ts.isPropertyAccessExpression(init) && ts.isCallExpression(init.expression)) { member = init.name.text; init = init.expression; }
      if (ts.isCallExpression(init) && dotted(init.expression) === 'require' && init.arguments[0] && ts.isStringLiteral(init.arguments[0])) {
        const spec = init.arguments[0].text;
        if (ts.isIdentifier(n.name)) noteImport(n.name.text, spec, member || '*');
        else if (ts.isObjectBindingPattern(n.name)) for (const el of n.name.elements) noteImport(el.name.getText(), spec, (el.propertyName ? el.propertyName.getText() : el.name.getText()));
      }
    }
    ts.forEachChild(n, visitImports);
  }
  visitImports(sf);

  function cur() { return info.functions[stack[stack.length - 1].qual]; }
  function isDeclName(n) {
    const p = n.parent; if (!p) return false;
    return (ts.isVariableDeclaration(p) && p.name === n) || (ts.isFunctionDeclaration(p) && p.name === n) || (ts.isParameter(p) && p.name === n)
      || (ts.isPropertyAssignment(p) && p.name === n) || ts.isImportSpecifier(p) || ts.isImportClause(p) || ts.isNamespaceImport(p)
      || (ts.isBindingElement(p) && (p.name === n || p.propertyName === n)) || (ts.isMethodDeclaration(p) && p.name === n) || (ts.isClassDeclaration(p) && p.name === n)
      || (ts.isPropertyDeclaration(p) && p.name === n) || ts.isJsxAttribute(p) || ts.isTypeReferenceNode(p) || ts.isQualifiedName(p) || ts.isTypeQueryNode(p)
      || (ts.isPropertyAccessExpression(p) && p.name === n) || ts.isLabeledStatement(p) || ts.isBreakOrContinueStatement(p) || ts.isExportSpecifier(p) || ts.isInterfaceDeclaration(p) || ts.isTypeAliasDeclaration(p) || ts.isEnumDeclaration(p) || ts.isEnumMember(p) || ts.isPropertySignature(p) || ts.isMethodSignature(p) || ts.isTypeParameterDeclaration(p) || ts.isGetAccessor(p) || ts.isSetAccessor(p) || ts.isShorthandPropertyAssignment(p) && false;
  }
  function visit(n) {
    // exports
    if (ts.isExportAssignment(n)) { const d = dotted(n.expression); if (d) info.exports.add(d); if (!n.isExportEquals && ts.isIdentifier(n.expression)) info.defaultExport = n.expression.text; }
    if ((ts.isFunctionDeclaration(n) || ts.isClassDeclaration(n)) && n.name && n.modifiers && n.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword) && n.modifiers.some(m => m.kind === ts.SyntaxKind.DefaultKeyword)) info.defaultExport = n.name.text;
    if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
      const l = dotted(n.left);
      if (l === 'module.exports' || l === 'exports') {
        if (ts.isObjectLiteralExpression(n.right)) for (const pr of n.right.properties) {
          if (ts.isShorthandPropertyAssignment(pr)) info.exports.add(pr.name.text);
          else if (ts.isPropertyAssignment(pr)) { const d = dotted(pr.initializer); info.exports.add(d || propName(pr.name)); }
          else if (ts.isMethodDeclaration(pr)) info.exports.add(`module.exports.${propName(pr.name)}`);
        } else { const d = dotted(n.right); if (d) info.exports.add(d); }
      } else if (l && (l.startsWith('module.exports.') || l.startsWith('exports.'))) { const d = dotted(n.right); info.exports.add(d || l); }
      const gm = l && l.match(GLOBAL_RE);
      if (gm) { info.globals[gm[2]] = ts.isObjectLiteralExpression(n.right) ? l : (dotted(n.right) || null); info.exports.add(l); }
    }
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer) {
      let init = n.initializer; if (ts.isBinaryExpression(init) && init.operatorToken.kind === ts.SyntaxKind.BarBarToken) init = init.left;
      const d = dotted(init); const am = d && d.match(GLOBAL_RE); if (am) info.aliases[n.name.text] = am[2];
    }
    // dispatch branches: if (name === "tool") { ... } / case "tool":
    if (ts.isIfStatement(n)) {
      const lit = litCond(n.expression);
      if (lit) {
        const top = stack[stack.length - 1]; const qual = `${top.qual} [${lit}]`;
        info.functions[qual] = info.functions[qual] || { line: line(n), kind: 'branch', calls: [], external: [], refs: [], channels: [], jsx: [], _c: [], _r: [], _ch: [] };
        info.branchParents[qual] = top.qual;
        visit(n.expression); stack.push({ qual, line: line(n) }); visit(n.thenStatement); stack.pop();
        if (!info.functions[qual]._c.length && !info.functions[qual]._r.length) delete info.functions[qual];
        if (n.elseStatement) visit(n.elseStatement);
        return;
      }
    }
    if (ts.isCaseClause(n) && litText(n.expression) != null) {
      const blk = n.parent; const pend = pendingCases.get(blk) || [];
      if (!n.statements.length) { pend.push(litText(n.expression)); pendingCases.set(blk, pend); return; } // fall-through: merge into the next case
      const lits = [...pend, litText(n.expression)]; pendingCases.set(blk, []);
      const sw = blk && blk.parent; const subj = sw && ts.isSwitchStatement(sw) ? dotted(sw.expression) || 'switch' : 'switch';
      const top = stack[stack.length - 1]; const qual = `${top.qual} [${subj} == ${lits.map(l => `"${l}"`).join(' | ')}]`;
      info.functions[qual] = info.functions[qual] || { line: line(n), kind: 'branch', calls: [], external: [], refs: [], channels: [], jsx: [], _c: [], _r: [], _ch: [] };
      info.branchParents[qual] = top.qual;
      stack.push({ qual, line: line(n) }); for (const st of n.statements) visit(st); stack.pop();
      if (!info.functions[qual]._c.length && !info.functions[qual]._r.length) delete info.functions[qual];
      return;
    }
    if (ts.isExportDeclaration(n) && n.exportClause && ts.isNamedExports(n.exportClause)) for (const el of n.exportClause.elements) info.exports.add((el.propertyName || el.name).text);
    if ((ts.isFunctionDeclaration(n) || ts.isVariableStatement(n) || ts.isClassDeclaration(n)) && n.modifiers && n.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) {
      if (ts.isFunctionDeclaration(n) && n.name) info.exports.add(n.name.text);
      if (ts.isClassDeclaration(n) && n.name) info.exports.add(n.name.text);
      if (ts.isVariableStatement(n)) for (const d of n.declarationList.declarations) if (ts.isIdentifier(d.name)) info.exports.add(d.name.text);
    }
    // env
    const dn = (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n)) ? dotted(n) : null;
    if (dn && /^(process\.env|import\.meta\.env)\.([A-Za-z_][\w]*)$/.test(dn)) info.env.add(dn.replace(/^(process\.env|import\.meta\.env)\./, ''));

    // class tracking
    if (ts.isClassLike(n)) {
      const cn = classNameOf(n); classStack.push(cn);
      info.functions[cn] = info.functions[cn] || { line: line(n), kind: 'class', calls: [], external: [], refs: [], channels: [], jsx: [], _c: [], _r: [], _ch: [], extends: n.heritageClauses ? n.heritageClauses.map(h => h.getText()).join(' ') : '' };
      ts.forEachChild(n, visit); classStack.pop(); return;
    }
    // function-like
    if (ts.isFunctionLike(n) && !ts.isFunctionTypeNode(n) && !ts.isMethodSignature(n) && !ts.isConstructSignatureDeclaration(n) && !ts.isCallSignatureDeclaration(n) && !ts.isIndexSignatureDeclaration(n) && !ts.isConstructorTypeNode(n)) {
      const nm = fnName(n, classStack);
      if (nm) {
        const top = stack[stack.length - 1];
        const qual = (nm.includes('.') || top.qual === '<module>') ? nm : `${top.qual}.${nm}`;
        const isExp = info.exports.has(nm) || (n.modifiers && n.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) || (n.parent && n.parent.parent && ts.isVariableStatement(n.parent.parent) && n.parent.parent.modifiers && n.parent.parent.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) || (n.parent && n.parent.parent && n.parent.parent.parent && ts.isVariableStatement(n.parent.parent.parent) && n.parent.parent.parent.modifiers && n.parent.parent.parent.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword));
        info.functions[qual] = info.functions[qual] || { line: line(n), kind: ts.isMethodDeclaration(n) || ts.isConstructorDeclaration(n) ? 'method' : 'function', async: !!(n.modifiers && n.modifiers.some(m => m.kind === ts.SyntaxKind.AsyncKeyword)), params: n.parameters.map(p => p.name.getText()).slice(0, 8), exported: !!isExp, calls: [], external: [], refs: [], channels: [], jsx: [], _c: [], _r: [], _ch: [] };
        stack.push({ qual, line: line(n) });
        ts.forEachChild(n, visit); stack.pop(); return;
      }
    }
    // calls
    if (ts.isCallExpression(n) || ts.isNewExpression(n)) {
      const d = dotted(n);
      const callee = d ? d.replace(/\(\)$/, '') : null;
      const tail = callee ? callee.replace(/^new /, '').split('.').pop() : '';
      const arg0 = n.arguments && n.arguments.length ? litText(n.arguments[0]) : null;
      const ch = (arg0 != null && (CHANNEL_TAIL.has(tail) || callee === 'fetch')) ? arg0 : null;
      cur()._c.push({ callee, ch, line: line(n) });
      if (n.arguments) for (const a of n.arguments) {
        let x = a; while (ts.isParenthesizedExpression(x) || ts.isAsExpression(x) || ts.isAwaitExpression(x)) x = x.expression;
        if (ts.isIdentifier(x) || ts.isPropertyAccessExpression(x)) { const dd = dotted(x); if (dd) cur()._r.push(dd); }
        if (ts.isCallExpression(x) && ts.isPropertyAccessExpression(x.expression) && x.expression.name.text === 'bind') { const dd = dotted(x.expression.expression); if (dd) cur()._r.push(dd); }
      }
    }
    // jsx
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) { const d = dotted(n.tagName); if (d && /^[A-Z]/.test(d.split('.').pop())) cur()._c.push({ callee: d, ch: null, line: line(n), jsx: true }); }
    // references (identifiers not in call/decl position)
    if (ts.isIdentifier(n) && !isDeclName(n) && !(ts.isCallExpression(n.parent) && n.parent.expression === n) && !(ts.isNewExpression(n.parent) && n.parent.expression === n)) cur()._r.push(n.text);
    if (ts.isShorthandPropertyAssignment(n)) cur()._r.push(n.name.text);
    if (ts.isPropertyAccessExpression(n) && n.expression.kind === ts.SyntaxKind.ThisKeyword && !(ts.isCallExpression(n.parent) && n.parent.expression === n)) cur()._r.push(dotted(n));
    ts.forEachChild(n, visit);
  }
  visit(sf);
  info.env = [...info.env]; info.exports = [...info.exports].filter(x => !GLOBAL_RE.test(x) || true);
  mods[r] = info;
  for (const q of Object.keys(info.functions)) allDefs.set(`${r}:${q}`, info);
}

// ---- resolution
const nsIndex = {}; // global namespace name -> [{file, expr}]
for (const [r, info] of Object.entries(mods)) for (const [name, expr] of Object.entries(info.globals)) (nsIndex[name] = nsIndex[name] || []).push({ file: r, expr });
const byTail = {}; // topdir -> method tail -> Set(ids)
for (const [id] of allDefs) { const [f, q] = [id.slice(0, id.indexOf(':')), id.slice(id.indexOf(':') + 1)]; if (q === '<module>' || q.includes('[')) continue; const top = f.split('/')[0]; const tail = q.split('.').pop(); const bt = (byTail[top] = byTail[top] || Object.create(null)); (bt[tail] = bt[tail] || new Set()).add(id); }
const byTopDir = {}; // topdir -> name -> [ids]  (shared browser globals / top-level defs)
for (const [id] of allDefs) { const [f, q] = id.split(':'); const top = f.split('/')[0]; if (!q.includes('.') && q !== '<module>') { const bd = (byTopDir[top] = byTopDir[top] || Object.create(null)); (bd[q] = bd[q] || []).push(id); } }

function resolve(r, info, name, scopeQual, classCtx) {
  if (!name) return null;
  name = name.replace(/\(\)/g, '').replace(/\[\]/g, '').replace(/^new /, '');
  const parts = name.split('.'); const head = parts[0];
  if (head === 'this' && parts.length >= 2) {
    for (const [id] of allDefs) { if (id.startsWith(`${r}:`) && id.endsWith(`.${parts[1]}`) && (!classCtx || id === `${r}:${classCtx}.${parts[1]}`)) return id; }
    return null;
  }
  // lexical scopes
  let sc = scopeQual;
  while (sc && sc !== '<module>') { if (allDefs.has(`${r}:${sc}.${name}`) && `${sc}.${name}` !== scopeQual) return `${r}:${sc}.${name}`; sc = sc.includes('.') ? sc.slice(0, sc.lastIndexOf('.')) : ''; }
  if (allDefs.has(`${r}:${name}`)) return `${r}:${name}`;
  { // namespace globals: root.X.m / window.X.m / Alias.m where `var Alias = root.X`
    let nsName = null, nrest = null;
    if (GLOBAL_RE.test(`${head}.${parts[1] || ''}`) && parts.length >= 2) { nsName = parts[1]; nrest = parts.slice(2); }
    else if (info.aliases[head]) { nsName = info.aliases[head]; nrest = parts.slice(1); }
    if (nsName && nsIndex[nsName]) for (const { file: nf, expr } of nsIndex[nsName]) {
      const cands = [];
      if (nrest.length) { const rj = nrest.join('.'); if (expr) cands.push(`${expr}.${rj}`); for (const g of ['root', 'window', 'globalThis', 'self']) cands.push(`${g}.${nsName}.${rj}`); cands.push(`${nsName}.${rj}`, rj); }
      else if (expr) cands.push(expr);
      for (const c of cands) if (allDefs.has(`${nf}:${c}`)) return `${nf}:${c}`;
    }
  }
  if (head === 'window' || head === 'globalThis' || head === 'self') { const rest = parts.slice(1).join('.'); if (rest && allDefs.has(`${r}:${rest}`)) return `${r}:${rest}`; for (const [id] of allDefs) if (id.endsWith(`:${rest}`) || id.endsWith(`:window.${rest}`)) return id; }
  if (info.imports[head]) {
    const im = info.imports[head];
    if (im.file) {
      const tf = rel(im.file); const rest = parts.slice(1);
      const cands = im.member === '*' || im.member === 'default' ? [rest.join('.'), ['default', ...rest].join('.'), ['module.exports', ...rest].join('.')] : [[im.member, ...rest].join('.'), ['module.exports', im.member, ...rest].join('.')];
      const dflt = im.member === 'default' && mods[tf] && mods[tf].defaultExport; if (dflt) cands.unshift([dflt, ...rest].join('.'));
      for (const c of cands) if (c && allDefs.has(`${tf}:${c}`)) return `${tf}:${c}`;
      // imported name may be an exported object with methods, e.g. api.search -> exported const api
      return `${tf}:${(im.member === '*' || im.member === 'default') ? rest.join('.') || im.member : [im.member, ...rest].join('.')}`;
    }
    return null; // external package
  }
  // shared globals within same top-level dir (browser scripts loaded on one page)
  const top = r.split('/')[0]; const g = byTopDir[top] && byTopDir[top][head];
  if (g && g.length === 1 && parts.length === 1 && g[0] !== `${r}:${head}`) return g[0];
  return null;
}

for (const [r, info] of Object.entries(mods)) {
  for (const [q, f] of Object.entries(info.functions)) {
    f.probable = []; const seen = new Set(); const classCtx = f.kind === 'method' ? q.split('.')[0] : (q.includes('.') ? q.split('.')[0] : null);
    for (const c of f._c) {
      if (!c.callee) continue;
      const id = resolve(r, info, c.callee, q, classCtx);
      if (id && !id.endsWith(':')) {
        if (!seen.has(id)) { seen.add(id); (c.jsx ? f.jsx : f.calls).push(id); }
        if (c.ch) f.channels.push(`${c.callee.split('.').pop()}("${c.ch}") -> ${id}`);
        continue;
      }
      const base = c.callee.replace(/^new /, ''); const parts = base.split('.'); const tail = parts[parts.length - 1]; const head = parts[0];
      if (!c.jsx && parts.length >= 2 && !DENY_TAIL.has(tail) && tail.length >= 4 && !TRIVIAL_HEAD.has(head) && !KEEP_HEAD.has(head) && head !== 'this' && head !== 'super') {
        const top = r.split('/')[0]; const cand = byTail[top] && byTail[top][tail];
        if (cand && cand.size === 1) { const pid = [...cand][0]; if (!pid.startsWith(`${r}:`) || true) { if (!seen.has(pid)) { seen.add(pid); f.probable.push(pid); } continue; } }
      }
      if (!c.jsx) {
        if (parts.length === 1 && TRIVIAL_HEAD.has(head)) continue;
        if (parts.length > 1 && TRIVIAL_HEAD.has(head) && !c.ch) continue;
        if (DENY_TAIL.has(tail) && !KEEP_HEAD.has(head) && !c.ch) continue;
      }
      let label = c.callee;
      if (c.ch) label = `${c.callee}("${c.ch}")`;
      if (!seen.has(label)) { seen.add(label); f.external.push(label); }
    }
    for (const d of f._r) {
      const id = resolve(r, info, d, q, classCtx);
      if (id && !seen.has(id) && allDefs.has(id)) { seen.add(id); f.refs.push(id); }
    }
    delete f._c; delete f._r; delete f._ch; f.called_by = [];
  }
}
// a branch is reached through the function that contains it
for (const [r, info] of Object.entries(mods)) for (const [bq, pq] of Object.entries(info.branchParents)) {
  const parent = info.functions[pq]; const id = `${r}:${bq}`;
  if (info.functions[bq] && parent && !parent.calls.includes(id)) parent.calls.push(id);
}
for (const [r, info] of Object.entries(mods)) for (const [q, f] of Object.entries(info.functions)) for (const t of [...f.calls, ...f.refs, ...f.jsx, ...f.probable]) {
  const [tf, tq] = [t.slice(0, t.indexOf(':')), t.slice(t.indexOf(':') + 1)];
  if (mods[tf] && mods[tf].functions[tq]) mods[tf].functions[tq].called_by.push(`${r}:${q}`);
}
fs.writeFileSync(OUT, JSON.stringify({ root: ROOT, modules: mods }, null, 1));
let nf = 0, ne = 0; for (const i of Object.values(mods)) for (const f of Object.values(i.functions)) { nf++; ne += f.calls.length + f.refs.length + f.jsx.length; }
console.log(`files=${Object.keys(mods).length} functions=${nf} internal_edges=${ne} -> ${OUT}`);
