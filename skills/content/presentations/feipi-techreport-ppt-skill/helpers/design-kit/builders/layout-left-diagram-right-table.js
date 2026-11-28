/** Legacy builder retired; compatibility is handled by compiler-adapter. */
'use strict';

module.exports = {
  build() {
    throw new Error('legacy design-kit builder 已停用，请使用 v2 adapter');
  },
};
