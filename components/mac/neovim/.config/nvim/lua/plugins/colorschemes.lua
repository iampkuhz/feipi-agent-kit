-- 快捷键清单（每行一个）：
-- 本文件插件未定义快捷键。
return {
  -- 这里是你其他插件的列表
  {
    "catppuccin/nvim",
    name = "catppuccin",   -- 为了在后面引用时更方便
    priority = 1000,       -- 当你想确保它在其它主题之前加载时可使用
    config = function()
      -- 这里是插件加载完成后要执行的配置代码
      vim.cmd.colorscheme("catppuccin-mocha")
    end
  },

  -- 其它插件 ...
}
