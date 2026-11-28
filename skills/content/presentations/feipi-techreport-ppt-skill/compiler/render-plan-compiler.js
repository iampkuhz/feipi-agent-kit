'use strict';

const crypto = require('crypto');
const { TokenStore } = require('./token-store');
const { ContractRegistry } = require('./contract-registry');
const { validateSlideIR } = require('./slide-ir-validator');
const { validateResolvedTextRoles } = require('./text-role-validator');
const { evaluateOverflow } = require('./overflow-evaluator');

const EMU_PER_INCH = 914400;

function inToEmu(value) {
  return Math.max(1, Math.round(Number(value) * EMU_PER_INCH));
}

function rectToEmu(rect) {
  return { x: Math.round(rect.x * EMU_PER_INCH), y: Math.round(rect.y * EMU_PER_INCH), w: inToEmu(rect.w), h: inToEmu(rect.h) };
}

function emuToIn(value) {
  return Number((value / EMU_PER_INCH).toFixed(5));
}

function safeObjectName(componentId, id) {
  return `feipi__${componentId}__${id}`.replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 120);
}

function defaultTextRole(element) {
  if (element.text_role) return element.text_role;
  if (element.component_id === 'native-table') return 'table_cell';
  if (element.component_id === 'flow-step') return 'diagram_node';
  if (element.component_id === 'source-note') return 'footer';
  if (element.component_id === 'capability-group') return 'body';
  return element.variant === 'takeaway' ? 'section_title' : element.variant;
}

function kindForElement(element) {
  if (element._legacy_kind) return element._legacy_kind;
  if (element.component_id === 'native-table') return 'matrix';
  if (element.component_id === 'flow-step') return 'component_node';
  if (element.component_id === 'capability-group') return 'note';
  if (element.component_id === 'source-note') return 'footer_note';
  return 'text';
}

function styleForElement(element, tokens, registry) {
  const textRole = defaultTextRole(element);
  const typography = tokens.typographyRole(textRole);
  const semanticColor = element.semantic_role === 'risk' ? 'semantic.danger'
    : element.semantic_role === 'takeaway' ? 'brand.secondary'
      : element.semantic_role === 'source_note' ? 'text.secondary' : 'text.primary';
  const fillToken = element.semantic_role === 'risk' ? 'surface.panel_red'
    : element.component_id === 'flow-step' || element.component_id === 'capability-group' ? 'surface.panel_blue'
      : 'surface.page';
  const style = {
    font_face: tokens.fontFace(typography.font_family),
    font_family_token: `typography.font_families.${typography.font_family}`,
    font_size_pt: typography.font_size_pt,
    font_size_token: `typography.sizes_pt.${textRole}`,
    color: tokens.color(semanticColor),
    color_token: `colors.tokens.${semanticColor}`,
    fill_color: tokens.color(fillToken),
    fill_token: `colors.tokens.${fillToken}`,
    line_color: tokens.color('border.default'),
    line_width_pt: tokens.lineWidth(element.component_id === 'flow-step' ? 'connector' : 'default'),
    bold: typography.bold || ['title', 'section_title', 'table_header', 'kpi_value'].includes(textRole),
    padding_in: tokens.padding(element.component_id === 'native-table' ? 'table_cell'
      : element.component_id === 'flow-step' ? 'diagram_node'
        : element.component_id === 'capability-group' ? 'card' : 'text_box'),
    corner_radius_in: tokens.cornerRadius(element.component_id === 'flow-step' ? 'md' : 'sm'),
  };
  const component = registry.component(element.component_id, { required: false });
  const slotStyles = {};
  for (const [slot, definition] of Object.entries(component?.contract?.slots || {})) {
    const role = definition.text_role_from_variant ? textRole : definition.text_role;
    if (!role) continue;
    const slotTypography = tokens.typographyRole(role);
    slotStyles[slot] = {
      text_role: role,
      font_face: tokens.fontFace(slotTypography.font_family),
      font_size_pt: slotTypography.font_size_pt,
      font_size_token: `typography.sizes_pt.${role}`,
      color: tokens.color(role === 'footer' || role === 'caption' ? 'text.secondary' : 'text.primary'),
      bold: slotTypography.bold || ['title', 'section_title', 'table_header'].includes(role),
    };
  }
  if (Object.keys(slotStyles).length > 0) style.slot_styles = slotStyles;
  return style;
}

