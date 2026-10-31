-- Bootstrap lazy.nvim（自动下载插件管理器）
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
-- 这里用 uv/fs_stat 判断是否已安装，避免每次启动都 git clone
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  local lazyrepo = "https://github.com/folke/lazy.nvim.git"
  -- 仅拉取必要内容，减少下载体积
  local out = vim.fn.system({ "git", "clone", "--filter=blob:none", "--branch=stable", lazyrepo, lazypath })
  -- clone 失败时提示并退出，避免后续报错
  if vim.v.shell_error ~= 0 then
    vim.api.nvim_echo({
      { "Failed to clone lazy.nvim:\n", "ErrorMsg" },
      { out, "WarningMsg" },
      { "\nPress any key to exit..." },
    }, true, {})
    vim.fn.getchar()
    os.exit(1)
  end
end
-- 把 lazy.nvim 放到运行时路径最前面，保证能被 require
vim.opt.rtp:prepend(lazypath)

-- Make sure to setup `mapleader` and `maplocalleader` before
-- loading lazy.nvim so that mappings are correct.
-- This is also a good place to setup other settings (vim.opt)
-- 统一 Leader 键，后续的快捷键配置都基于它
vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- lazy 管理入口（核心快捷键，不要太多）：
--   <leader>lz 打开插件管理面板
--   :Lazy 也可以手动打开
vim.keymap.set("n", "<leader>lz", "<cmd>Lazy<cr>", { noremap = true, silent = true, desc = "Lazy 管理面板" })

-- Setup lazy.nvim（插件加载入口）
require("lazy").setup({
  spec = {
    -- 插件清单入口，统一从 lua/plugins/ 目录导入
    { import = "plugins" },
  },
  -- Configure any other settings here. See the documentation for more details.
  -- colorscheme that will be used when installing plugins.
  -- install = { colorscheme = { "habamax" } },
  -- automatically check for plugin updates
  -- checker = { enabled = true },
})
