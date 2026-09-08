'use strict';

const LAYOUT_ALIASES = {
  'architecture-map': 'layered-architecture',
  'layered-stack': 'layered-architecture',
  'capability-map': 'layered-architecture',
  'metrics-dashboard': 'layered-architecture',
  'comparison-matrix': 'solution-comparison',
  'flow-diagram': 'multi-party-flow',
  'roadmap-timeline': 'multi-party-flow',
  'decision-tree': 'multi-party-flow',
  'primitive-gallery': 'layered-architecture',
};

function textRoleForLegacy(element) {
  if (element.semantic_role === 'title') return 'title';
  if (element.semantic_role === 'subtitle') return 'subtitle';
  if (element.semantic_role === 'takeaway') return 'section_title';
  if (element.kind === 'table' || element.kind === 'matrix') return 'table_cell';
  if (element.kind === 'footer_note' || element.semantic_role === 'source_note') return 'footer';
  if (element.kind === 'step_marker') return 'diagram_badge';
  if (element.kind === 'component_node') return 'diagram_node';
  if (element.kind === 'note' || element.kind === 'legend') return 'caption';
  if (element.kind === 'kpi_card') return 'kpi_label';
  return 'body';
}

function componentForLegacy(element) {
  if (element.kind === 'table' || element.kind === 'matrix') return 'native-table';
  if (element.kind === 'footer_note' || element.semantic_role === 'source_note') return 'source-note';
  if (element.kind === 'component_node' || element.kind === 'kpi_card') return 'capability-group';
  if (element.kind === 'step_marker') return 'text-hierarchy';
  return 'text-hierarchy';
}

function variantForLegacy(element, componentId) {
  if (componentId === 'native-table') return 'comparison_matrix';
  if (componentId === 'source-note') return 'standard';
  if (componentId === 'capability-group') return 'standard';
  const role = textRoleForLegacy(element);
  if (role === 'section_title' && element.semantic_role === 'takeaway') return 'takeaway';
  return ['title', 'subtitle', 'section_title', 'body', 'caption', 'footer'].includes(role) ? role : 'body';
}

function adaptV1ToV2(doc) {
  const layoutId = LAYOUT_ALIASES[doc.layout_pattern] || 'layered-architecture';
  return {
    version: 'v2',
    slide_id: doc.slide_id,
    language: doc.language || 'zh-CN',
    audience: doc.audience || 'CTO / technical executive',
    layout_id: layoutId,
    density: 'standard',
    source_summary: doc.source_summary || [],
    takeaway: doc.takeaway || '',
    elements: (doc.elements || []).map(element => {
      const componentId = componentForLegacy(element);
      return {
        id: element.id,
        component_id: componentId,
        variant: variantForLegacy(element, componentId),
        size: componentId === 'text-hierarchy' || componentId === 'source-note' ? 'default' : 'md',
        region_id: element.region_id,
        semantic_role: element.semantic_role,
        text_role: textRoleForLegacy(element),
        content: element.content,
        source_refs: element.source_refs || [],
        _legacy_kind: element.kind,
        _legacy_layout: element.layout || null,
        _legacy_constraints: element.constraints || {},
      };
    }),
    provenance: doc.provenance || [],
    _compatibility: {
      source_version: 'v1',
      source_layout_pattern: doc.layout_pattern,
      canvas: doc.canvas,
      regions: doc.regions || [],
    },
  };
}

module.exports = { adaptV1ToV2, textRoleForLegacy, LAYOUT_ALIASES };
