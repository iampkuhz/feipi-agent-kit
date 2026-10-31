-- 文件: lua/plugins/lsp_cmp.lua
-- 代码自动补全配置
-- 快捷键清单（每行一个）：
-- nvim-cmp `<CR>`：确认当前补全项（插入模式补全菜单）。
-- nvim-cmp `<Tab>`：选择下一个补全项（插入模式补全菜单）。
-- nvim-cmp `<S-Tab>`：选择上一个补全项（插入模式补全菜单）。
-- 命令行模式 `<Tab>`：触发命令行补全。
-- nvim-lspconfig：本文件未定义快捷键。
-- mason.nvim：本文件未定义快捷键。
return {
  -- 1. 自动补全框架 nvim-cmp 本体
  {
    "hrsh7th/nvim-cmp",
    -- nvim-cmp 依赖的补全源和 snippet 引擎
    dependencies = {
      -- LSP 补全源, 显示每个候选来源自哪个插件
      "hrsh7th/cmp-nvim-lsp",
      -- 从 buffer 里补全, 从当前buffer文本里面提取词条做不全
      "hrsh7th/cmp-buffer",
      -- 路径补全
      "hrsh7th/cmp-path",
      -- snippet 引擎，可以展示snippets
      "L3MON4D3/LuaSnip",
      -- LuaSnip 的补全源, 候选列表会由snippet条目，图标不同
      "saadparwaiz1/cmp_luasnip",
      -- 可选，提供美观图标, 给候选加上 图标+类型名
      "onsails/lspkind-nvim",
      -- 可选，提供丰富的预置 snippet
      "rafamadriz/friendly-snippets",
      -- 命令行补全, 让 /,: 命令行模式也可以支持自动补全
      "hrsh7th/cmp-cmdline",
    },
    config = function()
      -- 引入 nvim-cmp
      local cmp = require("cmp")
      local luasnip = require("luasnip")
      local lspkind = require("lspkind")
      -- 可选：加载 friendly-snippets
      require("luasnip.loaders.from_vscode").lazy_load()
      -- 记录本次 completion 菜单里已经出现过的 label, 用来去重
      -- 如果同一个候选值某个来源提示了，另一个来源不重复提示
      local seen_labels = {}
      cmp.event:on("menu_opened", function()
        seen_labels = {}
      end)
      cmp.event:on("menu_closed", function()
        seen_labels = {}
      end)
      cmp.event:on("complete_done", function()
        seen_labels = {}
      end)

      -- 基本配置
      cmp.setup({
        snippet = {
          expand = function(args)
            luasnip.lsp_expand(args.body) -- 让 nvim-cmp 调用 LuaSnip 来处理 snippet
          end,
        },
        mapping = {
          ["<CR>"] = cmp.mapping.confirm({ select = true }), -- 回车确认
          ["<Tab>"] = cmp.mapping.select_next_item(), -- Tab 切换
          ["<S-Tab>"] = cmp.mapping.select_prev_item(),
        },
        sources = cmp.config.sources({
          -- 让 LSP 靠前（= 优先保留 LSP，过滤掉后面的重复）
          {
            name = "nvim_lsp",
            entry_filter = function(entry, _)
              local label = entry.completion_item and entry.completion_item.label or ""
              if label ~= "" and not seen_labels[label] then
                seen_labels[label] = "nvim_lsp"
              end
              return true -- LSP 一律保留
            end,
          },
          { name = "luasnip" },
          -- Buffer 放在后面：如果 label 已经被上面的 source 放过，就丢弃
          {
            name = "buffer",
            keyword_length = 2,
            max_item_count = 5,
            entry_filter = function(entry, _)
              local label = entry.completion_item and entry.completion_item.label or ""
              if label ~= "" and seen_labels[label] then
                return false -- 丢掉与 LSP/前序 source 重复的
              end
              seen_labels[label] = "buffer"
              return true
            end,
          },
          { name = "path" },
        }),
        performance = {
          fetching_timeout = 8000,
        },
        -- 可选：使用 lspkind 增强显示
        formatting = {
          fields = { "kind", "abbr", "menu" },
          format = lspkind.cmp_format({
            mode = "symbol_text",
            maxwidth = 100,
            ellipsis_char = "...",
            before = function(entry, vim_item)
              local menu = { nvim_lsp = "[LSP]", luasnip = "[SNIP]", buffer = "[BUF]", path = "[PATH]" }
              vim_item.menu = menu[entry.source.name] or ("[" .. entry.source.name .. "]")
              -- vim_item.dup = ({ nvim_lsp = 0, buffer = 1, path = 1, luasnip = 1 })[entry.source.name] or 0
              return vim_item
            end,
          }),
        },
      })
      -- 为 `/` 搜索模式配置补全
      cmp.setup.cmdline("/", {
        mapping = cmp.mapping.preset.cmdline(),
        sources = {
          { name = "buffer" },
        },
      })

      -- 为 `:` 命令行模式配置补全
      cmp.setup.cmdline(":", {
        mapping = cmp.mapping.preset.cmdline(),
        sources = cmp.config.sources({
          { name = "path" },
        }, {
          { name = "cmdline" },
        }),
      })
      -- 添加命令行模式的 Tab 键补全映射
      vim.api.nvim_set_keymap("c", "<Tab>", "v:lua.cmp#complete()", { noremap = true, expr = true })
    end,
  },

  -- 2. nvim-lspconfig：配置语言服务器
  {
    "neovim/nvim-lspconfig",
    config = function()
      -- 让 cmp-nvim-lsp 获取正确的 capabilities
      local capabilities = require("cmp_nvim_lsp").default_capabilities()

      -- 例：配置 lua_ls（原 sumneko_lua）语言服务器
      local lua_ls_config = {
        capabilities = capabilities,
        settings = {
          Lua = {
            diagnostics = {
              globals = { "vim" }, -- 忽略对全局 vim 的警告
            },
          },
        },
      }

      -- Grammarly 在 Node v24 下会把本地 wasm 路径当成 URL 解析而报错；
      -- 如果你安装了 Node 20/22，可通过环境变量指定专用的 Node 路径：
      -- export GRAMMARLY_NODE_PATH="$HOME/.nvm/versions/node/v20.x.x/bin/node"
      local grammarly_node = os.getenv("GRAMMARLY_NODE_PATH")
      local grammarly_config = {
        capabilities = capabilities,
      }
      local grammarly_runner = vim.fn.stdpath("config") .. "/scripts/grammarly-wrapper.js"
      local node_cmd = grammarly_node ~= nil and grammarly_node ~= "" and grammarly_node or "node"
      -- 通过 wrapper 关闭全局 fetch，避免 undici 解析本地 wasm 路径报错
      grammarly_config.cmd = {
        node_cmd,
        grammarly_runner,
        "--stdio",
      }

      -- nvim 0.11+ 新增 vim.lsp.config，避免 lspconfig 框架警告
      if vim.lsp.config ~= nil then
        -- 用新版配置接口注册服务，再显式启用
        vim.lsp.config("lua_ls", lua_ls_config)
        vim.lsp.config("grammarly", grammarly_config)
        vim.lsp.enable({ "lua_ls", "grammarly" })
      else
        -- 旧版回退到 lspconfig.setup，兼容较低版本
        local lspconfig = require("lspconfig")
        lspconfig.lua_ls.setup(lua_ls_config)
        lspconfig.grammarly.setup(grammarly_config)
      end
    end,
  },

  -- 3. 可选：williamboman/mason.nvim + mason-lspconfig.nvim
  -- 让你轻松安装各种语言服务器，不用手动安装
  {
    "williamboman/mason.nvim",
    dependencies = {
      "williamboman/mason-lspconfig.nvim",
    },
    config = function()
      require("mason").setup()
      require("mason-lspconfig").setup({
        ensure_installed = {
          "rust_analyzer",--[[ markdown ]]
          "grammarly", --[[ java ]]
          "ast_grep",
          "solc",
        },
      })
    end,
  },
}
