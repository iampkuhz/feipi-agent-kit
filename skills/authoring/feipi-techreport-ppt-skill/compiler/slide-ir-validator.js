'use strict';

const fs = require('fs');
const path = require('path');
const Ajv2020 = require('ajv/dist/2020');
const { TokenStore, DEFAULT_SKILL_ROOT } = require('./token-store');
const { ContractRegistry } = require('./contract-registry');
const { adaptV1ToV2 } = require('./v1-to-v2');

const ajv = new Ajv2020({ allErrors: true, strict: false, allowUnionTypes: true });
const schemaV1 = JSON.parse(fs.readFileSync(path.join(DEFAULT_SKILL_ROOT, 'schemas', 'slide-ir.schema.json'), 'utf-8'));
const schemaV2 = JSON.parse(fs.readFileSync(path.join(DEFAULT_SKILL_ROOT, 'schemas', 'slide-ir.v2.schema.json'), 'utf-8'));
const validateV1Schema = ajv.compile(schemaV1);
const validateV2Schema = ajv.compile(schemaV2);

function formatAjvErrors(errors) {
  return (errors || []).map(error => `${error.instancePath || '/'} ${error.message}`);
}

function checkReferences(doc) {
  const errors = [];
  const sourceIds = new Set((doc.source_summary || []).map(source => source.source_id));
  const elementIds = new Set();
  for (const element of doc.elements || []) {
    if (elementIds.has(element.id)) errors.push(`element id 重复: ${element.id}`);
    elementIds.add(element.id);
    for (const ref of element.source_refs || []) {
      if (!sourceIds.has(ref)) errors.push(`元素 ${element.id} 引用了不存在的 source_ref=${ref}`);
    }
  }
  return errors;
}

function validateV1(doc, tokens) {
  const errors = [];
  if (!validateV1Schema(doc)) errors.push(...formatAjvErrors(validateV1Schema.errors));
  for (const element of doc.elements || []) {
    const value = element.style?.font_size_pt;
    if (value !== undefined) {
      try { tokens.assertRegisteredFontSize(value, `元素 ${element.id} font_size_pt`); }
      catch (error) { errors.push(error.message); }
    }
  }
  errors.push(...checkReferences(doc));
  return errors;
}

function validateV2(doc, registry) {
  const errors = [];
  if (!validateV2Schema(doc)) errors.push(...formatAjvErrors(validateV2Schema.errors));
  errors.push(...checkReferences(doc));
  for (const element of doc.elements || []) {
    if (element.component_id === 'text-hierarchy' && !element.text_role) {
      errors.push(`独立文本元素 ${element.id} 必须声明 text_role`);
    }
    errors.push(...registry.validateElement(element, doc.layout_id));
  }
  return errors;
}

function validateSlideIR(doc, options = {}) {
  const tokens = options.tokens || TokenStore.loadDefault();
  const registry = options.registry || new ContractRegistry({ tokens });
  let sourceVersion = doc.version;
  let normalized = doc;
  let errors = [];

  if (doc && doc.version === 'v1') {
    errors = validateV1(doc, tokens);
    if (errors.length === 0) normalized = adaptV1ToV2(doc);
  } else if (doc && doc.version === 'v2') {
    errors = validateV2(doc, registry);
  } else {
    sourceVersion = 'unknown';
    errors.push('version 必须为 v1 或 v2');
  }

  return { valid: errors.length === 0, errors, warnings: [], normalized, sourceVersion };
}

module.exports = { validateSlideIR, formatAjvErrors, checkReferences };
