#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const Ajv2020 = require('ajv/dist/2020');
const { TokenStore } = require('../../compiler/token-store');
const { ContractRegistry } = require('../../compiler/contract-registry');
const { validateSlideIR } = require('../../compiler/slide-ir-validator');
const { compileRenderPlan } = require('../../compiler/render-plan-compiler');
const { validateResolvedTextRoles } = require('../../compiler/text-role-validator');
const { evaluateOverflow, ORDERED_OVERFLOW_STATES } = require('../../compiler/overflow-evaluator');
const compiler = require('../../helpers/pptx/compiler');
const postcheck = require('../../helpers/pptx/postcheck');
const primitives = require('../../helpers/pptx/primitives');
const designKitAdapter = require('../../helpers/design-kit/adapters/compiler-adapter');
const { renderPptxEvidence } = require('../../helpers/pipeline/run-pipeline');

const ROOT = path.resolve(__dirname, '..', '..');
let passed = 0;

function test(name, fn) {
  return Promise.resolve().then(fn).then(() => { passed++; process.stdout.write(`ok ${passed} - ${name}\n`); });
}

function readJson(relativePath) { return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), 'utf-8')); }

function expectInvalid(doc, pattern) {
  const result = validateSlideIR(doc);
  assert.equal(result.valid, false, '输入应校验失败');
  assert.match(result.errors.join('\n'), pattern);
}

function rolePlan(role, size, kind = 'text', slot) {
  const style = slot
    ? { font_size_pt: size, font_size_token: `typography.sizes_pt.${role}`, slot_styles: { [slot]: { text_role: role, font_size_pt: size, font_size_token: `typography.sizes_pt.${role}` } } }
    : { font_size_pt: size, font_size_token: `typography.sizes_pt.${role}` };
  return { elements: [{ id: 'probe', kind, text_role: role, resolved_style: style }] };
}

