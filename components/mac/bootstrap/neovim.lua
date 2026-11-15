-- 复用 Lazy/Mason/Treesitter 的原生安装能力；不能只依赖 :Lazy 的退出状态。
-- 在 init.vim 前记录配置错误；最终准备阶段不能忽略其他插件的启动失败。
local startup_errors = {}
local notify = vim.notify
vim.notify = function(message, level, ...)
  if (level or vim.log.levels.INFO) >= vim.log.levels.ERROR then
    table.insert(startup_errors, tostring(message))
  end
  return notify(message, level, ...)
end
local function run()
  local config = require("lazy.core.config")
  local lazy = require("lazy")
  local function check_tasks()
    for name, plugin in pairs(config.plugins) do
      for _, task in ipairs(plugin._.tasks or {}) do
        assert(not task:has_errors(), name .. ": " .. task:output())
      end
    end
  end

  if vim.env.FEIPI_NVIM_PHASE == "restore" then
    -- Lazy 会重写锁文件排版；保留受管文件原文，避免恢复成功后来源检查报漂移。
    local original_lock = vim.fn.readfile(config.options.lockfile, "b")
    local restored, restore_error = pcall(lazy.restore, { wait = true, show = false })
    vim.fn.writefile(original_lock, config.options.lockfile, "b")
    assert(restored, restore_error)
    check_tasks()
    print("[通过] Lazy 锁定插件恢复")
    return
  end

  -- 锁文件缺项或实际 HEAD 不符都失败，防止已有缓存掩盖恢复遗漏。
  local lock = vim.json.decode(table.concat(vim.fn.readfile(config.options.lockfile), "\n"))
  for name, plugin in pairs(config.plugins) do
    if plugin.url then
      assert(lock[name], "锁文件缺少插件：" .. name)
      local head = vim.fn.system({ "git", "-C", plugin.dir, "rev-parse", "HEAD" }):gsub("%s+$", "")
      assert(vim.v.shell_error == 0 and head == lock[name].commit, "插件版本不符：" .. name)
    end
  end

  lazy.load({ plugins = { "mason.nvim", "nvim-treesitter", "markdown-preview.nvim", "conform.nvim" } })
  lazy.build({ plugins = { "markdown-preview.nvim" }, wait = true, show = false })
  check_tasks()

  -- 同一份清单供配置与首次安装使用；下载任务完成后逐个实际加载解析器。
  local parsers = config.plugins["nvim-treesitter"].opts.ensure_installed
  require("nvim-treesitter").install(parsers):wait(600000)
  for _, language in ipairs(parsers) do
    assert(pcall(vim.treesitter.language.add, language), "无法加载解析器：" .. language)
  end
  print("[通过] " .. #parsers .. " 个 Treesitter 解析器")

  local registry = require("mason-registry")
  local refreshed, refresh_ok = false, false
  registry.refresh(function(ok)
    refresh_ok, refreshed = ok, true
  end)
  assert(vim.wait(180000, function()
    return refreshed
  end, 100) and refresh_ok, "Mason registry 准备失败")
  local mapping = require("mason-lspconfig.mappings").get_mason_map().lspconfig_to_package
  local packages = {}
  for _, server in ipairs(require("mason-lspconfig.settings").current.ensure_installed) do
    assert(mapping[server], "Mason 不支持已配置的服务：" .. server)
    local package = registry.get_package(mapping[server])
    if not package:is_installed() and not package:is_installing() then
      package:install()
    end
    table.insert(packages, package)
  end
  assert(
    vim.wait(600000, function()
      for _, package in ipairs(packages) do
        if package:is_installing() then
          return false
        end
      end
      return true
    end, 200),
    "Mason 工具安装超时"
  )
  for _, package in ipairs(packages) do
    assert(package:is_installed(), "Mason 安装失败：" .. package.name .. "；详见 :MasonLog")
  end
  print("[通过] " .. #packages .. " 个 Mason 语言服务器")

  -- 打开真实缓冲区，检查解析器、Lua LSP 初始化与 Markdown 的本机 HTTP 预览。
  vim.cmd("enew")
  vim.api.nvim_buf_set_name(0, vim.fn.tempname() .. ".lua")
  vim.api.nvim_buf_set_lines(0, 0, -1, false, { "local answer=42", "print(answer)" })
  vim.bo.filetype = "lua"
  assert(#vim.treesitter.get_parser(0, "lua"):parse() > 0, "Lua 解析失败")
  assert(
    vim.wait(60000, function()
      for _, client in ipairs(vim.lsp.get_clients({ bufnr = 0, name = "lua_ls" })) do
        if client.initialized then
          return true
        end
      end
      return false
    end, 100),
    "Lua LSP 未完成初始化"
  )
  print("[通过] Lua 缓冲区解析与 LSP 初始化")

  local function format_buffer()
    local completed, format_error = false, nil
    require("conform").format({ async = false, lsp_format = "never", timeout_ms = 20000 }, function(err)
      format_error, completed = err, true
    end)
    assert(completed and not format_error, "缓冲区格式化失败：" .. tostring(format_error))
  end
  format_buffer()
  assert(vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == "local answer = 42", "Lua 格式化未生效")
  vim.cmd("enew!")
  vim.api.nvim_buf_set_name(0, vim.fn.tempname() .. ".json")
  vim.api.nvim_buf_set_lines(0, 0, -1, false, { '{"answer":42}' })
  vim.bo.filetype = "json"
  format_buffer()
  local formatted = table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n")
  assert(formatted ~= '{"answer":42}' and vim.json.decode(formatted).answer == 42, "JSON 格式化未生效")
  print("[通过] Lua 与 JSON 实际格式化")

  vim.cmd("enew!")
  vim.api.nvim_buf_set_name(0, vim.fn.tempname() .. ".md")
  vim.api.nvim_buf_set_lines(0, 0, -1, false, { "# 新机预览验收", "", "Markdown preview smoke test." })
  -- 用浏览器回调取得真实 URL，不在无人值守验收中打开浏览器窗口。
  local preview_url
  _G.FeipiPreviewUrl = function(url)
    preview_url = url
  end
  vim.cmd("function! FeipiPreviewUrl(url)\ncall v:lua.FeipiPreviewUrl(a:url)\nendfunction")
  vim.g.mkdp_browserfunc = "FeipiPreviewUrl"
  vim.bo.filetype = "markdown"
  vim.cmd("MarkdownPreview")
  assert(
    vim.wait(60000, function()
      return preview_url ~= nil
    end, 100),
    "Markdown 预览服务未启动"
  )
  -- HTTP 处理会回调 Neovim RPC；异步 curl 保持事件循环可用，避免验收自身造成死锁。
  local response
  vim.system(
    { "curl", "--fail", "--silent", "--max-time", "10", "--noproxy", "*", preview_url },
    { text = true },
    function(result)
      response = result
    end
  )
  assert(
    vim.wait(15000, function()
      return response ~= nil
    end, 100),
    "Markdown HTTP 请求超时"
  )
  assert(response.code == 0 and response.stdout:lower():find("<html", 1, true), "Markdown 预览未返回 HTML")
  vim.cmd("MarkdownPreviewStop")
  print("[通过] Markdown 本机 HTTP 预览")
  assert(#startup_errors == 0, table.concat(startup_errors, "\n"))
end

vim.api.nvim_create_autocmd("VimEnter", {
  once = true,
  callback = function()
    vim.schedule(function()
      local ok, err = xpcall(run, debug.traceback)
      if not ok then
        vim.api.nvim_err_writeln(tostring(err))
        vim.cmd("cquit 1")
      else
        vim.cmd("qa!")
      end
    end)
  end,
})
