return {
  "milanglacier/minuet-ai.nvim",
  dependencies = { "nvim-lua/plenary.nvim" },
  event = { "BufNewFile", "BufReadPost", "BufEnter" },

  opts = function()
    local api_base = os.getenv("AUTOCOMPLETE_API_BASE")
    if not api_base then
      return { enabled = false }
    end
    local api_key = os.getenv("AUTOCOMPLETE_API_KEY") or ""
    local model = os.getenv("AUTOCOMPLETE_MODEL")

    return {
      virtualtext = {
        auto_trigger_ft = { "*" },
        auto_trigger_ignore_ft = {},
        show_on_completion_menu = true,
        keymap = {
          accept = "<C-;>",
          next = nil,
          prev = nil,
          dismiss = "<C-e>",
        },
      },

      n_completions = 1,

      provider = "openai_fim_compatible",
      provider_options = {
        openai_fim_compatible = {
          name = "local",
          end_point = api_base .. "/completions",
          model = model,
          api_key = function()
            return api_key
          end,
          stream = true,
          optional = {
            n = 1,
            max_tokens = 24,
            top_p = 0.9,
            temperature = 0.2,
            stop = { "\n\n" },
          },
        },
      },

      notify = "warn",
      request_timeout = 20,
      context_window = 16000,
      context_ratio = 0.75,
      throttle = 1000,
      debounce = 250,
      after_cursor_filter_length = 15,
      before_cursor_filter_length = 5,
    }
  end,
}
