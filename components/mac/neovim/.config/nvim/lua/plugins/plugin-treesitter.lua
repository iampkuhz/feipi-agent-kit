-- Treesitter 语法高亮、缩进、折叠
--
-- ============================================================
-- 安装 / 升级流程
-- ============================================================
--
-- 1. 安装 tree-sitter-cli
--    旧版 nvim-treesitter 只需 node，Neovim 0.12+ 必须装 tree-sitter-cli：
--      brew install tree-sitter-cli        # macOS
--      sudo apt install tree-sitter-cli    # Ubuntu / Debian
--
-- 2. 同步插件（拉取 nvim-treesitter main 分支并编译 parser）
--    启动 Neovim 后执行：
--      :Lazy sync
--    或者命令行：
--      nvim --headless "+Lazy! sync" +qa
--
-- 3. 更新所有已安装的 parser
--      :TSUpdate
--
-- 4. 检查 health
--      :checkhealth nvim-treesitter
--    确认所有 parser 状态为 "installed"，无 ABI 版本不匹配警告。
--
-- 5. 如果 Markdown 仍报 "attempt to call method 'range' (a nil value)"
--    说明旧 parser 缓存与 Neovim 0.12 treesitter API 不兼容，清理后重装：
--      rm -rf ~/.local/share/nvim/site/parser
--      rm -rf ~/.local/share/nvim/site/queries
--      nvim +TSUpdate +qa
--
-- ============================================================
--
-- 适用环境：Neovim 0.12+  +  nvim-treesitter main 分支
--
-- 快捷键清单：
-- fold `zc`：关闭当前 fold。
-- fold `zo`：打开当前 fold。
-- fold `za`：切换当前 fold 开关。
-- fold `zM`：关闭所有 fold。
-- fold `zR`：打开所有 fold。
-- 缩进 `=`：按语法缩进当前行/选区。
-- 缩进 `gg=G`：从首行到末行整文件缩进。
--
-- 增量选择（incremental_selection）：
--   旧版 nvim-treesitter 的 incremental_selection 模块在 Neovim 0.12 迁移后
--   已不再维护。暂时关闭，等 treesitter 稳定后可用 Neovim 原生或独立插件替代。
--
-- WARN: indent 不等于 formatter，只能简单缩进对齐，无法识别语法
-- indent 快捷键 '='，一般常用的 indent 方法 'gg=G'（跳转到第一行，然后 indent 到最后一行）
return {
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    lazy = false,
    enabled = not vim.g.vscode, -- VS Code 已负责语法高亮，避免 vscode-neovim 启动 Treesitter 装饰器
    build = ":TSUpdate",
    config = function()
      local ensure_installed = {
        "lua",
        "python",
        "typescript",
        "javascript",
        "html",
        "css",
        "java",
        "solidity",
        "rust",
        "markdown",
        "markdown_inline",
        "elixir",
        "erlang",
        "scala",
        "git_config",
        "git_rebase",
        "go",
        "gpg",
        "groovy",
        "haskell",
        "json",
        "jq",
        "kotlin",
        "nginx",
        "ruby",
        "toml",
        "vim",
        "vimdoc",
        "xml",
        "yaml",
        "bash",
      }

      local ok, treesitter = pcall(require, "nvim-treesitter")
      if not ok then
        return
      end

      -- 新版 setup：指定 parser 安装目录
      treesitter.setup({
        install_dir = vim.fn.stdpath("data") .. "/site",
      })

      -- 安装 ensure_installed 列表中的 parser，失败不中断
      pcall(function()
        treesitter.install(ensure_installed)
      end)

      -- filetype → treesitter language 映射
      local ft_to_lang = {
        lua = "lua",
        python = "python",
        typescript = "typescript",
        javascript = "javascript",
        html = "html",
        css = "css",
        java = "java",
        solidity = "solidity",
        rust = "rust",
        markdown = "markdown",
        markdown_inline = "markdown_inline",
        elixir = "elixir",
        erlang = "erlang",
        scala = "scala",
        gitconfig = "git_config",
        gitrebase = "git_rebase",
        go = "go",
        gpg = "gpg",
        groovy = "groovy",
        haskell = "haskell",
        json = "json",
        jq = "jq",
        kotlin = "kotlin",
        nginx = "nginx",
        ruby = "ruby",
        toml = "toml",
        vim = "vim",
        help = "vimdoc",
        vimdoc = "vimdoc",
        xml = "xml",
        yaml = "yaml",
        sh = "bash",
        bash = "bash",
        zsh = "bash",
      }

      local group = vim.api.nvim_create_augroup("UserTreesitter", { clear = true })

      vim.api.nvim_create_autocmd("FileType", {
        group = group,
        callback = function(args)
          local ft = vim.bo[args.buf].filetype
          local lang = ft_to_lang[ft]
          if not lang then
            return
          end

          -- 启动 treesitter 高亮，失败静默（尤其保护 markdown/markview）
          pcall(vim.treesitter.start, args.buf, lang)

          -- Neovim 0.12 原生 foldexpr
          -- foldmethod/foldexpr/foldlevel 是 window-local option，不能用 args.buf 当 window id。
          local function apply_fold_options(bufnr)
            for _, win in ipairs(vim.api.nvim_list_wins()) do
              if vim.api.nvim_win_is_valid(win) and vim.api.nvim_win_get_buf(win) == bufnr then
                vim.wo[win].foldmethod = "expr"
                vim.wo[win].foldexpr = "v:lua.vim.treesitter.foldexpr()"
                vim.wo[win].foldlevel = 99
              end
            end
          end

          apply_fold_options(args.buf)

          -- treesitter indent（markdown 除外，避免和 markview 组合出错）
          if ft ~= "markdown" and ft ~= "markdown_inline" then
            pcall(function()
              vim.bo[args.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
            end)
          end
        end,
      })
    end,
  },
}
