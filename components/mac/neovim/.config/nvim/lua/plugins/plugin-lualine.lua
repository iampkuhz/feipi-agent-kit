-- 界面最下面的状态栏
--
-- 快捷键清单（每行一个）：
-- 本文件插件未定义快捷键。
return {
  {
    'nvim-lualine/lualine.nvim',
    dependencies = { 'nvim-tree/nvim-web-devicons' },
      config = function()
    require("lualine").setup({
      options = {
        -- 主题可以是 'gruvbox', 'tokyonight', 'dracula', 'onedark', 或者 'auto'
        theme = "auto",
        -- 下面这两行可以换成喜欢的符号，或直接留空
        -- component_separators = { left = "", right = "" },
        -- section_separators = { left = "", right = "" },
        -- 如果你想让它只在大多数文件类型启用，忽略特定类型，也可设置:
        -- disabled_filetypes = { "dashboard", "NvimTree", "packer" },
      },
      sections = {
        lualine_a = { "mode" },
        lualine_b = { "branch", "diff" },
        lualine_c = { "filename" },
        lualine_x = { "encoding", "fileformat", "filetype" },
        lualine_y = { "progress" },
        lualine_z = { "location" },
      },
      -- 你也可以自定义一些不常用的分段（例如 lualine_x、lualine_y 等）
      inactive_sections = {
        lualine_a = {},
        lualine_b = {},
        lualine_c = { "filename" },
        lualine_x = { "location" },
        lualine_y = {},
        lualine_z = {},
      },
      tabline = {},
      extensions = {},
    })
  end,
  }
}