function openXmlGeometry(xml, objectName) {
  const start = xml.indexOf(`name="${objectName}"`);
  assert.ok(start >= 0, `OpenXML 缺少语义对象名 ${objectName}`);
  const scope = xml.slice(start, start + 12000);
  const match = scope.match(/<(?:a|p):xfrm\b[^>]*>[\s\S]*?<a:off x="(\d+)" y="(\d+)"\s*\/>[\s\S]*?<a:ext cx="(\d+)" cy="(\d+)"\s*\/>/);
  assert.ok(match, `OpenXML 缺少 ${objectName} 的几何`);
  return { x: Number(match[1]), y: Number(match[2]), w: Number(match[3]), h: Number(match[4]) };
}

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'feipi-p0-tests-'));
  try {
    await test('Token Store 对未知、缺失和循环引用硬失败', () => {
      const store = new TokenStore({ demo: { a: { $ref: 'demo.b' }, b: { $ref: 'demo.a' } } });
      assert.throws(() => store.resolve('demo.missing'), /未知 token/);
      assert.throws(() => store.resolve('demo.a'), /循环引用/);
      assert.throws(() => TokenStore.loadDefault().assertRegisteredFontSize(9.7), /未登记/);
    });

    await test('Component Contract 的 token 引用全部可解析', () => {
      assert.deepEqual(new ContractRegistry().validateTokenReferences(), []);
    });

    await test('v2 Schema 拒绝任意 font_size=9.7', () => {
      const doc = readJson('tests/fixtures/acceptance/layered-architecture.slide-ir.v2.json');
      doc.elements[0].font_size = 9.7;
      expectInvalid(doc, /additional properties|must NOT have/);
    });

    await test('body_dense 仅为 legacy token，v2 正文不能选择该角色', () => {
      const doc = readJson('tests/fixtures/acceptance/layered-architecture.slide-ir.v2.json');
      doc.elements[0].text_role = 'body_dense';
      expectInvalid(doc, /must be equal to one of the allowed values/);
      assert.equal(readJson('design-system/components/capability-group.json').contract.slots.items.text_role, 'body');
    });

    await test('v1 compatibility 拒绝未登记 font_size_pt=9.7', () => {
      const doc = readJson('tests/fixtures/architecture-map.slide-ir.json');
      doc.elements[0].style.font_size_pt = 9.7;
      expectInvalid(doc, /未登记到 typography token/);
    });

    await test('普通模式拒绝任意 style 和坐标', () => {
      const doc = readJson('tests/fixtures/acceptance/layered-architecture.slide-ir.v2.json');
      doc.elements[0].style = { color: '#000000' };
      doc.elements[0].x = 1;
      expectInvalid(doc, /additional properties|must NOT have/);
    });

    await test('custom-grid 只接受整数网格，不接受 inch 坐标', () => {
      const base = readJson('tests/fixtures/acceptance/layered-architecture.slide-ir.v2.json');
      const doc = {
        ...base, layout_id: 'custom-grid',
        elements: [{ ...base.elements[0], region_id: 'main', grid_position: { column: 1, row: 1, column_span: 12, row_span: 2 } }],
        provenance: [{ ...base.provenance[0], used_by_elements: ['title'] }],
      };
      assert.equal(validateSlideIR(doc).valid, true);
      doc.elements[0].grid_position.column = 1.5;
      expectInvalid(doc, /integer/);
    });

    await test('body 小于 token minimum 时失败', () => {
      const result = validateResolvedTextRoles(rolePlan('body', 9));
      assert.equal(result.valid, false);
      assert.match(result.errors.join('\n'), /body.*9pt/);
    });

    await test('table_cell 小于自己的 minimum 时失败', () => {
      const result = validateResolvedTextRoles(rolePlan('table_cell', 8, 'matrix', 'rows'));
      assert.equal(result.valid, false);
      assert.match(result.errors.join('\n'), /table_cell/);
    });

    await test('caption 和 footer 分别按自己的 minimum 校验', () => {
      assert.equal(validateResolvedTextRoles(rolePlan('caption', 7)).valid, false);
      assert.equal(validateResolvedTextRoles(rolePlan('footer', 7)).valid, false);
      assert.equal(validateResolvedTextRoles(rolePlan('caption', 8.5)).valid, true);
      assert.equal(validateResolvedTextRoles(rolePlan('footer', 8.5)).valid, true);
    });

    await test('Renderer 缺 resolved token 时硬失败且无字号 fallback', () => {
      assert.throws(() => primitives.renderElement({ addText() {} }, { id: 'bad', kind: 'text', bounds_emu: { x: 0, y: 0, w: 1, h: 1 }, content: 'x' }), /resolved_style/);
      const activeSources = [
        'helpers/pptx/primitives.js', 'adapters/pptxgenjs/backend.js', 'compiler/render-plan-compiler.js',
        'helpers/design-kit/token-resolver.js', 'helpers/layout/autofit.js',
      ].map(file => fs.readFileSync(path.join(ROOT, file), 'utf-8')).join('\n');
      assert.doesNotMatch(activeSources, /autoFit\s*:\s*true|fontScale|fontSize\s*:\s*\d/);
    });

    await test('overflow 只返回固定动作序列，不生成新字号', () => {
      const plan = {
        elements: [{
          id: 'overflow', kind: 'text', content: '这是一段会超过固定区域容量的长文本'.repeat(20),
          bounds_emu: { x: 0, y: 0, w: 914400, h: 100000 }, resolved_style: { font_size_pt: 10 },
        }],
      };
      const result = evaluateOverflow(plan);
      assert.equal(result.status, 'compress_text');
      assert.deepEqual(result.next_actions, ORDERED_OVERFLOW_STATES);
      assert.equal(plan.elements[0].resolved_style.font_size_pt, 10);
    });

    const acceptance = fs.readdirSync(path.join(ROOT, 'tests', 'fixtures', 'acceptance')).filter(name => name.endsWith('.json')).sort();
    await test('三个 v2 场景产生稳定 Render Plan 几何 hash', () => {
      for (const file of acceptance) {
        const doc = readJson(path.join('tests', 'fixtures', 'acceptance', file));
        const first = compileRenderPlan(doc);
        const second = compileRenderPlan(doc);
        assert.equal(first.geometry_hash, second.geometry_hash, file);
        assert.equal(first.overflow.status, 'fit', file);
        assert.ok(first.elements.filter(element => element.kind !== 'connector').every(element => element.text_role), file);
      }
    });

    const outputs = [];
    await test('三个 v2 场景生成真实原生可编辑 PPTX', async () => {
      for (const file of acceptance) {
        const doc = readJson(path.join('tests', 'fixtures', 'acceptance', file));
        const plan = compileRenderPlan(doc);
        const output = path.join(tempDir, file.replace('.slide-ir.v2.json', '.pptx'));
        const built = await compiler.compile(doc, output);
        assert.equal(built.success, true, built.error);
        const checked = await postcheck.postcheck(output, { expectedSlides: 1, releaseMode: true });
        assert.equal(checked.success, true, JSON.stringify(checked.issues));
        assert.ok(checked.stats.editable_objects.text_shapes > 0);
        assert.equal(checked.stats.editable_objects.pictures, 0);
        assert.ok(checked.stats.semantic_object_names.every(name => name.startsWith('feipi__')));
        const slideXml = execFileSync('unzip', ['-p', output, 'ppt/slides/slide1.xml'], { encoding: 'utf8' });
        for (const element of plan.elements) {
          const actual = openXmlGeometry(slideXml, element.object_name);
          for (const key of ['x', 'y', 'w', 'h']) {
            assert.ok(Math.abs(actual[key] - element.bounds_emu[key]) <= 10, `${file}:${element.id}.${key} OpenXML 与 Render Plan 不一致`);
          }
        }
        outputs.push(output);
      }
      const comparison = await postcheck.postcheck(outputs.find(file => file.includes('solution-comparison')));
      assert.ok(comparison.stats.editable_objects.native_tables > 0);
      const flow = await postcheck.postcheck(outputs.find(file => file.includes('multi-party-flow')));
      assert.ok(flow.stats.editable_objects.native_lines > 0);
    });

    await test('现有三份 v1 代表 fixture 仍可生成', async () => {
      for (const file of ['architecture-map.slide-ir.json', 'comparison-matrix.slide-ir.json', 'flow-diagram.slide-ir.json']) {
        const output = path.join(tempDir, `v1-${file}.pptx`);
        const built = await compiler.compile(readJson(path.join('tests', 'fixtures', file)), output);
        assert.equal(built.success, true, `${file}: ${built.error}`);
        assert.ok(fs.statSync(output).size > 0);
      }
    });

    await test('两份 legacy design-kit fixture 通过仓内 adapter 生成', async () => {
      for (const file of ['design-kit-left-diagram-right-table.json', 'design-kit-roadmap-5-stage.json']) {
        const normalized = designKitAdapter.normalizeToSlideIR(readJson(path.join('tests', 'fixtures', file)));
        assert.equal(validateSlideIR(normalized).valid, true, file);
        const built = await compiler.compile(normalized, path.join(tempDir, `${file}.pptx`));
        assert.equal(built.success, true, built.error);
      }
    });

    await test('Render Plan Schema 可校验编译产物', () => {
      const schema = readJson('schemas/render-plan.schema.json');
      const validate = new Ajv2020({ strict: false, allowUnionTypes: true }).compile(schema);
      const doc = readJson('tests/fixtures/acceptance/solution-comparison.slide-ir.v2.json');
      assert.equal(validate(compileRenderPlan(doc)), true, JSON.stringify(validate.errors));
    });

    await test('QuickLook/CoreText 可为三个场景生成全尺寸视觉证据', () => {
      if (process.platform !== 'darwin' || !fs.existsSync('/usr/bin/qlmanage')) return;
      for (const output of outputs) {
        const evidence = renderPptxEvidence(output, `${output}.render`);
        assert.equal(evidence.status, 'pass', JSON.stringify(evidence.issues));
        assert.equal(evidence.renderer, 'quicklook-coretext');
        assert.ok(evidence.slides[0].width_px >= 1600);
      }
    });

    await test('Render QA 不会仅凭 PNG 存在和宽高比误报视觉通过', () => {
      if (outputs.length === 0) return;
      const output = outputs[0];
      const renderDir = `${output}.render`;
      if (!fs.existsSync(path.join(renderDir, 'render-manifest.json'))) {
        const evidence = renderPptxEvidence(output, renderDir);
        if (evidence.status === 'skip') return;
      }
      const raw = execFileSync(process.execPath, [
        path.join(ROOT, 'scripts', 'visual_qa_report.js'),
        path.join(renderDir, 'render-manifest.json'),
        '--json',
      ], { encoding: 'utf8' });
      const report = JSON.parse(raw);
      assert.equal(report.automatic_status, 'pass');
      assert.equal(report.status, 'needs_visual_review');
      assert.equal(report.visual_review_required, true);
    });

    process.stdout.write(`# P0 tests passed: ${passed}\n`);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error.stack || error.message); process.exit(1); });
