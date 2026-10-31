-- 需要提前安装好yarn npm
-- install with yarn or npm
-- 快捷键清单（每行一个）：
-- 本文件插件未定义快捷键（可用命令 `:MarkdownPreviewToggle` 手动开关预览）。
return {
  "iamcco/markdown-preview.nvim",
  cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
  build = "cd app && yarn install",
  init = function()
    vim.g.mkdp_filetypes = { "markdown" }
  end,
  ft = { "markdown" },
}
