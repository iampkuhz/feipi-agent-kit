-- 文件目录树
-- 快捷键清单（每行一个）：
-- nvim-tree `<Leader>e`：显示/隐藏目录树。
-- nvim-tree `<Leader>n`：把焦点切回目录树。
-- nvim-tree 内部 `o`：打开文件或目录。
-- nvim-tree 内部 `a`：创建文件。
-- nvim-tree 内部 `r`：重命名。
-- nvim-tree 内部 `x`：剪切。
-- nvim-tree 内部 `c`：复制。
-- nvim-tree 内部 `p`：粘贴。
-- nvim-tree 内部 `d`：删除。
-- nvimTree内部快捷键:
--  o: 打开文件或文件夹
--  a: 创建文件
--  r: 重命名
--  x: 剪切
--  c: 拷贝
--  p: 粘贴
--  d: 删除
return {
  "nvim-tree/nvim-tree.lua",
  version = "*",
  lazy = false,
  dependencies = {
    "nvim-tree/nvim-web-devicons",
  },
  config = function()
    require("nvim-tree").setup {}
  end,
}
