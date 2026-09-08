#!/usr/bin/env node
'use strict';

/**
 * Pipeline CLI 入口
 *
 * 用法:
 *   node generate_pptx_pipeline.js <slide-ir.json> <output-dir> [--dry-run] [--no-render] [--json] [--max-rounds N] [--mode fast|review|strict]
 *
 * 输出目录:
 *   pipeline-report.json   完整 pipeline 报告
 *   qa-static.json         Static QA 报告
 *   repair-plan.json       修复 plan（如有）
 *   output.pptx            编译成功的 PPTX（如 build 成功）
 *   render-manifest.json   渲染 manifest（如 render 成功）
 *   qa-render.json         Render QA 报告（如 render 成功）
 */

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const fileArgs = args.filter(a => !a.startsWith('--'));
const dryRun = args.includes('--dry-run');
const noRender = args.includes('--no-render');
const jsonFlag = args.includes('--json');
const maxRoundsIdx = args.indexOf('--max-rounds');
const maxRounds = maxRoundsIdx >= 0 ? parseInt(args[maxRoundsIdx + 1], 10) || 3 : 3;
const modeIdx = args.indexOf('--mode');
const mode = modeIdx >= 0 ? args[modeIdx + 1] : 'review';

if (fileArgs.length < 2) {
  console.error('用法: node generate_pptx_pipeline.js <slide-ir.json> <output-dir> [options]');
  console.error('');
  console.error('选项:');
  console.error('  --dry-run        只做 Validate + Static QA + Repair Plan，不编译 PPTX');
  console.error('  --no-render      跳过 Render QA');
  console.error('  --json           输出 JSON 格式的 pipeline report');
  console.error('  --max-rounds N   最大迭代轮次（默认 3）');
  console.error('  --mode MODE      fast、review、strict；draft/production 为兼容 alias');
  process.exit(1);
}

if (!['fast', 'review', 'strict', 'draft', 'production'].includes(mode)) {
  console.error(`错误: 不支持的模式 "${mode}"，请使用 fast、review 或 strict`);
  process.exit(1);
}

const irPath = path.resolve(fileArgs[0]);
const outputDir = path.resolve(fileArgs[1]);

// --- 读取 Slide IR ---
if (!fs.existsSync(irPath)) {
  console.error(`错误: Slide IR 文件不存在: ${irPath}`);
  process.exit(1);
}

let slideIR;
try {
  const raw = fs.readFileSync(irPath, 'utf-8');
  slideIR = JSON.parse(raw);
} catch (e) {
  console.error('错误: Slide IR JSON 解析失败');
  console.error(e.message);
  process.exit(1);
}

// --- 运行 Pipeline ---
const pipelinePath = path.join(__dirname, '..', 'helpers', 'pipeline', 'run-pipeline.js');
const { runPipeline } = require(pipelinePath);

if (!jsonFlag) {
  console.log(`\nPipeline 启动`);
  console.log(`  输入: ${irPath}`);
  console.log(`  输出: ${outputDir}`);
  console.log(`  slide_id: ${slideIR.slide_id}`);
  console.log(`  版式: ${slideIR.layout_pattern}`);
  console.log(`  模式: ${mode}`);
  console.log(`  Dry Run: ${dryRun}`);
  console.log(`  渲染: ${!noRender}`);
  console.log(`  最大轮次: ${maxRounds}`);
  console.log('');
}

(async () => {
  const report = await runPipeline(slideIR, outputDir, {
    maxRounds,
    mode,
    render: !noRender,
    dryRun
  });

  // --- 输出结果 ---
  if (jsonFlag) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    printPipelineReport(report);
  }

  // 退出码
  const finalStatus = report.final_status;
  if (finalStatus === 'pass') {
    process.exit(0);
  } else if (finalStatus === 'needs_user_decision') {
    process.exit(100);
  } else if (finalStatus === 'incomplete') {
    process.exit(2);
  } else {
    process.exit(1);
  }
})();

function printPipelineReport(report) {
  const statusMap = {
    pass: '[PASS]',
    fail: '[FAIL]',
    incomplete: '[INCOMPLETE]',
    needs_user_decision: '[需用户决策]'
  };
  const icon = statusMap[report.final_status] || `[${report.final_status}]`;

  console.log(`=== Pipeline 报告 ${icon} ===\n`);
  console.log(`Slide: ${report.slide_id} (${report.layout_pattern})`);
  console.log(`模式: ${report.mode || 'review'}`);
  console.log(`运行轮次: ${report.rounds.length} / ${report.max_rounds}`);
  console.log(`Dry Run: ${report.dry_run ? '是' : '否'}`);
  console.log('');

  for (const round of report.rounds) {
    console.log(`--- Round ${round.round} ---`);

    // Static QA
    if (round.static_qa) {
      const sq = round.static_qa.summary;
      console.log(`  Static QA: hard_fail=${sq.hard_fail}, warning=${sq.warning}, intentional=${sq.acceptable_intentional}`);
    }

    // Layout Solver
    if (round.layout_solver) {
      console.log(`  Layout Solver: status=${round.layout_solver.status}`);
      if (round.layout_solver.message) {
        console.log(`    说明: ${round.layout_solver.message}`);
      }
    }

    // Static QA post-solve
    if (round.static_qa_post_solve) {
      const sq = round.static_qa_post_solve.summary;
      console.log(`  Static QA (post-solve): hard_fail=${sq.hard_fail}, warning=${sq.warning}, intentional=${sq.acceptable_intentional}`);
    }

    // Render QA
    if (round.render_qa) {
      const rq = round.render_qa.summary;
      console.log(`  Render QA: slides=${rq.slides_checked}, hard_fail=${rq.hard_fail}, warning=${rq.warning}`);
    }

    // Repair Plan
    if (round.repair_plan) {
      const rp = round.repair_plan;
      console.log(`  Repair Plan: status=${rp.status}, actions=${rp.actions ? rp.actions.length : 0}`);
      if (rp.requires_user_decision) {
        console.log(`    建议: ${rp.recommendation}`);
        console.log(`    原因: ${rp.reason}`);
      }
    }

    // Build
    if (round.build_result) {
      if (round.build_result.success) {
        console.log(`  PPTX: 编译成功 (${round.build_result.summary.elements_rendered} 个元素)`);
      } else if (round.build_result.skipped) {
        console.log(`  PPTX: 跳过 (${round.build_result.error})`);
      } else {
        console.log(`  PPTX: 编译失败 (${round.build_result.error})`);
      }
    }

    // Postcheck
    if (round.postcheck) {
      const pc = round.postcheck;
      console.log(`  Postcheck: success=${pc.success}, issues=${pc.issues ? pc.issues.length : 0}`);
      if (pc.issues && pc.issues.length > 0) {
        pc.issues.filter(i => i.severity === 'hard_fail').forEach(i => {
          console.log(`    [hard_fail] ${i.message}`);
        });
      }
    }

    console.log(`  Round 状态: ${round.round_status}`);
    if (round.message) {
      console.log(`  说明: ${round.message}`);
    }
    console.log('');
  }

  console.log(`最终状态: ${report.final_status}`);
  if (report.final_message) {
    console.log(`说明: ${report.final_message}`);
  }
  console.log(`\n报告文件: ${outputDir}/pipeline-report.json`);
  console.log('================================\n');
}
