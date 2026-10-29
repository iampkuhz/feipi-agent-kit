#!/usr/bin/env node
// 固定依赖、本地浏览器、单次渲染；同一 SVG 提供 PNG 与几何证据。
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import puppeteer from 'puppeteer';
import {renderMermaid} from '@mermaid-js/mermaid-cli';

const version = async name => JSON.parse(await fs.readFile(new URL('../node_modules/'+name+'/package.json',import.meta.url),'utf8')).version;
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const args = process.argv.slice(2);
const value = flag => args.includes(flag) ? args[args.indexOf(flag)+1] : undefined;
let browser;
let stage = 'renderer';
try {
  let executablePath = value('--browser');
  if (!executablePath) {
    const candidates = [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome',
    ];
    for (const candidate of candidates) {
      try {await fs.access(candidate); executablePath = candidate; break;} catch {}
    }
  }
  browser = await puppeteer.launch({executablePath, headless:true, timeout:15000,
    protocolTimeout:30000, args:['--disable-background-networking']});
  const renderer = {
    cli:await version('@mermaid-js/mermaid-cli'),
    mermaid:await version('mermaid'),
    puppeteer:await version('puppeteer'),
    browser:await browser.version(),
  };
  const locked=JSON.parse(await fs.readFile(new URL('../package-lock.json',import.meta.url),'utf8'));
  for (const [field,name] of Object.entries({cli:'@mermaid-js/mermaid-cli',mermaid:'mermaid',puppeteer:'puppeteer'})) {
    if(renderer[field] !== locked.packages['node_modules/'+name].version) throw new Error('依赖版本与 lockfile 不一致，请重新 npm ci');
  }
  if (args.includes('--check')) {
    console.log(JSON.stringify({status:'ready',renderer}));
  } else {
    const out = value('--out-dir');
    const source = await fs.readFile(value('--source'),'utf8');
    const brief = JSON.parse(await fs.readFile(value('--brief'),'utf8'));
    // CLI 使用伪域名拦截本地 ESM；除此之外不准联网。
    const newPage = browser.newPage.bind(browser);
    browser.newPage = async () => {
      const page = await newPage();
      await page.setRequestInterception(true);
      page.on('request', request => {
        if (/^https?:/.test(request.url()) && !request.url().startsWith('https://mermaid-cli-intercept.invalid/')) {
          request.abort('blockedbyclient',100);
        } else {
          request.continue({},-100);
        }
      });
      return page;
    };
    stage = 'render';
    const spacing = brief.layout?.spacing ?? 60;
    const {data} = await renderMermaid(browser,source,'svg',{
      viewport:{width:1600,height:1200,deviceScaleFactor:1},backgroundColor:'white',fontEmbed:false,
      mermaidConfig:{nodeSpacing:spacing,rankSpacing:spacing,securityLevel:'strict',theme:'base',htmlLabels:true,
        fontFamily:'Arial, PingFang SC, Noto Sans CJK SC, sans-serif',
        themeVariables:{fontSize:'16px',primaryColor:'#edf3ff',primaryTextColor:'#17243b',
          primaryBorderColor:'#5679a6',lineColor:'#52657d',secondaryColor:'#eff8f2',tertiaryColor:'#f6f7fb'},
        flowchart:{htmlLabels:true,curve:'linear',nodeSpacing:spacing,rankSpacing:spacing,padding:18,useMaxWidth:false},
        sequence:{useMaxWidth:false,wrap:false,actorMargin:spacing,mirrorActors:false},
        mindmap:{useMaxWidth:false,padding:18},
      },
    });
    const svg = Buffer.from(data).toString('utf8');
    if (/<(?:script|iframe|image)\b/i.test(svg)) throw new Error('SVG 含不允许的活动资源');
    if (/class="error-icon"/.test(svg)) throw new Error('Mermaid 返回错误图：'+[...svg.matchAll(/<text[^>]*class="error-text"[^>]*>(.*?)<\/text>/g)].map(x=>x[1]).join(' '));
    stage = 'layout';
    const page = await browser.newPage();
    await page.setViewport({width:1600,height:1200,deviceScaleFactor:1});
    await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:white">'+svg+'</body></html>');
    await page.evaluate(() => document.fonts.ready);
    // 原生 mindmap 的力导向布局没有公开间距控制；保留节点尺寸，按中心拉开位置和边。
    if (/^\s*mindmap\b/.test(source)) {
      await page.$eval('svg',(svg,factor)=>{
        const root=svg.querySelector('.mindmap-node.section-root');
        if (!root) throw new Error('无法定位原生思维导图根节点');
        const origin=root.transform.baseVal.consolidate().matrix;
        const dx=origin.e*(1-factor),dy=origin.f*(1-factor);
        for(const node of svg.querySelectorAll('.mindmap-node')) {
          const t=node.transform.baseVal.consolidate().matrix;
          node.setAttribute('transform',`translate(${factor*t.e+dx},${factor*t.f+dy})`);
        }
        for(const edge of svg.querySelectorAll('path.edge,path.flowchart-link')) {
          edge.setAttribute('transform',`matrix(${factor},0,0,${factor},${dx},${dy})`);
          edge.setAttribute('vector-effect','non-scaling-stroke');
        }
      },1+spacing/60);
    }
    const dimensions = await page.$eval('svg', el => {
      const original = el.viewBox.baseVal;
      // 仅扩展真实文字边界；甘特图图外的今日线等有意裁切内容不应扩大画布。
      const inverse=el.getScreenCTM().inverse();
      const bounds=[...el.querySelectorAll('text,foreignObject,g.mindmap-node')].filter(e=>e.textContent.trim() && getComputedStyle(e).visibility!=='hidden').map(e=>{
        const r=e.getBoundingClientRect();
        return [new DOMPoint(r.x,r.y).matrixTransform(inverse),new DOMPoint(r.right,r.bottom).matrixTransform(inverse)];
      });
      const x=Math.min(original.x,...bounds.map(r=>r[0].x))-8;
      const y=Math.min(original.y,...bounds.map(r=>r[0].y))-8;
      const right=Math.max(original.x+original.width,...bounds.map(r=>r[1].x))+8;
      const bottom=Math.max(original.y+original.height,...bounds.map(r=>r[1].y))+8;
      el.setAttribute('viewBox',`${x} ${y} ${right-x} ${bottom-y}`);
      const v = el.viewBox.baseVal;
      if (!v.width || !v.height || v.width > 6000 || v.height > 6000) throw new Error('图面尺寸必须在 1–6000 px');
      el.style.maxWidth='none'; el.setAttribute('width',String(Math.ceil(v.width)));el.setAttribute('height',String(Math.ceil(v.height)));
      return {width:Math.ceil(v.width),height:Math.ceil(v.height)};
    });
    await page.setViewport({...dimensions,deviceScaleFactor:1});
    // DAGRE 默认将分组标题居中，纵向入边容易穿字；把标题置于左上角。
    await page.$$eval('g.cluster', clusters => {
      for (const group of clusters) {
        const rect=group.querySelector(':scope > rect');
        const label=group.querySelector(':scope > .cluster-label');
        if (rect && label) {
          const box=rect.getBBox();
          label.setAttribute('transform',`translate(${box.x+8},${box.y+6})`);
        }
      }
    });
    const geometry = await page.$eval('svg', svg => {
      const matrix = svg.getScreenCTM().inverse();
      const rect = element => {
        const r = element.getBoundingClientRect();
        const a = new DOMPoint(r.x,r.y).matrixTransform(matrix);
        const b = new DOMPoint(r.right,r.bottom).matrixTransform(matrix);
        return [a.x,a.y,b.x-a.x,b.y-a.y];
      };
      const texts = [...svg.querySelectorAll('text,foreignObject')].filter(e => e.textContent.trim() && getComputedStyle(e).visibility !== 'hidden' && rect(e)[2] > 0).map(e => ({
        text:e.textContent.trim(),rect:rect(e),masked_edge:e.closest('[data-id]')?.getAttribute('data-id') || null,
        masked_node:e.closest('.mindmap-node')?.id || null,
      }));
      const paths = [...svg.querySelectorAll('path.flowchart-link,path.edge,path.edgePath,path.messageLine0,path.messageLine1,line.messageLine0,line.messageLine1')];
      const edges = paths.map((el,i) => {
        const length = el.getTotalLength();
        const transform = el.getScreenCTM();
        const points = [];
        for (let n=0;n<=Math.ceil(length/2);n++) {
          const p=el.getPointAtLength(Math.min(n*2,length));
          const q=new DOMPoint(p.x,p.y).matrixTransform(transform).matrixTransform(matrix);
          points.push([q.x,q.y]);
        }
        const endpoints=el.id.match(/^(.*)-edge_(\d+)_(\d+)$/);
        return {id:el.id || 'edge-'+i,points,masked_endpoints:endpoints ? [endpoints[1]+'-node_'+endpoints[2],endpoints[1]+'-node_'+endpoints[3]] : []};
      });
      const v=svg.viewBox.baseVal;
      const nodes=[...svg.querySelectorAll('.mindmap-node')].map(n=>({id:n.id,rect:rect(n)}));
      return {view_box:[v.x,v.y,v.width,v.height],texts,edges,nodes};
    });
    if (!geometry.texts.length) throw new Error('无法提取文字几何，必须人工检查工具支持');
    const finalSVG=await page.$eval('svg',svg=>new XMLSerializer().serializeToString(svg));
    const evidence = {...geometry,source_sha256:hash(source),svg_sha256:hash(finalSVG),renderer};
    await fs.writeFile(path.join(out,'diagram.svg'),finalSVG);
    await (await page.$('svg')).screenshot({path:path.join(out,'diagram.png')});
    await fs.writeFile(path.join(out,'render-evidence.json'),JSON.stringify(evidence,null,2)+'\n');
    console.log(JSON.stringify({status:'rendered',renderer}));
  }
} catch (error) {
  console.error(JSON.stringify({status:'blocked',stage,reason:String(error.message || error)}));
  process.exitCode=1;
} finally {
  if (browser) await browser.close();
}
