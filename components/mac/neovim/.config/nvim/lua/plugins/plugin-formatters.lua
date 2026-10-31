-- 快捷键清单（每行一个）：
-- conform.nvim `<leader>f`：格式化当前缓冲区（支持 normal/visual 等模式）。
return {
  {
    "stevearc/conform.nvim",
    event = { "BufWritePre" },
    -- 快捷键 `:ConformInfo` 查看插件安装现状
    cmd = { "ConformInfo" },
    keys = {
      {
        -- -- 自定义快捷键映射, 使用 `<leader>f` 快捷键来触发格式化操作。
        "<leader>f",
        function()
          require("conform").format({ async = false, lsp_fallback = false, timeout_ms = 2000 })
        end,
        mode = "", -- 适用于所有模式（normal、visual 等）。
        desc = "Format buffer", -- 描述此快捷键的作用：格式化缓冲区
      },
    },

    -- 通过注解提供类型提示（用于 Lua 语言服务器，如 LuaLS）。
    ---@module "conform"
    ---@type conform.setupOpts
    opts = {
      -- 定义各文件类型对应的格式化工具。
      formatters_by_ft = {
        -- 格式化工具需要自己本地安装好，conform.nvim 会调用
        -- brew install shfmt
        lua = { "stylua", stop_after_first = true }, -- Lua 文件使用 `stylua` 格式化工具。
        javascript = { "prettierd", "prettier", stop_after_first = true }, -- JavaScript 文件使用 `prettierd`，如果失败则使用 `prettier`，并在第一个成功后停止。
        typescript = { "prettierd", "prettier", stop_after_first = true },
        json = { "prettierd", "prettier", stop_after_first = true },
        jsonc = { "prettierd", "prettier", stop_after_first = true },
        markdown = { "prettierd", "prettier", stop_after_first = true },
        html = { "prettierd", "prettier", stop_after_first = true },
        css = { "prettierd", "prettier", stop_after_first = true },
        bash = { "shfmt", stop_after_first = true },
        sh = { "shfmt", stop_after_first = true },
        yaml = { "yamlfmt", stop_after_first = true },
        rust = { "rustfmt", lsp_format = "fallback" },
        plantuml = { "puml_formatter", stop_after_first = true },
        -- 未知文件类型不强行交给 Prettier，避免保存普通文本时超时。
      },
      -- 设置默认的格式化选项。
      default_format_opts = {
        lsp_format = "fallback", -- 使用 `lsp_format` 作为格式化的回退选项。
      },
      -- 配置保存时自动格式化。
      format_on_save = { timeout_ms = 500 }, -- 自动格式化超时时间为 500 毫秒。
      -- 自定义格式化工具的参数。
      formatters = {
        shfmt = { -- 自定义 `shfmt` 的格式化参数。
          prepend_args = { "-i", "2" }, -- 在 `shfmt` 的调用中添加参数 `-i 2`，设置缩进为 2。
        },
        -- 使用自定义配置的 puml 格式化脚本
        puml_formatter = {
          command = "python3",
          args = { vim.fn.expand("~/.config/nvim/formatter/puml_formatter.py"), "--stdin" },
          stdin = true,
        },
        stylua = {
          args = { "--indent-type", "Spaces", "--indent-width", "2", "-" },
        },
      },
    },

    init = function()
      -- 设置 `formatexpr`，用于指定格式化表达式。
      vim.o.formatexpr = "v:lua.require'conform'.formatexpr()"
    end,
  },
}
