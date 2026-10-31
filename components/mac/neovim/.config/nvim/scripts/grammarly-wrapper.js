// Grammarly LSP 启动前的环境修复
// Node 22/24 下 web-tree-sitter 会用 fetch 加载本地 wasm，导致 URL 解析失败
// 这里提供一个“文件路径优先”的 fetch：本地路径用 fs 读，其他 URL 再交给 node-fetch
const fs = require("fs");
const path = require("path");
const nodeFetch = require(
  path.join(
    process.env.HOME || "",
    ".local/share/nvim/mason/packages/grammarly-languageserver/node_modules/grammarly-languageserver/node_modules/node-fetch"
  )
);

function filePathToArrayBuffer(filePath) {
  // 读取本地文件并返回 ArrayBuffer，供 tree-sitter 使用
  const buf = fs.readFileSync(filePath);
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
}

function isLocalPath(input) {
  if (typeof input === "string") {
    return input.startsWith("/") || input.startsWith("./") || input.startsWith("../");
  }
  if (input && typeof input.url === "string") {
    return input.url.startsWith("/") || input.url.startsWith("./") || input.url.startsWith("../");
  }
  return false;
}

globalThis.fetch = (input, init) => {
  if (isLocalPath(input)) {
    const rawPath = typeof input === "string" ? input : input.url;
    const absPath = path.resolve(rawPath);
    return Promise.resolve({
      ok: true,
      arrayBuffer: async () => filePathToArrayBuffer(absPath),
    });
  }
  return nodeFetch(input, init);
};
globalThis.Headers = nodeFetch.Headers;
globalThis.Request = nodeFetch.Request;
globalThis.Response = nodeFetch.Response;

// 继续启动 Grammarly 语言服务器（保持 stdio 通信）
const serverPath = path.join(
  process.env.HOME || "",
  ".local/share/nvim/mason/packages/grammarly-languageserver/node_modules/grammarly-languageserver/bin/server.js"
);
require(serverPath);
