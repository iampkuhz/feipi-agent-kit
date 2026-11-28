/**
 * Shared pipeline level computation.
 *
 * Rules:
 *   full      = pptxgenjs available AND render engine available
 *   pptx-build = pptxgenjs available AND render engine NOT available
 *   static-only = pptxgenjs NOT available (render status is irrelevant)
 *
 * Both pptxgenjs and render are required for "full".
 * Render alone without pptxgenjs cannot produce a pipeline output.
 */

function computePipelineLevel(capabilities) {
  const pptxAvailable = !!(capabilities && capabilities.pptxgenjs && capabilities.pptxgenjs.available);
  const renderAvailable = !!(capabilities && capabilities.render && capabilities.render.status === "available");

  if (pptxAvailable && renderAvailable) return "full";
  if (pptxAvailable) return "pptx-build";
  return "static-only";
}

module.exports = { computePipelineLevel };