function allocateRegion(region, elements, gap) {
  const bounds = region.bounds_in;
  if (elements.length === 0) return [];
  if (region.flow === 'header') {
    return elements.map((element, index) => {
      const role = defaultTextRole(element);
      if (role === 'title') return { x: bounds.x, y: bounds.y, w: bounds.w, h: 0.55 };
      if (role === 'subtitle') return { x: bounds.x, y: bounds.y + 0.58, w: bounds.w, h: Math.max(0.3, bounds.h - 0.58) };
      const h = (bounds.h - gap * (elements.length - 1)) / elements.length;
      return { x: bounds.x, y: bounds.y + index * (h + gap), w: bounds.w, h };
    });
  }
  if (region.flow === 'horizontal') {
    const w = (bounds.w - gap * (elements.length - 1)) / elements.length;
    return elements.map((element, index) => ({ x: bounds.x + index * (w + gap), y: bounds.y, w, h: bounds.h }));
  }
  if (region.flow === 'stack' || elements.length > 1) {
    const h = (bounds.h - gap * (elements.length - 1)) / elements.length;
    return elements.map((element, index) => ({ x: bounds.x, y: bounds.y + index * (h + gap), w: bounds.w, h }));
  }
  return [{ ...bounds }];
}

function customGridBounds(element, tokens) {
  const canvas = tokens.resolve('spacing.canvas');
  const margin = tokens.resolve('spacing.page.margin_in');
  const gutter = tokens.resolve('spacing.grid.gutter_in');
  const availableW = canvas.width_in - margin * 2;
  const colW = (availableW - gutter * 11) / 12;
  const rowH = 0.4;
  const grid = element.grid_position;
  return {
    x: margin + (grid.column - 1) * (colW + gutter),
    y: margin + (grid.row - 1) * (rowH + gutter),
    w: grid.column_span * colW + (grid.column_span - 1) * gutter,
    h: grid.row_span * rowH + (grid.row_span - 1) * gutter,
  };
}

