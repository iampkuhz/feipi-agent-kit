/**
 * PptxGenJS 原生对象原语。
 * 只接受 Compiler 产出的 resolved_style 和确定性 bounds，不提供视觉 fallback。
 */
'use strict';

const { emuToIn } = require('../../compiler/render-plan-compiler');

function color(value) { return String(value || '').replace(/^#/, ''); }
function marginPoints(values) { return (values || []).map(value => Number((value * 72).toFixed(2))); }

function extractText(element) {
  if (typeof element.content === 'string') return element.content;
  if (element.content?.label) return element.content.label;
  if (element.content?.text) return element.content.text;
  return '';
}

function extractLayout(element) {
  const bounds = element.bounds_emu;
  if (!bounds || !['x', 'y', 'w', 'h'].every(key => Number.isInteger(bounds[key]))) {
    throw new Error(`元素 ${element.id} 缺少 Compiler 生成的 bounds_emu`);
  }
  return { x: emuToIn(bounds.x), y: emuToIn(bounds.y), w: emuToIn(bounds.w), h: emuToIn(bounds.h), hasCoords: true };
}

function mergeStyle(element) {
  const style = element.resolved_style;
  if (!style || typeof style !== 'object') throw new Error(`元素 ${element.id} 缺少 resolved_style`);
  if (element.kind !== 'connector' && element.kind !== 'matrix' && typeof style.font_size_pt !== 'number') {
    throw new Error(`文本元素 ${element.id} 缺少 token 解析后的 font_size_pt`);
  }
  return style;
}

function baseTextOptions(element, align = 'left', valign = 'top') {
  const layout = extractLayout(element);
  const style = mergeStyle(element);
  return {
    ...layout,
    objectName: element.object_name,
    fontFace: style.font_face,
    fontSize: style.font_size_pt,
    color: color(style.color),
    bold: Boolean(style.bold),
    align,
    valign,
    wrap: true,
    margin: marginPoints(style.padding_in),
  };
}

function addTextBox(slide, element) {
  slide.addText(extractText(element), baseTextOptions(element));
}

function addComponentNode(slide, element) {
  const style = mergeStyle(element);
  slide.addText(extractText(element), {
    ...baseTextOptions(element, 'center', 'middle'),
    shape: 'roundRect',
    rectRadius: style.corner_radius_in,
    fill: { color: color(style.fill_color) },
    line: { color: color(style.line_color), width: style.line_width_pt },
  });
}

function addConnector(slide, element) {
  const layout = extractLayout(element);
  const style = mergeStyle(element);
  slide.addShape('line', {
    ...layout,
    objectName: element.object_name,
    line: { color: color(style.color), width: style.line_width_pt, endArrowType: 'triangle' },
  });
}

function addStepMarker(slide, element) { addTextBox(slide, element); }

function addKpiCard(slide, element) { addCapabilityGroup(slide, element); }

function addCapabilityGroup(slide, element) {
  const style = mergeStyle(element);
  const titleStyle = style.slot_styles?.title;
  const itemStyle = style.slot_styles?.items;
  const content = element.content || {};
  const items = Array.isArray(content.items) ? content.items : [];
  if (!titleStyle || !itemStyle) throw new Error(`组件 ${element.id} 缺少 slot_styles`);
  const runs = [
    { text: `${content.title || ''}\n`, options: { fontFace: titleStyle.font_face, fontSize: titleStyle.font_size_pt, color: color(titleStyle.color), bold: titleStyle.bold, breakLine: false } },
    { text: items.map(item => `• ${item}`).join('\n'), options: { fontFace: itemStyle.font_face, fontSize: itemStyle.font_size_pt, color: color(itemStyle.color), bold: itemStyle.bold } },
  ];
  slide.addText(runs, {
    ...extractLayout(element), objectName: element.object_name,
    shape: 'roundRect', rectRadius: style.corner_radius_in,
    fill: { color: color(style.fill_color) },
    line: { color: color(style.line_color), width: style.line_width_pt },
    align: 'left', valign: 'top', wrap: true, margin: marginPoints(style.padding_in),
  });
}

function addMatrix(slide, element) {
  const layout = extractLayout(element);
  const style = mergeStyle(element);
  const headerStyle = style.slot_styles?.headers;
  const cellStyle = style.slot_styles?.rows;
  if (!headerStyle || !cellStyle) throw new Error(`表格 ${element.id} 缺少 header/cell slot style`);
  const content = element.content || {};
  const headers = content.headers || [];
  const rows = content.rows || [];
  const tableRows = [];
  if (headers.length) {
    tableRows.push(headers.map(text => ({ text: String(text), options: {
      fontFace: headerStyle.font_face, fontSize: headerStyle.font_size_pt, color: color(headerStyle.color), bold: headerStyle.bold,
      fill: { color: color(style.fill_color) }, align: 'center', valign: 'middle', margin: marginPoints(style.padding_in),
    } })));
  }
  for (const row of rows) {
    tableRows.push(row.map((text, index) => ({ text: String(text), options: {
      fontFace: cellStyle.font_face, fontSize: cellStyle.font_size_pt, color: color(cellStyle.color), bold: index === 0,
      align: 'center', valign: 'middle', margin: marginPoints(style.padding_in),
    } })));
  }
  if (!tableRows.length) throw new Error(`表格 ${element.id} 没有数据`);
  const rowHeight = layout.h / tableRows.length;
  slide.addTable(tableRows, {
    ...layout, objectName: element.object_name,
    border: { color: color(style.line_color), width: style.line_width_pt, type: 'solid' },
    colW: Array(headers.length || tableRows[0].length).fill(layout.w / (headers.length || tableRows[0].length)),
    rowH: Array(tableRows.length).fill(rowHeight), margin: 0,
  });
}

function addNote(slide, element) {
  if (element.component_id === 'capability-group') return addCapabilityGroup(slide, element);
  const style = mergeStyle(element);
  slide.addText(extractText(element), {
    ...baseTextOptions(element),
    shape: 'roundRect', rectRadius: style.corner_radius_in,
    fill: { color: color(style.fill_color) },
    line: { color: color(style.line_color), width: style.line_width_pt },
  });
}

function addFooterNote(slide, element) { addTextBox(slide, element); }

function addRegionFrame() {
  throw new Error('区域背景必须由 Layout Contract 编译为显式组件，禁止 renderer 自行添加');
}

function renderElement(slide, element) {
  if (element.kind === 'connector') return addConnector(slide, element);
  if (element.kind === 'component_node') return addComponentNode(slide, element);
  if (element.kind === 'step_marker') return addStepMarker(slide, element);
  if (element.kind === 'matrix' || element.kind === 'table') return addMatrix(slide, element);
  if (element.kind === 'kpi_card') return addKpiCard(slide, element);
  if (element.kind === 'note') return addNote(slide, element);
  if (element.kind === 'footer_note') return addFooterNote(slide, element);
  return addTextBox(slide, element);
}

module.exports = {
  renderElement, addTextBox, addComponentNode, addConnector, addStepMarker, addKpiCard,
  addMatrix, addNote, addFooterNote, addRegionFrame, addCapabilityGroup,
  extractText, extractLayout, mergeStyle,
};
