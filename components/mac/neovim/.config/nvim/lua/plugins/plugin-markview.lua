-- For `plugins/markview.lua` users.
-- 快捷键清单（每行一个）：
-- markview.nvim `<leader>md`：切换 Markdown 预览渲染。
return {
  "OXY2DEV/markview.nvim",
  lazy = false,
  enabled = not vim.g.vscode, -- 在 VSCode 中禁用
  opts = {
    enable = false,
  },
  -- 在 lazy.nvim 配置中
  keys = {
    { "<leader>md", "<cmd>Markview toggle<CR>", desc = "Toggle Markview preview" },
  },
  ft = { "markdown" },
}
