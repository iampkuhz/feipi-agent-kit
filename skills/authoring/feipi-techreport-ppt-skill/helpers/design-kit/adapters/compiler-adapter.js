/**
 * 旧 design-kit spec -> Semantic Slide IR v2 兼容适配器。
 * 只读取仓内 contract，不再依赖 Downloads 目录。
 */
'use strict';

function isDesignKitSpec(value) {
  return Boolean(value && value.slideType && Array.isArray(value.components) && !value.version);
}

function mapLayout(slideType) {
  if (slideType === 'left-diagram-right-table') return 'solution-comparison';
  if (slideType === 'roadmap-5-stage') return 'multi-party-flow';
  throw new Error(`不支持的 legacy design-kit slideType: ${slideType}`);
}

function mapRegion(slideType, region) {
  if (slideType === 'left-diagram-right-table') {
    return { 'left.main': 'main-left', 'right.main': 'main-right', 'right.notes': 'evidence' }[region] || region;
  }
  if (slideType === 'roadmap-5-stage') return region === 'matrix' ? 'evidence' : region.startsWith('stage.') ? 'main' : region;
  return region;
}

function mapComponent(component) {
  if (component.type === 'native-table') {
    return { component_id: 'native-table', variant: 'standard', size: 'md', semantic_role: 'evidence', content: component.slots };
  }
  if (component.type === 'timeline-card') {
    const slots = component.slots || {};
    return {
      component_id: 'flow-step', variant: ['done', 'doing', 'planned'].includes(component.variant) ? component.variant : 'standard', size: 'md', semantic_role: 'process_step',
      content: { label: [slots.stage, slots.headline, slots.metric].filter(Boolean).join('\n'), note: (slots.items || []).join('；') },
    };
  }
  const slots = component.slots || {};
  return {
    component_id: 'capability-group', variant: ['primary', 'muted'].includes(component.variant) ? component.variant : 'standard', size: 'md', semantic_role: 'system_component',
    content: { title: slots.title || slots.headline || component.type, items: slots.items || (slots.subtitle ? [slots.subtitle] : []) },
  };
}

function normalizeToSlideIR(spec) {
  if (!isDesignKitSpec(spec)) return spec;
  const sourceId = 'legacy_design_kit_input';
  const elements = [{
    id: 'title', component_id: 'text-hierarchy', variant: 'title', size: 'default', region_id: 'header',
    semantic_role: 'title', text_role: 'title', content: spec.title || spec.slideType, source_refs: [sourceId],
  }];
  for (let index = 0; index < spec.components.length; index++) {
    const component = spec.components[index];
    const mapped = mapComponent(component);
    elements.push({
      id: `${mapped.component_id}_${index + 1}`,
      ...mapped,
      region_id: mapRegion(spec.slideType, component.region),
      source_refs: [sourceId],
    });
  }
  return {
    version: 'v2',
    slide_id: spec.slide_id || `design-kit-${spec.slideType}`,
    language: 'zh-CN',
    audience: 'CTO / technical executive',
    layout_id: mapLayout(spec.slideType),
    density: ['compact', 'standard', 'spacious'].includes(spec.density) ? spec.density : 'standard',
    source_summary: [{ source_id: sourceId, content_type: 'other', description: 'legacy design-kit 输入' }],
    takeaway: spec.title || spec.slideType,
    elements,
    provenance: [{
      source_id: sourceId, source_type: 'user_input', quote_or_summary: 'legacy design-kit 输入',
      used_by_elements: elements.map(element => element.id),
    }],
  };
}

module.exports = { isDesignKitSpec, normalizeToSlideIR, mapLayout, mapRegion, mapComponent };
