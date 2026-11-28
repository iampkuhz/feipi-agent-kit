/**
 * 兼容占位：文本压缩属于语义层，不能由机械字符串截断或字号估算自动完成。
 */
'use strict';

function compressText() {
  return {
    success: false,
    compressed_text: null,
    provenance: null,
    action: 'compress_text',
    message: '请由语义层删除重复表述并形成新的 IR',
  };
}

module.exports = { compressText };
