'use strict';

class PptxBackend {
  async write() { throw new Error('PptxBackend.write 必须由具体 adapter 实现'); }
}

module.exports = { PptxBackend };
