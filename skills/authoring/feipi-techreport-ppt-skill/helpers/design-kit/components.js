/** Legacy renderer retired: use Semantic IR v2 -> Render Plan -> PptxBackend. */
'use strict';

function retired() {
  throw new Error('design-kit renderer 已停用，请使用 compiler/render-plan-compiler');
}

module.exports = new Proxy({}, { get: () => retired });
