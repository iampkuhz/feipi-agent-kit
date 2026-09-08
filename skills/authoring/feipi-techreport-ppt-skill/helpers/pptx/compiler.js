/**
 * 向后兼容编译入口：Slide IR -> Render Plan -> PptxBackend。
 */
'use strict';

const { compileRenderPlan } = require('../../compiler/render-plan-compiler');
const { PptxGenJSBackend } = require('../../adapters/pptxgenjs/backend');

const backend = new PptxGenJSBackend();

function checkDependency() { return backend.checkDependency(); }

async function compile(slideIR, outputPath) {
  try {
    const renderPlan = compileRenderPlan(slideIR);
    const artifact = await backend.write(renderPlan, outputPath);
    return {
      success: true,
      summary: {
        slide_id: renderPlan.slide_id,
        layout_pattern: renderPlan.layout_id,
        elements_rendered: artifact.elements_rendered,
        canvas: {
          width_in: renderPlan.canvas_emu.w / 914400,
          height_in: renderPlan.canvas_emu.h / 914400,
        },
        geometry_hash: renderPlan.geometry_hash,
        overflow: renderPlan.overflow,
        backend: 'pptxgenjs',
      },
      error: null,
    };
  } catch (error) {
    return { success: false, summary: null, error: `PPTX 编译失败: ${error.message}` };
  }
}

module.exports = {
  compile,
  checkDependency,
  BUILDERS: Object.freeze({}),
  getSupportedPatterns: () => ['v1-compatibility', 'layered-architecture', 'solution-comparison', 'multi-party-flow', 'custom-grid'],
};
