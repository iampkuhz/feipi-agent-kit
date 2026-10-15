// 直接调用镜像内固定版本的 draw.io Graph，禁止访问在线编辑器。
async (xml) => {
  // export-init 只透传部分 URL 参数；在本地导出上下文关闭兼容查看器的外链提示。
  urlParams['svg-warning'] = '0';
  document.body.replaceChildren();
  const container = document.createElement('div');
  document.body.appendChild(container);
  const graph = new Graph(container);
  graph.setEnabled(false);
  const doc = mxUtils.parseXml(xml);
  new mxCodec(doc).decode(doc.documentElement, graph.getModel());
  graph.refresh();
  await document.fonts.ready;
  graph.refresh();
  const cells = Object.values(graph.getModel().cells).filter(c => c.vertex || c.edge);
  const geometry = cells.map(cell => {
    const state = graph.view.getState(cell);
    if (!state) throw new Error('不可见的 cell: ' + cell.id);
    const box = state.text && state.text.boundingBox;
    return {
      id: cell.id, edge: !!cell.edge,
      rect: [state.x, state.y, state.width, state.height],
      text: box ? [box.x, box.y, box.width, box.height] : null,
      points: (state.absolutePoints || []).filter(Boolean).map(p => [p.x, p.y])
    };
  });
  const svg = graph.getSvg('#ffffff', 1, 20);
  graph.disableSvgLinks(svg);
  return {svg: mxUtils.getXml(svg), geometry};
}
