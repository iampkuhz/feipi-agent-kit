'use strict';

const fs = require('fs');
const loadDependency = require('../../helpers/dependencies');
const path = require('path');
const { PptxBackend } = require('../pptx-backend');
const primitives = require('../../helpers/pptx/primitives');
const { TokenStore } = require('../../compiler/token-store');
const { EMU_PER_INCH } = require('../../compiler/render-plan-compiler');
const { fixDuplicateCnvpIds } = require('../../helpers/pptx/fix-duplicate-cnvp-id');

class PptxGenJSBackend extends PptxBackend {
  constructor(options = {}) {
    super();
    this.tokens = options.tokens || TokenStore.loadDefault();
  }

  checkDependency() {
    try { loadDependency('pptxgenjs'); return { available: true, error: null }; }
    catch (error) { return { available: false, error: `pptxgenjs 未安装: ${error.message}` }; }
  }

  async write(input, outputPath) {
    const plans = Array.isArray(input) ? input : [input];
    if (!plans.length) throw new Error('PPTX 至少需要一页 Render Plan');
    const renderPlan = plans[0];
    if (plans.some(plan => plan.canvas_emu.w !== renderPlan.canvas_emu.w || plan.canvas_emu.h !== renderPlan.canvas_emu.h)) {
      throw new Error('同一 PPTX 的页面尺寸必须一致');
    }
    const dependency = this.checkDependency();
    if (!dependency.available) throw new Error(dependency.error);
    const PptxGenJS = loadDependency('pptxgenjs');
    const pptx = new PptxGenJS();
    const width = renderPlan.canvas_emu.w / EMU_PER_INCH;
    const height = renderPlan.canvas_emu.h / EMU_PER_INCH;
    pptx._presLayout = {
      name: 'custom', width: renderPlan.canvas_emu.w, height: renderPlan.canvas_emu.h,
      _sizeW: renderPlan.canvas_emu.w, _sizeH: renderPlan.canvas_emu.h,
    };
    pptx.defineLayout({ name: 'Custom', width, height });
    pptx.layout = 'Custom';
    pptx.theme = {
      headFontFace: this.tokens.fontFace('title'),
      bodyFontFace: this.tokens.fontFace('default'),
      lang: 'zh-CN',
    };
    pptx.author = 'feipi-techreport-ppt-skill';
    pptx.subject = renderPlan.slide_id;
    pptx.title = renderPlan.slide_id;

    for (const plan of plans) {
      const slide = pptx.addSlide();
      slide.background = { color: this.tokens.color('surface.page').replace(/^#/, '') };
      plan.elements
        .map((element, index) => ({ element, index }))
        .sort((a, b) => (a.element.z_order - b.element.z_order) || (a.index - b.index))
        .forEach(({ element }) => primitives.renderElement(slide, element));
    }

    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    await pptx.writeFile({ outputType: 'nodefs', fileName: outputPath });
    const compatibilityFix = fixDuplicateCnvpIds(outputPath);
    if (!compatibilityFix.success) throw new Error(compatibilityFix.error);
    const stats = fs.statSync(outputPath);
    if (stats.size === 0) throw new Error(`PPTX 文件为空: ${outputPath}`);
    return { path: outputPath, size_bytes: stats.size, elements_rendered: plans.reduce((sum, plan) => sum + plan.elements.length, 0), compatibility_fix: 'cNvPr-id' };
  }
}

module.exports = { PptxGenJSBackend };
