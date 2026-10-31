-- leader key 为空格
vim.g.mapleader = " "
vim.g.maplocalleader = " "
-- 保存本地变量, 之后就可以这样映射按键了【map('模式','按键','映射为XX',opt)】
local map = vim.api.nvim_set_keymap
local opt = {noremap = true, silent = true }

-- 原始空格键在normal模式会向后移动一个字符，禁用之，方便<Leader>键
map("n", " ", "", opt)

-- normal模式里，Ctrl+j 设置为下翻4行
map("n", "<C-j>", "4j", opt)
-- normal模式里，Ctrl+k 设置为上翻4行
map("n", "<C-k>", "4k", opt)
-- 插入模式里，Ctrl+h 设置为跳转到行首
map("i", "<C-h>", "<ESC>I", opt)
-- 插入模式里，Ctrl+l 设置为跳转到行尾
map("i", "<C-l>", "<ESC>A", opt)

-- ctrl u / ctrl + d  只移动16行(默认值是移动半屏, 太多了)
map("n", "<C-u>", "16k", opt)
map("n", "<C-d>", "16j", opt)

-- 文本显示类快捷键
-- `<Leader>ww`：切换当前窗口自动换行（wrap），比 `<Leader>tw` 更直观
map("n", "<Leader>ww", ":setlocal wrap!<CR>", opt)

-- visual模式下缩进代码
map("v", "<", "<gv", opt)
map("v", ">", ">gv", opt)

-- magic search
map("n", "/", "/\\v", { noremap = true , silent = false})
map("v", "/", "/\\v", { noremap = true , silent = false})

-- 分屏快捷键
map("n", "<Leader>sv", ":vsp<CR>", opt)
map("n", "<Leader>sh", ":sp<CR>", opt)
-- 关闭当前tab
map("n", "<Leader>sc", "<C-w>c", opt)
-- 关闭其他tab
map("n", "<Leader>so", "<C-w>o", opt) -- close others
-- 分屏比例控制
map("n", "<Leader>s.", ":vertical resize +20<CR>", opt)
map("n", "<Leader>s,", ":vertical resize -20<CR>", opt)
map("n", "<Leader>s=", "<C-w>=", opt)
map("n", "<Leader>sj", ":resize -10<CR>", opt)
map("n", "<Leader>sk", ":resize +10<CR>", opt)

-- alt + hjkl  窗口之间跳转
map("n", "<A-h>", "<C-w>h", opt)
map("n", "<A-j>", "<C-w>j", opt)
map("n", "<A-k>", "<C-w>k", opt)
map("n", "<A-l>", "<C-w>l", opt)


-- nvimTree 操作快捷键
-- nvimTree内部快捷键
--  o: 打开文件或文件夹
--  a: 创建文件
--  r: 重命名
--  x: 剪切
--  c: 拷贝
--  p: 粘贴
--  d: 删除
map("n", "<Leader>e", ":NvimTreeToggle<CR>", opt)
-- 快速跳转回目录树
map("n", "<Leader>n", ":NvimTreeFocus<CR>", opt)
