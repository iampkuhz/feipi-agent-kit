#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const Ajv2020 = require('ajv/dist/2020');
const { ContractRegistry } = require('../compiler/contract-registry');

const filePath = path.resolve(process.argv[2] || '');
if (!filePath || !fs.existsSync(filePath)) { console.error(`错误: 文件不存在: ${filePath}`); process.exit(1); }
const doc = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
const schema = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'schemas', 'style-lock.schema.json'), 'utf-8'));
const validate = new Ajv2020({ allErrors: true, strict: false }).compile(schema);
const errors = [];
if (!validate(doc)) errors.push(...validate.errors.map(error => `${error.instancePath || '/'} ${error.message}`));
const registry = new ContractRegistry();
for (const layoutId of doc.layout_refs || []) {
  if (!registry.layout(layoutId, { required: false })) errors.push(`未知 layout_ref: ${layoutId}`);
}
if (errors.length) {
  errors.forEach(error => console.error(`错误: ${error}`));
  process.exit(1);
}
console.log(`校验通过: ${doc.name}（视觉值由 token 派生）`);
