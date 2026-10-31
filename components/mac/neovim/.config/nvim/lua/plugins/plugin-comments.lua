-- 代码注释工具
-- 快捷键清单（每行一个）：
-- todo-comments：本文件未显式定义快捷键。
-- Comment.nvim `gcc`：注释/取消注释当前行。
-- Comment.nvim `gbc`：块注释/取消注释当前行。
-- Comment.nvim `vipgc`：可视模式下按行注释选区。
-- Comment.nvim `vipgb`：可视模式下按块注释选区。
return {

  -- 插件：todo-comments，支持多种todo类型
  -- 包括的keyword有：
  -- TODO:
  -- HACK:
  -- WARN:
  -- PERF:
  -- NOTE:
  -- TEST:
  -- ERROR:
  -- FIX:
  -- WARNING:
  {
    "folke/todo-comments.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    opts = {
      -- your configuration comes here
      -- or leave it empty to use the default settings
      -- refer to the configuration section below
    }
  },

  -- 插件：注释
  -- 快捷键：'gcc' 注释当前行
  -- 快捷键：'gbc' 使用块注释注释当前行
  -- 快捷键：'vipgc' 先试用visual模式选中段落，然后对整个段落单行注释
  -- 快捷键：'vipgb' 先试用visual模式选中段落，然后对整个段落块注释
  {
    'numToStr/Comment.nvim',
    opts = {
      -- add any options here
    }
  }

}