function compileRenderPlan(doc, options = {}) {
  const tokens = options.tokens || TokenStore.loadDefault();
  const registry = options.registry || new ContractRegistry({ tokens });
  const validation = validateSlideIR(doc, { tokens, registry });
  if (!validation.valid) {
    const error = new Error(`Slide IR 校验失败:\n- ${validation.errors.join('\n- ')}`);
    error.validationErrors = validation.errors;
    throw error;
  }
  const ir = validation.normalized;
  const compatibility = ir._compatibility || null;
  const canvas = compatibility?.canvas || tokens.resolve('spacing.canvas');
  const layout = ir.layout_id === 'custom-grid' ? null : registry.layout(ir.layout_id);
  const gap = tokens.resolve('spacing.grid.card_gap_in');
  const allocations = new Map();

  if (ir.layout_id === 'custom-grid') {
    for (const element of ir.elements) allocations.set(element.id, customGridBounds(element, tokens));
  } else if (compatibility) {
    const regionMap = new Map((compatibility.regions || []).map(region => {
      const contractRegionId = region.role === 'header' ? 'header' : region.role === 'footer' ? 'footer' : region.role === 'takeaway_bar' ? 'takeaway' : null;
      const contractRegion = contractRegionId ? layout?.regions?.[contractRegionId] : null;
      const footerBounds = layout?.regions?.footer?.bounds_in;
      const takeawayBounds = region.role === 'takeaway_bar' && !contractRegion && footerBounds
        ? {
          x: footerBounds.x,
          y: footerBounds.y - gap - region.bounds.h,
          w: footerBounds.w,
          h: region.bounds.h,
        }
        : null;
      return [region.id, {
        bounds_in: contractRegion?.bounds_in || takeawayBounds || region.bounds,
        flow: region.role === 'header' ? 'header' : contractRegion?.flow || 'stack',
        preserve_legacy: !['header', 'footer', 'takeaway_bar'].includes(region.role),
      }];
    }));
    for (const [regionId, region] of regionMap) {
      const elements = ir.elements.filter(element => element.region_id === regionId);
      const generated = allocateRegion(region, elements, gap);
      elements.forEach((element, index) => {
        const legacy = element._legacy_layout;
        const hasLegacyBounds = legacy && ['x', 'y', 'w', 'h'].every(key => typeof legacy[key] === 'number');
        const preserveLegacy = hasLegacyBounds && region.preserve_legacy;
        allocations.set(element.id, preserveLegacy ? { x: legacy.x, y: legacy.y, w: legacy.w, h: legacy.h } : generated[index]);
      });
    }

    // 兼容输入中同一行的独立文本按固定 gap 右移，避免保留历史的轻微压叠。
    for (const regionId of regionMap.keys()) {
      const rowItems = ir.elements
        .filter(element => element.region_id === regionId && ['text', 'note', 'footer_note', 'legend'].includes(element._legacy_kind))
        .map(element => ({ element, bounds: allocations.get(element.id) }))
        .filter(item => item.bounds)
        .sort((a, b) => a.bounds.y - b.bounds.y || a.bounds.x - b.bounds.x);
      for (let index = 1; index < rowItems.length; index++) {
        const previous = rowItems[index - 1];
        const current = rowItems[index];
        if (Math.abs(previous.bounds.y - current.bounds.y) > 0.12) continue;
        const minX = previous.bounds.x + previous.bounds.w + gap;
        if (current.bounds.x < minX) current.bounds.x = minX;
      }
    }

    // 同一区域中纵向相交的兼容文本按固定 gap 下推；若因此越界，Static QA 会返回结构化 overflow。
    for (const regionId of regionMap.keys()) {
      const columnItems = ir.elements
        .filter(element => element.region_id === regionId && ['text', 'note', 'footer_note', 'legend'].includes(element._legacy_kind))
        .map(element => ({ element, bounds: allocations.get(element.id) }))
        .filter(item => item.bounds)
        .sort((a, b) => a.bounds.y - b.bounds.y || a.bounds.x - b.bounds.x);
      for (let index = 1; index < columnItems.length; index++) {
        const current = columnItems[index];
        for (let priorIndex = 0; priorIndex < index; priorIndex++) {
          const prior = columnItems[priorIndex];
          const horizontalOverlap = Math.min(prior.bounds.x + prior.bounds.w, current.bounds.x + current.bounds.w)
            - Math.max(prior.bounds.x, current.bounds.x);
          const verticalOverlap = Math.min(prior.bounds.y + prior.bounds.h, current.bounds.y + current.bounds.h)
            - Math.max(prior.bounds.y, current.bounds.y);
          if (horizontalOverlap > 0 && verticalOverlap > 0) {
            current.bounds.y = prior.bounds.y + prior.bounds.h + gap;
          }
        }
      }
      const regionBounds = regionMap.get(regionId)?.bounds_in;
      if (regionBounds && columnItems.length > 0) {
        const maxBottom = Math.max(...columnItems.map(item => item.bounds.y + item.bounds.h));
        const overflow = maxBottom - (regionBounds.y + regionBounds.h);
        const minTop = Math.min(...columnItems.map(item => item.bounds.y));
        if (overflow > 0 && minTop - overflow >= regionBounds.y) {
          for (const item of columnItems) item.bounds.y -= overflow;
        }
      }
    }

    // v1 takeaway 在固定 footer 之前按实际主体几何收口；高度只能被约束空间截短，不改变字号。
    const compatibilityRoleByRegion = new Map((compatibility.regions || []).map(region => [region.id, region.role]));
    const footerElement = ir.elements.find(element => compatibilityRoleByRegion.get(element.region_id) === 'footer');
    const footerAllocation = footerElement ? allocations.get(footerElement.id) : null;
    const takeawayElements = ir.elements.filter(element => compatibilityRoleByRegion.get(element.region_id) === 'takeaway_bar');
    if (footerAllocation && takeawayElements.length > 0) {
      const minGap = tokens.resolve('spacing.rules.min_element_gap_in');
      const contentBottom = Math.max(0, ...ir.elements
        .filter(element => !['header', 'footer', 'takeaway_bar'].includes(compatibilityRoleByRegion.get(element.region_id)))
        .map(element => allocations.get(element.id))
        .filter(Boolean)
        .map(bounds => bounds.y + bounds.h));
      for (const element of takeawayElements) {
        const bounds = allocations.get(element.id);
        if (!bounds) continue;
        const availableHeight = footerAllocation.y - minGap - (contentBottom + minGap);
        if (availableHeight <= 0) continue;
        bounds.h = Math.min(bounds.h, availableHeight);
        bounds.y = footerAllocation.y - minGap - bounds.h;
      }
    }

    // 连接线只由端点节点几何推导，不使用 solver/fallback 坐标。
    for (const element of ir.elements.filter(item => item._legacy_kind === 'connector')) {
      const from = allocations.get(element.content?.from);
      const to = allocations.get(element.content?.to);
      if (!from || !to) continue;
      allocations.set(element.id, {
        x: from.x + from.w,
        y: from.y + from.h / 2,
        w: Math.max(0.01, to.x - (from.x + from.w)),
        h: Math.max(0.01, (to.y + to.h / 2) - (from.y + from.h / 2)),
      });
    }
  } else {
    for (const [regionId, region] of Object.entries(layout.regions)) {
      const elements = ir.elements.filter(element => element.region_id === regionId);
      const generated = allocateRegion(region, elements, gap);
      elements.forEach((element, index) => allocations.set(element.id, generated[index]));
    }
  }

  const elements = ir.elements.map(element => {
    const bounds = allocations.get(element.id);
    if (!bounds) throw new Error(`元素 ${element.id} 未获得 layout contract 几何`);
    const kind = kindForElement(element);
    return {
      id: element.id,
      object_name: safeObjectName(element.component_id, element.id),
      kind,
      component_id: element.component_id,
      region_id: element.region_id,
      semantic_role: element.semantic_role,
      text_role: kind === 'connector' ? null : defaultTextRole(element),
      bounds_emu: rectToEmu(bounds),
      content: element.content,
      resolved_style: styleForElement(element, tokens, registry),
      z_order: kind === 'connector' ? 10 : kind === 'footer_note' ? 40 : 20,
    };
  });

  if (!compatibility && ir.layout_id === 'multi-party-flow') {
    const steps = elements.filter(element => element.component_id === 'flow-step');
    for (let index = 0; index < steps.length - 1; index++) {
      const from = steps[index];
      const to = steps[index + 1];
      const startX = from.bounds_emu.x + from.bounds_emu.w;
      const endX = to.bounds_emu.x;
      const y = from.bounds_emu.y + Math.round(from.bounds_emu.h / 2);
      elements.push({
        id: `connector_${from.id}_${to.id}`,
        object_name: safeObjectName('flow-connector', `${from.id}_${to.id}`),
        kind: 'connector', component_id: 'flow-connector', region_id: 'main', semantic_role: 'data_flow', text_role: null,
        bounds_emu: { x: startX, y, w: Math.max(1, endX - startX), h: 1 },
        content: { connector_type: 'arrow', from: from.id, to: to.id },
        resolved_style: {
          color: tokens.color('brand.secondary'),
          color_token: 'colors.tokens.brand.secondary',
          line_width_pt: tokens.lineWidth('connector'),
        },
        z_order: 10,
      });
    }
  }

  const geometryPayload = elements.map(element => ({ id: element.id, bounds_emu: element.bounds_emu, z_order: element.z_order }));
  const plan = {
    version: 'render-plan.v1',
    slide_id: ir.slide_id,
    layout_id: ir.layout_id,
    canvas_emu: { x: 0, y: 0, w: inToEmu(canvas.width_in), h: inToEmu(canvas.height_in) },
    elements,
    geometry_hash: crypto.createHash('sha256').update(JSON.stringify(geometryPayload)).digest('hex'),
    source_version: compatibility ? 'v1' : (options.sourceVersion || 'v2'),
  };
  const roleValidation = validateResolvedTextRoles(plan, { tokens });
  if (!roleValidation.valid) throw new Error(`Render Plan text role 校验失败:\n- ${roleValidation.errors.join('\n- ')}`);
  plan.overflow = evaluateOverflow(plan);
  return plan;
}

