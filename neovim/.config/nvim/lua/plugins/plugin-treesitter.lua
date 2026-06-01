-- Neovim 0.12+ treesitter 配置
--
-- 说明：
--   - 使用 nvim-treesitter main 分支，适配 Neovim 0.12+
--   - 需要安装 tree-sitter-cli（brew install tree-sitter-cli），仅装 node 不够
--   - 升级后首次启动需执行 :TSUpdate 拉取/编译最新 parser
--   - 如果 Markdown 仍报 "attempt to call method 'range' (a nil value)" 等错误，
--     建议清理旧 parser/query 缓存：
--       rm -rf ~/.local/share/nvim/site/parser/*
--       rm -rf ~/.local/share/nvim/site/queries/*
--     然后重新启动 Neovim 并执行 :TSUpdate

return {
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    lazy = false,
    build = ":TSUpdate",
    config = function()
      -- 需要安装的语言列表
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

      -- 新版配置：不再使用旧 configs 模块
      treesitter.setup({
        install_dir = vim.fn.stdpath("data") .. "/site",
      })

      -- 安装 parser，用 pcall 保护，避免某个 parser 失败导致启动崩溃
      pcall(function()
        treesitter.install(ensure_installed)
      end)

      -- filetype -> treesitter language 映射
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

          -- 启动 treesitter 高亮；markdown 失败时静默，不弹栈
          pcall(vim.treesitter.start, args.buf, lang)

          -- Neovim 0.12 推荐的 folding 设置
          vim.wo.foldmethod = "expr"
          vim.wo.foldexpr = "v:lua.vim.treesitter.foldexpr()"
          vim.wo.foldlevel = 99

          -- treesitter indent：markdown 不启用，避免和 markview 冲突
          if ft ~= "markdown" then
            pcall(function()
              vim.bo[args.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
            end)
          end
        end,
      })
    end,
  },
}
