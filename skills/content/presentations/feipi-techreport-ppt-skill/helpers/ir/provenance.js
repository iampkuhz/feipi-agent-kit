/**
 * Provenance 完整性检查。
 * 每个事实性元素必须有 source_refs，且能在 provenance 中找到。
 */
'use strict';

function checkProvenance(ir) {
  const issues = [];
  const provenanceIds = new Set((ir.provenance || []).map(p => p.source_id));
  const sourceIds = new Set((ir.source_summary || []).map(s => s.source_id));

  // Check each element
  for (const el of ir.elements || []) {
    // layout_only elements don't need provenance
    if (el.semantic_role === 'source_note') continue;

    // Elements without source_refs are OK if they are layout/title derived
    if (!el.source_refs || el.source_refs.length === 0) {
      // Some elements are structural and don't need source refs
      if (['title', 'subtitle', 'takeaway'].includes(el.semantic_role)) {
        // Takeaway should have provenance or be a summary of provided facts
        if (el.semantic_role === 'takeaway') {
          // Check if any provenance references the takeaway
          const hasTakeawayProvenance = (ir.provenance || []).some(p =>
            p.used_by_elements && p.used_by_elements.includes(el.id)
          );
          if (!hasTakeawayProvenance) {
            issues.push({
              type: 'takeaway_missing_provenance',
              element_id: el.id,
              message: `takeaway 元素 "${el.id}" 缺少 provenance 追溯`,
              severity: 'warning',
            });
          }
        }
        continue;
      }
      // For other elements, missing source_refs is an issue
      issues.push({
        type: 'element_missing_source_refs',
        element_id: el.id,
        message: `元素 "${el.id}" (role=${el.semantic_role}) 缺少 source_refs`,
        severity: 'hard_fail',
      });
      continue;
    }

    // Check each source_ref exists in provenance
    for (const ref of el.source_refs) {
      if (!provenanceIds.has(ref)) {
        issues.push({
          type: 'source_ref_not_in_provenance',
          element_id: el.id,
          source_ref: ref,
          message: `元素 "${el.id}" 引用了 "${ref}"，但 provenance 中不存在`,
          severity: 'hard_fail',
        });
      }
    }
  }

  // Check provenance entries reference valid elements
  for (const p of ir.provenance || []) {
    const elementIds = new Set((ir.elements || []).map(e => e.id));
    for (const elId of p.used_by_elements || []) {
      if (!elementIds.has(elId)) {
        issues.push({
          type: 'provenance_references_nonexistent_element',
          provenance_source_id: p.source_id,
          element_id: elId,
          message: `provenance "${p.source_id}" 引用了不存在的元素 "${elId}"`,
          severity: 'warning',
        });
      }
    }
  }

  // Check for untraced facts: source_summary items not used by any element
  for (const src of ir.source_summary || []) {
    const usedByProvenance = (ir.provenance || []).some(p =>
      p.source_id === src.source_id && p.used_by_elements && p.used_by_elements.length > 0
    );
    if (!usedByProvenance) {
      issues.push({
        type: 'source_not_used',
        source_id: src.source_id,
        message: `原始材料 "${src.source_id}" 未被任何元素引用`,
        severity: 'warning',
      });
    }
  }

  return issues;
}

module.exports = { checkProvenance };