function toLegacyQAIR(plan) {
  const canvas = {
    preset: 'wide_16_9', width_in: emuToIn(plan.canvas_emu.w), height_in: emuToIn(plan.canvas_emu.h),
    safe_margin_in: 0.25,
  };
  const regions = [];
  for (const regionId of new Set(plan.elements.map(element => element.region_id))) {
    const items = plan.elements.filter(element => element.region_id === regionId);
    const xs = items.map(item => item.bounds_emu.x);
    const ys = items.map(item => item.bounds_emu.y);
    const rs = items.map(item => item.bounds_emu.x + item.bounds_emu.w);
    const bs = items.map(item => item.bounds_emu.y + item.bounds_emu.h);
    regions.push({
      id: regionId, role: regionId === 'header' ? 'header' : regionId === 'footer' ? 'footer' : 'primary_visual',
      bounds: { x: emuToIn(Math.min(...xs)), y: emuToIn(Math.min(...ys)), w: emuToIn(Math.max(...rs) - Math.min(...xs)), h: emuToIn(Math.max(...bs) - Math.min(...ys)) },
      capacity: { max_items: Math.max(1, items.length) }, priority: 1,
    });
  }
  return {
    version: 'render-plan.v1', slide_id: plan.slide_id, canvas, regions,
    elements: plan.elements.map(element => ({
      id: element.id, kind: element.kind, semantic_role: element.semantic_role, text_role: element.text_role,
      region_id: element.region_id, content: element.content,
      layout: { x: emuToIn(element.bounds_emu.x), y: emuToIn(element.bounds_emu.y), w: emuToIn(element.bounds_emu.w), h: emuToIn(element.bounds_emu.h) },
      style: element.text_role ? { font_size_pt: element.resolved_style.font_size_pt } : {},
      constraints: { must_stay_within_region: false },
    })),
  };
}

module.exports = { compileRenderPlan, toLegacyQAIR, inToEmu, emuToIn, EMU_PER_INCH };
